# stores/book_store.py
from __future__ import annotations
import os
import json
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


def project_root_from_here() -> Path:
    # /stores/book_store.py -> project root
    return Path(__file__).resolve().parents[1]


def utc_now_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def safe_slug(s: str) -> str:
    keep = "".join(ch.lower() if ch.isalnum() else "-" for ch in (s or "item"))
    while "--" in keep:
        keep = keep.replace("--", "-")
    return keep.strip("-") or "item"


@dataclass(frozen=True)
class BookStore:
    data_root: Path  # e.g. Path(".../data")

    @classmethod
    def default(cls) -> "BookStore":
        return cls(project_root_from_here() / "data")

    @property
    def items_dir(self) -> Path:
        return self.data_root / "items"

    @property
    def index_path(self) -> Path:
        return self.data_root / "index.json"

    def ensure(self) -> None:
        self.items_dir.mkdir(parents=True, exist_ok=True)
        if not self.index_path.exists():
            self.index_path.write_text(json.dumps({"by_identifier": {}}, indent=2), encoding="utf-8")

    def _load_index(self) -> dict[str, Any]:
        self.ensure()
        return json.loads(self.index_path.read_text(encoding="utf-8"))

    def _save_index(self, idx: dict[str, Any]) -> None:
        tmp = self.index_path.with_suffix(".json.tmp")
        tmp.write_text(json.dumps(idx, indent=2, ensure_ascii=False), encoding="utf-8")
        os.replace(tmp, self.index_path)

    def get_by_identifier(self, kind: str, value: str) -> dict[str, Any] | None:
        idx = self._load_index()
        item_id = idx.get("by_identifier", {}).get(f"{kind}:{value}")
        if not item_id:
            return None
        p = self.items_dir / f"{item_id}.json"
        return json.loads(p.read_text(encoding="utf-8")) if p.exists() else None

    def upsert_book(self, book: dict[str, Any]) -> dict[str, Any]:
        self.ensure()

        idents = book.get("identifiers") or {}
        if "isbn" in idents:
            kind, value = "isbn", idents["isbn"]
        elif "asin" in idents:
            kind, value = "asin", idents["asin"]
        else:
            raise ValueError("book.identifiers must include isbn or asin")

        idx = self._load_index()
        by_ident = idx.setdefault("by_identifier", {})
        ident_key = f"{kind}:{value}"

        existing_id = by_ident.get(ident_key)
        now = utc_now_iso()

        if existing_id:
            item_id = existing_id
            existing = self.get_by_identifier(kind, value) or {}
            merged = {**existing, **book}
            merged["updated_at"] = now
            merged.setdefault("added_at", existing.get("added_at") or now)
            merged.setdefault("id", item_id)
        else:
            title = book.get("title") or f"book-{value}"
            item_id = f"book_{kind}_{value}_{safe_slug(title)[:32]}"
            merged = {**book, "id": item_id, "added_at": now, "updated_at": now}

        path = self.items_dir / f"{item_id}.json"
        tmp = path.with_suffix(".json.tmp")
        tmp.write_text(json.dumps(merged, indent=2, ensure_ascii=False), encoding="utf-8")
        os.replace(tmp, path)

        by_ident[ident_key] = item_id
        self._save_index(idx)

        return merged
