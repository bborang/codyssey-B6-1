-- SQLite에서는 외래 키 검사가 연결별로 꺼져 있을 수 있다.
PRAGMA foreign_keys = ON;

-- 회원: 한 회원은 여러 대여 기록을 가질 수 있다.
CREATE TABLE member (
    id INTEGER PRIMARY KEY,
    name TEXT NOT NULL,
    email TEXT NOT NULL UNIQUE,
    joined_at TEXT NOT NULL
);

-- 카테고리: 한 카테고리에는 여러 도서가 속할 수 있다.
CREATE TABLE category (
    id INTEGER PRIMARY KEY,
    name TEXT NOT NULL UNIQUE
);

-- 도서: category_id는 category.id를 참조한다.
CREATE TABLE book (
    id INTEGER PRIMARY KEY,
    title TEXT NOT NULL,
    author TEXT,
    category_id INTEGER NOT NULL,
    FOREIGN KEY (category_id) REFERENCES category(id)
);

-- 대여 기록: 각각 한 회원과 한 도서를 참조한다.
-- 날짜는 YYYY-MM-DD 형식의 TEXT로 저장하므로 날짜 순서를 문자열로 비교할 수 있다.
CREATE TABLE rental (
    id INTEGER PRIMARY KEY,
    member_id INTEGER NOT NULL,
    book_id INTEGER NOT NULL,
    rented_at TEXT NOT NULL,
    due_at TEXT NOT NULL,
    returned_at TEXT,
    rental_fee INTEGER NOT NULL CHECK (rental_fee >= 0),
    FOREIGN KEY (member_id) REFERENCES member(id),
    FOREIGN KEY (book_id) REFERENCES book(id),
    CHECK (due_at >= rented_at),
    CHECK (returned_at IS NULL OR returned_at >= rented_at)
);
