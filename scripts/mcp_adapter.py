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
