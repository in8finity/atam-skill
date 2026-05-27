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
