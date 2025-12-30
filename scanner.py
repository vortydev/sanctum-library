# scanner.py
from __future__ import annotations
import re
import requests
from datetime import datetime
from typing import Any
from pathlib import Path

from models.scanner_status import ScannerStatus, detect_scanner

# Variables
OPENLIB_BOOKS_API = "https://openlibrary.org/api/books"
GOOGLE_BOOKS_API = "https://www.googleapis.com/books/v1/volumes"


# ========== Helpers ==========

def normalize_isbn(raw: str) -> str | None:
    """
    Accepts scanner input like '978-1-...', ' ISBN:978...', etc.
    Returns digits only ISBN10/ISBN13, else None.
    """
    if not raw:
        return None
    digits = re.sub(r"\D", "", raw)
    if len(digits) in (10, 13):
        return digits
    return None


def normalize_code(raw: str) -> tuple[str, str] | None:
    """
    Returns (kind, value) where kind is 'isbn' or 'asin'.
    - isbn: digits only, len 10 or 13
    - asin: alnum only, len 10 (common for Amazon)
    """
    if not raw:
        return None

    s = raw.strip()

    digits = re.sub(r"\D", "", s)
    if len(digits) in (10, 13):
        return ("isbn", digits)

    alnum = re.sub(r"[^A-Za-z0-9]", "", s)
    if len(alnum) == 10 and alnum.isalnum():
        return ("asin", alnum.upper())

    return None


def extract_unique_genres(genres: list[str]) -> list[str]:
    seen: set[str] = set()
    out: list[str] = []
    for genre in genres or []:
        for sub in (genre or "").split(","):
            g = sub.strip().lower()
            if g and g not in seen:
                seen.add(g)
                out.append(g.capitalize())
    return sorted(out)


def format_publish_date(publish_date: str | None) -> str | None:
    if not publish_date:
        return None

    formats = ["%Y-%m-%d", "%Y-%m", "%Y"]
    for fmt in formats:
        try:
            dt = datetime.strptime(publish_date, fmt)
            return dt.strftime("%Y-%m-%d")
        except ValueError:
            pass
    return None


# ========== Fetching ==========

def fetch_openlibrary_book(isbn: str, timeout_s: int = 10, debug: bool = False,) -> dict[str, Any] | None:
    """
    Returns normalized dict or None if not found.
    """
    params = {"bibkeys": f"ISBN:{isbn}", "format": "json", "jscmd": "data"}
    try:
        r = requests.get(OPENLIB_BOOKS_API, params=params, timeout=timeout_s)
        if debug:
            print("---- OpenLibrary raw response ----")
            print(r.text)
            print("---- end response ----")
        r.raise_for_status()
    except requests.RequestException as e:
        print(f"Open Library request failed: {e}")
        return None

    data = r.json()
    key = f"ISBN:{isbn}"
    b: dict = data.get(key)
    if not b:
        return None
    
    # OpenLibrary can sometimes provide cover links too; keep canonical cover fallback
    cover = None
    if isinstance(b.get("cover"), dict):
        cover = b["cover"].get("large") or b["cover"].get("medium") or b["cover"].get("small")
    cover = cover or f"https://covers.openlibrary.org/b/ISBN/{isbn}-L.jpg"

    b = data[key]
    resp = {
        "type": "book",
        "identifiers": {
            "isbn": isbn,
            "isbn10": None,
            "isbn13": isbn if len(isbn) == 13 else None,
        },
        "subtitle": b.get("subtitle"),
        "authors": [a.get("name") for a in b.get("authors", []) if a.get("name")],
        "publish_date": format_publish_date(b.get("publish_date")),
        "nb_pages": b.get("number_of_pages"),
        "publishers": [p.get("name") for p in b.get("publishers", []) if p.get("name")],
        "genres": extract_unique_genres([s.get("name") for s in b.get("subjects", []) if s.get("name")]),
        "language": None,  # openlibrary 'data' payload doesn't reliably include it
        "description": (b.get("notes") if isinstance(b.get("notes"), str) else None),
        "cover_image": cover,
        "links": {
            "openlibrary": b.get("url"),
        },
        "sources": [{"provider": "openlibrary", "provider_key": key}],
    }
    return resp


