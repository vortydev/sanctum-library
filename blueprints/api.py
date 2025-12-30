from flask import Blueprint, jsonify, request

from scanner import normalize_code, fetch_book_with_fallback
from stores.book_store import BookStore

bp = Blueprint("api", __name__, url_prefix="/api")
store = BookStore.default()


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
    book = fetch_book_with_fallback(value, merge=True, debug=True)
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
