# blueprints/api.py
from __future__ import annotations

import json
from typing import Any
from flask import Blueprint, jsonify, request

from scanner import normalize_code, fetch_book_with_fallback
from stores.book_store import BookStore

bp = Blueprint("api", __name__, url_prefix="/api")
store = BookStore.default()


# ---------------------------
# Helpers
# ---------------------------

def _pick_str_or_first(v):
    if isinstance(v, list):
        for x in v:
            if isinstance(x, str) and x.strip():
                return x.strip()
        return None
    if isinstance(v, str) and v.strip():
        return v.strip()
    return None


def _parse_refresh_opts(payload: dict | None) -> dict:
    payload = payload or {}
    return {
        "debug": bool(payload.get("debug", False)),
        "dry_run": bool(payload.get("dry_run", False)),
        "only_missing": bool(payload.get("only_missing", False)),
        "limit": payload.get("limit"),
    }


def _needs_refresh(book: dict) -> bool:
    # tweak rules as you like
    missing = (
        not (book.get("title") or "").strip()
        or not (book.get("authors") or [])
        or not (book.get("publish_date") or "").strip()
        or not (book.get("cover_image") or "").strip()
        or not (book.get("language") or "").strip()
    )
    return bool(missing)

def _refresh_items(
    items: list[dict[str, Any]],
    *,
    debug: bool,
    dry_run: bool,
    only_missing: bool,
) -> dict[str, Any]:
    """
    Refresh a list of book JSON objects.
    Returns a summary + per-item checklist-friendly arrays.
    """
    out: dict[str, Any] = {
        "counts": {"updated": 0, "skipped": 0, "failed": 0},
        "updated_items": [],
        "skipped_items": [],
        "failed_items": [],
    }

    for cur in items:
        item_id = cur.get("id") or "(no-id)"

        if only_missing and not _needs_refresh(cur):
            out["counts"]["skipped"] += 1
            out["skipped_items"].append({
                "id": item_id,
                "isbn": _best_isbn(cur),
                "title": cur.get("title"),
                "subtitle": cur.get("subtitle"),
                "sources": [s.get("provider") for s in (cur.get("sources") or []) if isinstance(s, dict) and s.get("provider")],
                "reason": "not_missing",
            })
            continue

        res = _refresh_one_book(cur, debug=debug, dry_run=dry_run)

        status = res.get("status")
        if status in ("updated", "dry_run"):
            out["counts"]["updated"] += 1
            saved = res.get("saved") or res.get("book") or cur
            out["updated_items"].append({
                "id": (saved.get("id") or item_id),
                "isbn": _best_isbn(saved),
                "title": saved.get("title"),
                "subtitle": saved.get("subtitle"),
                "sources": _providers(saved),
                "status": status,
            })
        elif status == "skipped":
            out["counts"]["skipped"] += 1
            out["skipped_items"].append({
                "id": item_id,
                "isbn": _best_isbn(cur),
                "title": cur.get("title"),
                "subtitle": cur.get("subtitle"),
                "sources": _providers(cur),
                "reason": res.get("reason") or "skipped",
            })
        else:
            out["counts"]["failed"] += 1
            out["failed_items"].append({
                "id": item_id,
                "isbn": _best_isbn(cur),
                "title": cur.get("title"),
                "subtitle": cur.get("subtitle"),
                "sources": _providers(cur),
                "error": res.get("error") or "refresh_failed",
            })

    return out

def _refresh_one_book(cur: dict[str, Any], *, debug: bool, dry_run: bool) -> dict[str, Any]:
    """
    Refresh a single book based on best ISBN. Optionally dry-run.
    Saves via store.upsert_book() unless dry_run.
    """
    item_id = cur.get("id")
    isbn = _best_isbn(cur)
    if not isbn:
        return {"status": "failed", "id": item_id, "error": "No ISBN available to refresh."}

    fresh = fetch_book_with_fallback(isbn, merge=True, debug=debug)
    if not fresh:
        return {"status": "failed", "id": item_id, "error": f"No provider data for ISBN {isbn}."}

    if dry_run:
        return {"status": "dry_run", "id": item_id, "book": fresh}

    saved = store.upsert_book(fresh)
    return {"status": "updated", "id": saved.get("id") or item_id, "saved": saved}


def _run_refresh(items: list[dict], *, debug: bool, dry_run: bool, only_missing: bool) -> dict:
    updated = []
    skipped = []
    failed = []

    for current in items:
        if only_missing and not _needs_refresh(current):
            skipped.append({"status": "skipped", "id": current.get("id"), "reason": "not_missing"})
            continue

        res = _refresh_one_book(current, debug=debug, dry_run=dry_run)

        if res["status"] in ("updated", "dry_run"):
            updated.append(res)
        elif res["status"] == "skipped":
            skipped.append(res)
        else:
            failed.append(res)

    return {
        "updated": updated,
        "skipped": skipped,
        "failed": failed,
        "counts": {"updated": len(updated), "skipped": len(skipped), "failed": len(failed)},
    }

