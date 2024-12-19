# Use the official MariaDB image
FROM mariadb:latest

# Set the working directory inside the container
WORKDIR /mariadb

# Copy the initialization script to the container's init directory
COPY init.sql /docker-entrypoint-initdb.d/init.sql

# Expose the MariaDB port
EXPOSE 3306
