# scan_books.py
from scanner import detect_scanner, listen_scanner, fetch_book_with_fallback
from stores.book_store import BookStore

def main():
    status = detect_scanner()
    print(status.message)
    if status.candidates:
        for c in status.candidates[:8]:
            print(f"  - {c}")

    store = BookStore.default()
    print(f"Data dir: {store.data_root}")
    print("Ready. Ctrl+C to exit.")

    for kind, value in listen_scanner():
        if kind == "asin":
            print(
                f"ASIN detected ({value}). "
                "No supported provider yet. Skipping."
            )
            continue

        # ISBN path only
        book = fetch_book_with_fallback(value)
        if not book:
            continue

        saved = store.upsert_book(book)
        print(f"Saved: {saved.get('title')} (ISBN {value})")


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\nUser aborted program! Exiting.")
        exit()
    except Exception as e:
        print(f"\nAn error occured: {e}")
        exit(1)
    