def _best_isbn(book: dict[str, Any]) -> str | None:
    """
    Prefer isbn13, then isbn10, then isbn.
    """
    ids = book.get("identifiers") or {}
    for k in ("isbn13", "isbn10", "isbn"):
        v = ids.get(k)
        if isinstance(v, str) and v.strip():
            return v.strip()
    return None

def _load_book_file(path):
    return json.loads(path.read_text(encoding="utf-8"))

def _providers(book: dict[str, Any]) -> list[str]:
    srcs = book.get("sources") or []
    out: list[str] = []
    seen = set()
    for s in srcs:
        if not isinstance(s, dict):
            continue
        p = s.get("provider")
        if not p:
            continue
        if p in seen:
            continue
        seen.add(p)
        out.append(p)
    return out


# ---------------------------
# Routes
# ---------------------------

@bp.post("/scan/lookup")
def scan_lookup():
    payload = request.get_json(silent=True) or {}
    raw = (payload.get("code") or "").strip()
    parsed = normalize_code(raw)

    if not parsed:
        return jsonify({"error": "Unsupported code. Expected ISBN-10/13 or ASIN."}), 400

    kind, value = parsed

    if kind == "asin":
        return jsonify({ 
            "kind": kind,
            "value": value,
            "book": None,
            "error": "ASIN detected. No supported provider yet. Skipping."
        }), 200

    # isbn
    book = fetch_book_with_fallback(value, merge=True, debug=False)
    if not book:
        return jsonify({
            "kind": kind,
            "value": value,
            "book": None,
            "error": "No result from OpenLibrary/Google Books for this ISBN."
        }), 200

    return jsonify({"kind": kind, "value": value, "book": book, "error": None}), 200


@bp.post("/books")
def books_create():
    payload = request.get_json(silent=True) or {}
    book = payload.get("book")
    if not isinstance(book, dict):
        return jsonify({"error": "Missing or invalid 'book' object."}), 400

    saved = store.upsert_book(book)
    return jsonify({"saved": saved}), 201


@bp.get("/books")
def books_list():
    q = (request.args.get("q") or "").strip().lower()

    items = []
    for p in store.items_dir.glob("*.json"):
        try:
            items.append(p)
        except Exception:
            continue

    # Load + simple search
    out = []
    for p in items:
        try:
            obj = __import__("json").loads(p.read_text(encoding="utf-8"))
        except Exception:
            continue

        if q:
            hay = f"{obj.get('title','')} {' '.join(obj.get('authors',[]))}".lower()
            if q not in hay:
                continue
        out.append(obj)

    # default sort: newest first
    out.sort(key=lambda x: x.get("added_at") or "", reverse=True)
    return jsonify({"items": out, "count": len(out)}), 200


@bp.get("/books/<item_id>")
def books_get(item_id: str):
    p = store.items_dir / f"{item_id}.json"
    if not p.exists():
        return jsonify({"error": "Not found"}), 404

    obj = __import__("json").loads(p.read_text(encoding="utf-8"))
    return jsonify(obj), 200


@bp.post("/books/refresh")
def books_refresh_all():
    payload = request.get_json(silent=True) or {}
    opts = _parse_refresh_opts(payload)

    files = sorted(store.items_dir.glob("*.json"))
    if isinstance(opts["limit"], int) and opts["limit"] > 0:
        files = files[: opts["limit"]]

    items = []
    read_failed = []

    for p in files:
        try:
            items.append(_load_book_file(p))
        except Exception as e:
            read_failed.append({"id": p.stem, "error": f"read_json: {e}"})

    result = _run_refresh(
        items,
        debug=opts["debug"],
        dry_run=opts["dry_run"],
        only_missing=opts["only_missing"],
    )

    if read_failed:
        result["read_failed"] = read_failed
        result["counts"]["failed"] += len(read_failed)
        # also mirror into failed_items for UI consistency
        for rf in read_failed:
            result["failed_items"].append({
                "id": rf.get("id"),
                "isbn": None,
                "title": None,
                "subtitle": None,
                "sources": [],
                "error": rf.get("error"),
            })
            
    return jsonify(result), 200


@bp.post("/books/<item_id>/refresh")
def books_refresh_one(item_id: str):
    payload = request.get_json(silent=True) or {}
    opts = _parse_refresh_opts(payload)

    p = store.items_dir / f"{item_id}.json"
    if not p.exists():
        return jsonify({"error": "Not found"}), 404

    try:
        current = _load_book_file(p)
    except Exception as e:
        return jsonify({"error": f"Failed to read book JSON: {e}"}), 500

    if opts["only_missing"] and not _needs_refresh(current):
        return jsonify({"status": "skipped", "id": item_id, "reason": "not_missing"}), 200

    res = _refresh_one_book(current, debug=opts["debug"], dry_run=opts["dry_run"])
    code = 200 if res["status"] in ("updated", "dry_run", "skipped") else 502
    return jsonify(res), code