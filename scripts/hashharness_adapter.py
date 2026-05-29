"""Real hashharness adapter — talks to the SQLite-backed store directly via
the `hashharness` Python package.

Drop-in replacement for FakeAdapter in production. Mirrors the stipo-r
implementation so records emitted by this controller are visible to
LLM-driven MCP queries and vice versa.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from mcp_adapter import ItemSpec, McpAdapter


def _maybe_import_hashharness():
    try:
        from hashharness.storage import make_store  # type: ignore

        return make_store
    except ImportError as e:
        raise ImportError(
            "hashharness package not importable. Run via "
            "/Users/a.morozov/.hashharness/venv/bin/python or install hashharness. "
            "Original error: " + str(e)
        ) from e


class HashharnessAdapter(McpAdapter):
    DEFAULT_STORE_PATH = Path.home() / ".hashharness" / "hashharness.sqlite"

    def __init__(self, store_path: str | Path | None = None) -> None:
        make_store = _maybe_import_hashharness()
        self._store_path = Path(store_path) if store_path else self.DEFAULT_STORE_PATH
        self._store = make_store("sqlite", str(self._store_path))

    @property
    def store(self):
        return self._store

    def create_item(self, spec: ItemSpec) -> str:
        r = self._store.create_item(
            item_type=spec.type,
            text=spec.text,
            title=spec.title,
            work_package_id=spec.work_package_id,
            attributes=spec.attributes,
            links=spec.links,
        )
        return r["record_sha256"]

    def find_items(
        self,
        type: str | None = None,
        work_package_id: str | None = None,
        limit: int = 50,
    ) -> list[dict[str, Any]]:
        # §1 routing: callers passing (type, wp) want the entire set in that
        # work-package — not a limited grep. Hand off to get_work_package which
        # is the indexed, unbounded primitive for that intent.
        if type is not None and work_package_id is not None:
            return self.get_work_package(work_package_id, type=type)
        items = self._store.find_items(item_type=type, limit=max(limit * 4, limit))
        if work_package_id is not None:
            items = [i for i in items if i.get("work_package_id") == work_package_id]
        return items[:limit]

    def get_item_by_hash(self, record_sha256: str) -> dict[str, Any] | None:
        all_items = self._store.find_items(limit=10000)
        for it in all_items:
            if it.get("record_sha256") == record_sha256:
                return it
        return None

    def get_work_package(
        self,
        work_package_id: str,
        type: str | None = None,
    ) -> list[dict[str, Any]]:
        """§1 (perf-integration 2026-05-30): unbounded fetch of every record in
        a work-package, optionally filtered by type. Required to fix silent
        truncation from the old find_items(type, wp, limit=N) call sites."""
        # Note: the store kwarg is `item_type`, the MCP tool's is `type`. We
        # accept `type` (matching the MCP-side contract) and forward as
        # `item_type` to the local store.
        kwargs: dict[str, Any] = {"work_package_id": work_package_id}
        if type is not None:
            kwargs["item_type"] = type
        result = self._store.get_work_package(**kwargs)
        # Store returns {work_package_id, type_filter, items, item_count}.
        # Items are the actual records; the rest is metadata.
        if isinstance(result, dict):
            return list(result.get("items") or [])
        return list(result)

    def list_work_packages(self, prefix: str | None = None) -> list[str]:
        """§3: portfolio enumeration. Use the store primitive when available
        (post `30fd482`); otherwise fall back to scanning AtamEvaluation records."""
        if hasattr(self._store, "list_work_packages"):
            kwargs = {}
            if prefix is not None:
                kwargs["prefix"] = prefix
            return list(self._store.list_work_packages(**kwargs))
        return super().list_work_packages(prefix=prefix)

    def find_tips_where(
        self,
        type: str,
        where_attributes: dict[str, Any] | None = None,
    ) -> dict[str, dict[str, Any]]:
        """§4: indexed tip-by-attribute when available; client-side fallback otherwise."""
        if hasattr(self._store, "find_tips_where"):
            kwargs = {"type": type}
            if where_attributes:
                kwargs["where_attributes"] = where_attributes
            return dict(self._store.find_tips_where(**kwargs))
        return super().find_tips_where(type=type, where_attributes=where_attributes)

    def verify_work_package(
        self,
        work_package_id: str,
        summary: bool = True,
    ) -> dict[str, Any]:
        """§2: whole-work-package cryptographic audit. Uses the store primitive
        when available; falls back to the per-item rehydrate check otherwise."""
        if hasattr(self._store, "verify_work_package"):
            return dict(self._store.verify_work_package(
                work_package_id=work_package_id, summary=summary
            ))
        return super().verify_work_package(work_package_id, summary=summary)
