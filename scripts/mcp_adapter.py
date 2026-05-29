"""MCP adapter layer — the only place the ATAM controller talks to hashharness.

Three responsibilities (mirrors psyinterviewer/stipo-r/scripts/mcp_adapter.py):
  1. Wrap MCP create_item / find_items / etc.
  2. Bind record_sha256s to roles by TEXT (not by submission order).
  3. Provide a FakeAdapter for tests so controller logic is testable
     without a live hashharness store.
"""

from __future__ import annotations

import hashlib
import json
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any


def _sha256_text(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


@dataclass
class ItemSpec:
    type: str
    work_package_id: str
    title: str
    text: str
    attributes: dict[str, Any] = field(default_factory=dict)
    links: dict[str, Any] = field(default_factory=dict)

    @property
    def text_sha256(self) -> str:
        return _sha256_text(self.text)


class McpAdapter(ABC):
    @abstractmethod
    def create_item(self, spec: ItemSpec) -> str: ...

    def create_items_parallel(self, specs: list[ItemSpec]) -> dict[str, str]:
        """Create N items. Returns {spec.text: record_sha256}, never positional.

        The dict-by-text return prevents the parallel-response-ordering bug.
        """
        out: dict[str, str] = {}
        for spec in specs:
            out[spec.text] = self.create_item(spec)
        return out

    @abstractmethod
    def find_items(
        self,
        type: str | None = None,
        work_package_id: str | None = None,
        limit: int = 50,
    ) -> list[dict[str, Any]]: ...

    @abstractmethod
    def get_item_by_hash(self, record_sha256: str) -> dict[str, Any] | None: ...

    # --- hashharness perf-integration §1: unbounded per-(wp, type) fetch.
    # Replaces find_items(type=T, wp=W, limit=N) which silently truncates at N
    # on long-running evaluations. Subclasses MUST return every matching record.
    @abstractmethod
    def get_work_package(
        self,
        work_package_id: str,
        type: str | None = None,
    ) -> list[dict[str, Any]]: ...

    # --- §3: portfolio enumeration. Default impl is a fallback that scans
    # AtamEvaluation records and dedups workpackage ids; concrete adapters
    # should override with list_work_packages when the primitive is available.
    def list_work_packages(self, prefix: str | None = None) -> list[str]:
        # Fallback: enumerate via AtamEvaluation records.
        evals = self.find_items(type="AtamEvaluation", limit=10000)
        wps: set[str] = set()
        for it in evals:
            wp = it.get("work_package_id", "")
            if wp and (prefix is None or wp.startswith(prefix)):
                wps.add(wp)
        return sorted(wps)

    # --- §4: tip-by-attribute query. Fallback walks the full PhaseGate (or other
    # chain_predecessor type) set and filters client-side; concrete adapters
    # should override with find_tips_where when available.
    def find_tips_where(
        self,
        type: str,
        where_attributes: dict[str, Any] | None = None,
    ) -> dict[str, dict[str, Any]]:
        """Return {work_package_id: tip_record} where the tip's attributes match
        all entries of where_attributes (str==str equality)."""
        all_items = self.find_items(type=type, limit=10000)
        by_wp: dict[str, dict[str, Any]] = {}
        for it in all_items:
            wp = it.get("work_package_id", "")
            if not wp:
                continue
            # last-write-wins by created_at; this is a fallback, not indexed
            prev = by_wp.get(wp)
            if prev is None or it.get("created_at", "") > prev.get("created_at", ""):
                by_wp[wp] = it
        if not where_attributes:
            return by_wp
        out: dict[str, dict[str, Any]] = {}
        for wp, tip in by_wp.items():
            a = tip.get("attributes", {})
            if all(str(a.get(k)) == str(v) for k, v in where_attributes.items()):
                out[wp] = tip
        return out

    # --- §2: cryptographic audit of a whole work package. Fallback uses the
    # existing per-item verification path; override with verify_work_package
    # when the primitive ships.
    def verify_work_package(
        self,
        work_package_id: str,
        summary: bool = True,
    ) -> dict[str, Any]:
        """Structural audit (NOT cryptographic): every record present, every link
        target reachable. Fast because it loads the wp ONCE and resolves
        intra-wp links from an in-memory map. Cross-wp link targets are looked
        up only if not in the wp — at most once per unique sha.

        This is the fallback when upstream `verify_work_package` isn't installed.
        It catches missing records, dangling intra-wp links, and obvious
        corruption — but does NOT re-verify each record's hash binding or schema
        binding the way the upstream primitive does. Document the gap to callers.
        """
        items = self.get_work_package(work_package_id)
        in_wp: set[str] = {it["record_sha256"] for it in items if it.get("record_sha256")}
        errors: list[dict[str, Any]] = []
        external_seen: dict[str, bool] = {}  # sha → present?
        for it in items:
            sha = it.get("record_sha256")
            if not sha:
                errors.append({"text": it.get("text", ""), "error": "missing record_sha256"})
                continue
            for role, val in (it.get("links") or {}).items():
                if role.endswith("Hash") and role[:-4] in (it.get("links") or {}):
                    continue  # digest companion, not a record ref
                targets = val if isinstance(val, list) else [val] if isinstance(val, str) else []
                for t in targets:
                    if not t:
                        continue
                    if t in in_wp:
                        continue
                    if t not in external_seen:
                        external_seen[t] = self.get_item_by_hash(t) is not None
                    if not external_seen[t]:
                        errors.append({"sha": sha, "link_role": role, "missing_target": t,
                                       "text": it.get("text", "")})
        return {
            "work_package_id": work_package_id,
            "ok": not errors,
            "checked_items": len(items),
            "errors_count": len(errors),
            "errors": (errors[:10] if summary else errors),
            "verifier": (
                "atam-adapter-fallback (structural only — every record present and "
                "every link target reachable; does NOT replay hash/schema bindings — "
                "upstream verify_work_package not yet installed)"
            ),
        }


class FakeAdapter(McpAdapter):
    """In-memory substitute for tests."""

    def __init__(self) -> None:
        self._records_by_record_sha: dict[str, dict[str, Any]] = {}
        self._records_by_text: dict[str, dict[str, Any]] = {}

    def _compute_record_sha(self, spec: ItemSpec) -> str:
        link_repr = json.dumps(spec.links, sort_keys=True)
        return hashlib.sha256(
            (spec.text + "|" + link_repr).encode("utf-8")
        ).hexdigest()

    def create_item(self, spec: ItemSpec) -> str:
        record_sha = self._compute_record_sha(spec)
        record = {
            "type": spec.type,
            "work_package_id": spec.work_package_id,
            "title": spec.title,
            "text": spec.text,
            "text_sha256": spec.text_sha256,
            "record_sha256": record_sha,
            "attributes": dict(spec.attributes),
            "links": dict(spec.links),
        }
        self._records_by_record_sha[record_sha] = record
        self._records_by_text[spec.text] = record
        return record_sha

    def find_items(
        self,
        type: str | None = None,
        work_package_id: str | None = None,
        limit: int = 50,
    ) -> list[dict[str, Any]]:
        out: list[dict[str, Any]] = []
        for rec in self._records_by_record_sha.values():
            if type is not None and rec["type"] != type:
                continue
            if work_package_id is not None and rec["work_package_id"] != work_package_id:
                continue
            out.append(rec)
            if len(out) >= limit:
                break
        return out

    def get_item_by_hash(self, record_sha256: str) -> dict[str, Any] | None:
        return self._records_by_record_sha.get(record_sha256)

    def get_work_package(
        self,
        work_package_id: str,
        type: str | None = None,
    ) -> list[dict[str, Any]]:
        out: list[dict[str, Any]] = []
        for rec in self._records_by_record_sha.values():
            if rec["work_package_id"] != work_package_id:
                continue
            if type is not None and rec["type"] != type:
                continue
            out.append(rec)
        return out
