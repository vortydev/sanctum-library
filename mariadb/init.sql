-- Create the database if it doesn't exist and use it
CREATE DATABASE IF NOT EXISTS library_db;
USE library_db;

-- Grant all permissions to library_user
GRANT ALL PRIVILEGES ON library_db.* TO 'library_user'@'%' IDENTIFIED BY 'library_password';
FLUSH PRIVILEGES;

-- Table definitions
CREATE TABLE IF NOT EXISTS book (
    prikey INT AUTO_INCREMENT PRIMARY KEY,
    isbn VARCHAR(20) UNIQUE NOT NULL,
    title VARCHAR(255) NOT NULL,
    publish_date DATE,
    nb_pages INT,
    cover_image TEXT,
    creation_date DATETIME DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS author (
    prikey INT AUTO_INCREMENT PRIMARY KEY,
    author_name VARCHAR(255) NOT NULL UNIQUE,
    creation_date DATETIME DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS publisher (
    prikey INT AUTO_INCREMENT PRIMARY KEY,
    publisher_name VARCHAR(255) NOT NULL UNIQUE,
    creation_date DATETIME DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS genre (
    prikey INT AUTO_INCREMENT PRIMARY KEY,
    genre_name VARCHAR(255) NOT NULL UNIQUE,
    creation_date DATETIME DEFAULT CURRENT_TIMESTAMP
);
GO

CREATE TABLE IF NOT EXISTS book_author (
    book_prikey INT NOT NULL,
    author_prikey INT NOT NULL,
    creation_date DATETIME DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (book_prikey, author_prikey),
    FOREIGN KEY (book_prikey) REFERENCES book(prikey) ON DELETE CASCADE,
    FOREIGN KEY (author_prikey) REFERENCES author(prikey) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS book_publisher (
    book_prikey INT NOT NULL,
    publisher_prikey INT NOT NULL,
    creation_date DATETIME DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (book_prikey, publisher_prikey),
    FOREIGN KEY (book_prikey) REFERENCES book(prikey) ON DELETE CASCADE,
    FOREIGN KEY (publisher_prikey) REFERENCES publisher(prikey) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS book_genre (
    book_prikey INT NOT NULL,
    genre_prikey INT NOT NULL,
    creation_date DATETIME DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (book_prikey, genre_prikey),
    FOREIGN KEY (book_prikey) REFERENCES book(prikey) ON DELETE CASCADE,
    FOREIGN KEY (genre_prikey) REFERENCES genre(prikey) ON DELETE CASCADE
);
