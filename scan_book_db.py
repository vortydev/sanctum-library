import requests
import mariadb
from mariadb import Error
from datetime import datetime

# Database connection details
DB_CONFIG = {
    'host': 'localhost',          # Change if Docker is on a different network
    'port': 3306,                 # MariaDB container port
    'database': 'library_db',
    'user': 'library_user',
    'password': 'library_password'
}

def fetch_book_details(isbn):
    """Fetch book details from Open Library API."""
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
                "publish_date": format_publish_date(book_details.get("publish_date")),
                "nb_pages": book_details.get("number_of_pages"),
                "publisher": [publisher.get("name") for publisher in book_details.get("publishers", [])],
                "genres": extract_unique_genres([subject.get("name") for subject in book_details.get("subjects", [])]),
                "cover_image": f"https://covers.openlibrary.org/b/ISBN/{isbn}-L.jpg",
                "isbn": isbn
            }
    return None

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

from datetime import datetime

def format_publish_date(publish_date):
    """
    Format a publish_date string into a valid date.
    If the publish_date is incomplete or invalid, return None.

    Args:
        publish_date (str): The publish date string from the API.

    Returns:
        str: A valid date string in 'YYYY-MM-DD' format, or None.
    """
    if not publish_date:
        return None

    # Try to parse the date with increasing specificity
    formats = ["%Y-%m-%d", "%Y-%m", "%Y"]
    for date_format in formats:
        try:
            parsed_date = datetime.strptime(publish_date, date_format)
            return parsed_date.strftime("%Y-%m-%d")  # Return in 'YYYY-MM-DD' format
        except ValueError:
            continue

    # If no format works, return None
    return None

def connect_to_database():
    """Establish a connection to the MariaDB database."""
    try:
        connection = mariadb.connect(**DB_CONFIG)
        return connection
    except Error as e:
        print(f"Error connecting to MariaDB: {e}")
        return None

def check_if_book_exists(connection, isbn):
    """Check if a book with the given ISBN exists."""
    cursor = connection.cursor()
    query = "SELECT COUNT(*) FROM book WHERE isbn = %s"
    cursor.execute(query, (isbn,))
    result = cursor.fetchone()[0]
    cursor.close()
    return result > 0

def insert_data(connection, details):
    """Insert book, authors, genres, and publishers into the database."""
    cursor = connection.cursor()
    try:
        # Insert into book table
        book_query = """
        INSERT INTO book (title, publish_date, nb_pages, cover_image, isbn)
        VALUES (?, ?, ?, ?, ?)
        """
        cursor.execute(book_query, (details["title"], details["publish_date"], 
                                    details["nb_pages"], details["cover_image"], details["isbn"]))
        book_id = cursor.lastrowid
        print(f"Inserted book: {details['title']} (ISBN: {details['isbn']})")

        # Insert authors and associate with book
        for author in details["authors"]:
            cursor.execute("INSERT IGNORE INTO author (author_name) VALUES (?)", (author,))
            cursor.execute("SELECT prikey FROM author WHERE author_name = ?", (author,))
            author_id = cursor.fetchone()[0]
            cursor.execute("INSERT IGNORE INTO book_author (book_prikey, author_prikey) VALUES (?, ?)", (book_id, author_id))
            print(f"Associated author: {author} with book ID {book_id}")

        # Insert publishers and associate with book
        for publisher in details["publisher"]:
            cursor.execute("INSERT IGNORE INTO publisher (publisher_name) VALUES (?)", (publisher,))
            cursor.execute("SELECT prikey FROM publisher WHERE publisher_name = ?", (publisher,))
            publisher_id = cursor.fetchone()[0]
            cursor.execute("INSERT IGNORE INTO book_publisher (book_prikey, publisher_prikey) VALUES (?, ?)", (book_id, publisher_id))
            print(f"Associated publisher: {publisher} with book ID {book_id}")

        # Insert genres and associate with book
        for genre in details["genres"]:
            cursor.execute("INSERT IGNORE INTO genre (genre_name) VALUES (?)", (genre,))
            cursor.execute("SELECT prikey FROM genre WHERE genre_name = ?", (genre,))
            genre_id = cursor.fetchone()[0]
            cursor.execute("INSERT IGNORE INTO book_genre (book_prikey, genre_prikey) VALUES (?, ?)", (book_id, genre_id))
            print(f"Associated genre: {genre} with book ID {book_id}")

        connection.commit()
        print("Book and associated data inserted successfully!")
    except Error as e:
        print(f"Error inserting data: {e}")
        connection.rollback()
    finally:
        cursor.close()

def main():
    """Main function to fetch data and interact with the database."""
    print("Ready to scan books! (Press Ctrl+C to stop)")

    connection = None
    try:
        connection = connect_to_database()
        if not connection:
            return

        while True:  # Infinite loop to keep scanning books
            isbn = input("\nScan a book's barcode (or press Ctrl+C to exit): ").strip()

            if not isbn:
                print("No input detected. Please scan again.")
                continue

            details = fetch_book_details(isbn)
            if not details:
                print(f"Book details for ISBN {isbn} could not be fetched. Try another scan.")
                continue

            if check_if_book_exists(connection, isbn):
                print(f"Book with ISBN {isbn} already exists in the database.")
            else:
                insert_data(connection, details)
    except KeyboardInterrupt:
        print("\nExiting book scanner. Goodbye!")
    except Exception as e:
        print(f"An error occurred: {e}")
    finally:
        if connection:
            connection.close()
            print("Database connection closed.")
        else:
            print("No active database connection to close.")


if __name__ == "__main__":
    main()
