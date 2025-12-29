# scanner.py
from __future__ import annotations
import re
import requests
import subprocess
import platform
from dataclasses import dataclass
from datetime import datetime
from typing import Any
from pathlib import Path

# Variables
_SCANNER_HINTS = ("scanner", "barcode", "symbol", "zebra", "honeywell", "datalogic")
OPENLIB_BOOKS_API = "https://openlibrary.org/api/books"
GOOGLE_BOOKS_API = "https://www.googleapis.com/books/v1/volumes"

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
    if key not in data:
        return None

    b = data[key]
    return {
        "type": "book",
        "identifiers": {"isbn": isbn},
        "title": b.get("title"),
        "authors": [a.get("name") for a in b.get("authors", []) if a.get("name")],
        "publish_date": format_publish_date(b.get("publish_date")),
        "nb_pages": b.get("number_of_pages"),
        "publishers": [p.get("name") for p in b.get("publishers", []) if p.get("name")],
        "genres": extract_unique_genres([s.get("name") for s in b.get("subjects", []) if s.get("name")]),
        "cover_image": f"https://covers.openlibrary.org/b/ISBN/{isbn}-L.jpg",
        "sources": [{"provider": "openlibrary", "provider_key": key}],
    }


def fetch_book_with_fallback(isbn: str) -> dict[str, Any] | None:
    book = fetch_openlibrary_book(isbn)
    if book:
        return book

    print(f"No Open Library result for ISBN {isbn}, trying Google Books...")
    book = fetch_google_books(isbn)
    if book:
        return book

    print(f"No provider found data for ISBN {isbn}.")
    return None


def fetch_google_books(isbn: str, timeout_s: int = 10) -> dict[str, Any] | None:
    params = {"q": f"isbn:{isbn}"}

    try:
        r = requests.get(GOOGLE_BOOKS_API, params=params, timeout=timeout_s)
        r.raise_for_status()
    except requests.RequestException as e:
        print(f"Google Books request failed: {e}")
        return None

    data = r.json()
    items = data.get("items")
    if not items:
        return None

    v = items[0]["volumeInfo"]

    return {
        "type": "book",
        "identifiers": {"isbn": isbn},
        "title": v.get("title"),
        "authors": v.get("authors", []),
        "publish_date": format_publish_date(v.get("publishedDate")),
        "nb_pages": v.get("pageCount"),
        "publishers": [v.get("publisher")] if v.get("publisher") else [],
        "genres": extract_unique_genres(v.get("categories", [])),
        "cover_image": (
            v.get("imageLinks", {}).get("thumbnail")
            or v.get("imageLinks", {}).get("smallThumbnail")
        ),
        "sources": [
            {
                "provider": "google_books",
                "provider_key": items[0].get("id"),
            }
        ],
    }


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


@dataclass(frozen=True)
class ScannerStatus:
    ok: bool
    message: str
    candidates: list[str]


def detect_scanner() -> ScannerStatus:
    sysname = platform.system().lower()

    if sysname == "linux":
        candidates: list[str] = []

        by_id = Path("/dev/input/by-id")
        if by_id.exists():
            for p in by_id.iterdir():
                name = p.name.lower()
                if any(h in name for h in _SCANNER_HINTS):
                    candidates.append(str(p))

        try:
            out = subprocess.check_output(["lsusb"], text=True, stderr=subprocess.DEVNULL)
            for line in out.splitlines():
                low = line.lower()
                if any(h in low for h in _SCANNER_HINTS):
                    candidates.append(line.strip())
        except Exception:
            pass

        uniq = sorted(set(candidates))
        if uniq:
            return ScannerStatus(True, "Scanner-like device detected (heuristic).", uniq)

        return ScannerStatus(
            False,
            "No obvious scanner detected. Note: HID keyboard-style scanners often can't be reliably detected.",
            [],
        )

    return ScannerStatus(
        False,
        f"Scanner detection not implemented for {platform.system()} (common HID scanners still work).",
        [],
    )
