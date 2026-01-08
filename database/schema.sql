CREATE DATABASE IF NOT EXISTS noteshelf;
USE noteshelf;

CREATE TABLE users (
    id INT AUTO_INCREMENT PRIMARY KEY,
    name VARCHAR(100),
    email VARCHAR(100) UNIQUE,
    password VARCHAR(255)
);

CREATE TABLE admins (
    id INT AUTO_INCREMENT PRIMARY KEY,
    username VARCHAR(50) UNIQUE,
    password VARCHAR(255)
);

CREATE TABLE subjects (
    id INT AUTO_INCREMENT PRIMARY KEY,
    subject_name VARCHAR(150),
    description TEXT
);

CREATE TABLE pdfs (
    id INT AUTO_INCREMENT PRIMARY KEY,
    subject_id INT,
    title VARCHAR(200),
    price INT DEFAULT 0,
    file_path VARCHAR(255),
    downloads INT DEFAULT 0,
    FOREIGN KEY (subject_id) REFERENCES subjects(id)
);