def fetch_google_books(isbn: str, timeout_s: int = 10, debug: bool = False) -> dict[str, Any] | None:
    params = {"q": f"isbn:{isbn}"}

    try:
        r = requests.get(GOOGLE_BOOKS_API, params=params, timeout=timeout_s)
        if debug:
            print("---- Google Books raw response ----")
            print(r.text)
            print("---- end response ----")
        r.raise_for_status()
    except requests.RequestException as e:
        print(f"Google Books request failed: {e}")
        return None

    data = r.json()
    items = data.get("items") or []
    if not items:
        return None

    item = items[0]
    v = item.get("volumeInfo") or {}

    isbns = _extract_isbns_from_google(v)
    # Prefer canonical 13-digit if present
    canon_isbn = isbns.get("isbn13") or isbns.get("isbn10") or isbn

    # Description can be long; keep it but it’s optional
    desc = v.get("description")
    if isinstance(desc, str) and len(desc) > 4000:
        desc = desc[:4000] + "..."

    resp = {
        "type": "book",
        "identifiers": {
            "isbn": canon_isbn,
            "isbn10": isbns.get("isbn10"),
            "isbn13": isbns.get("isbn13"),
        },
        "title": v.get("title"),
        "subtitle": v.get("subtitle"),
        "authors": v.get("authors", []) or [],
        "publish_date": format_publish_date(v.get("publishedDate")),
        "nb_pages": v.get("pageCount"),
        "publishers": [v.get("publisher")] if v.get("publisher") else [],
        "genres": extract_unique_genres(v.get("categories", []) or []),
        "language": v.get("language"),
        "description": desc,
        "cover_image": _choose_cover_from_google(v),
        "links": {
            "google": v.get("infoLink"),
            "preview": v.get("previewLink"),
            "canonical": v.get("canonicalVolumeLink"),
        },
        "sources": [{"provider": "google_books", "provider_key": item.get("id")}],
    }
    return resp

def fetch_book_with_fallback(isbn: str, merge: bool = True, debug: bool = False) -> dict[str, Any] | None:
    ol = fetch_openlibrary_book(isbn, debug=debug)
    gb = None

    if ol and merge:
        # try to enrich (language/description/isbns/cover)
        gb = fetch_google_books(isbn, debug=debug)
        return merge_book_data(ol, gb) if gb else ol

    print(f"No Open Library result for ISBN {isbn}, trying Google Books...")
    gb = fetch_google_books(isbn, debug=debug)
    if gb:
        return gb

    print(f"No provider found data for ISBN {isbn}.")
    return None


# ========== Scanner ==========

def listen_scanner(prompt: str = "Scan barcode/ISBN: "):
    """
    Generator that yields normalized ISBNs from stdin (scanner acts like keyboard).
    """
    while True:
        raw = input(prompt).strip()
        isbn = normalize_code(raw)
        if not isbn:
            print("Unsupported code. Expected ISBN-10/13 or ASIN.")
            continue
        yield isbn


# 
def _choose_cover_from_google(v: dict[str, Any]) -> str | None:
    links = v.get("imageLinks") or {}
    return (
        links.get("large")
        or links.get("medium")
        or links.get("small")
        or links.get("thumbnail")
        or links.get("smallThumbnail")
    )

def _extract_isbns_from_google(v: dict[str, Any]) -> dict[str, str]:
    out: dict[str, str] = {}
    for it in v.get("industryIdentifiers", []) or []:
        t = (it.get("type") or "").upper()
        ident = (it.get("identifier") or "").strip()
        if not ident:
            continue
        if t == "ISBN_13":
            out["isbn13"] = ident
        elif t == "ISBN_10":
            out["isbn10"] = ident
    return out

def merge_book_data(primary: dict[str, Any], secondary: dict[str, Any]) -> dict[str, Any]:
    """
    Keep primary as authority, fill missing fields from secondary.
    Merge lists uniquely. Merge identifiers.
    """
    out = {**primary}

    # identifiers
    out_id = {**(secondary.get("identifiers") or {}), **(primary.get("identifiers") or {})}
    out["identifiers"] = out_id

    # scalar fields to backfill
    for k in ("title", "subtitle", "publish_date", "nb_pages", "language", "description", "cover_image"):
        if not out.get(k) and secondary.get(k):
            out[k] = secondary[k]

    # list fields union
    for k in ("authors", "publishers", "genres"):
        a = out.get(k) or []
        b = secondary.get(k) or []
        seen = set()
        merged = []
        for x in a + b:
            if not x:
                continue
            key = str(x).strip().lower()
            if key and key not in seen:
                seen.add(key)
                merged.append(x)
        out[k] = merged

    # links merge
    links = {**(secondary.get("links") or {}), **(primary.get("links") or {})}
    if links:
        out["links"] = links

    # sources append (avoid dup)
    sources = (primary.get("sources") or []) + (secondary.get("sources") or [])
    uniq = []
    seen = set()
    for s in sources:
        if not isinstance(s, dict):
            continue
        key = (s.get("provider"), s.get("provider_key"))
        if key in seen:
            continue
        seen.add(key)
        uniq.append(s)
    out["sources"] = uniq

    return out