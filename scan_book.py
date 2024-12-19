import requests

def fetch_book_details(isbn):
    """
    Fetch book details using the Open Library Books API.
    :param isbn: ISBN number of the book as a string
    """
    url = f"https://openlibrary.org/api/books"
    params = {"bibkeys": f"ISBN:{isbn}", "format": "json", "jscmd": "data"}
    response = requests.get(url, params=params)
    
    if response.status_code == 200:
        data = response.json()
        if f"ISBN:{isbn}" in data:
            book_details = data[f"ISBN:{isbn}"]
            return {
                "title": book_details.get("title"),
                "authors": [author.get("name") for author in book_details.get("authors", [])],
                "publish_date": book_details.get("publish_date"),
                "pages": book_details.get("number_of_pages"),
                "publisher": [publisher.get("name") for publisher in book_details.get("publishers", [])],
                "genres": extract_unique_genres([subject.get("name") for subject in book_details.get("subjects", [])]),
                "cover_image": f"https://covers.openlibrary.org/b/ISBN/{isbn}-L.jpg",
            }
        else:
            return {"error": "Book not found"}
    else:
        return {"error": f"Failed to fetch data: {response.status_code}"}
    
def extract_unique_genres(genres: list[str]) -> list[str]:
    """
    Ensure only unique, normalized genres are included.
    :param genres: List of genre names
    :return: List of unique genre names
    """
    seen = set()
    unique_genres = []
    for genre in genres:
        # Split by comma, normalize, and process each sub-genre
        for sub_genre in genre.split(","):
            normalized_genre = sub_genre.lower().strip()
            if normalized_genre and normalized_genre not in seen:
                seen.add(normalized_genre)
                unique_genres.append(normalized_genre.capitalize())  # Append the normalized genre
    return sorted(unique_genres)

def listen_to_barcode_scanner():
    """
    Continuously listen for barcodes from the scanner.
    """
    print("Listening for barcodes (press Ctrl+C to exit)...")
    try:
        while True:
            # Simulate barcode scanner input (e.g., from keyboard input)
            isbn = input("Scan a book's barcode: ").strip()
            if isbn.isdigit() and len(isbn) in [10, 13]:  # Validate ISBN length
                book_details = fetch_book_details(isbn)
                print("\nBook Details:")
                for key, value in book_details.items():
                    if isinstance(value, list):
                        print(f"{key.capitalize()}: {', '.join(value)}")
                    else:
                        print(f"{key.capitalize()}: {value}")
                print("\n")
            else:
                print("Invalid ISBN. Please try again.")
    except KeyboardInterrupt:
        print("\nExiting barcode scanner listener.")

if __name__ == "__main__":
    listen_to_barcode_scanner()
