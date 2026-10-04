-- SQLite 전용 PRAGMA: 새 연결에서도 외래 키 검사를 활성화한다.
PRAGMA foreign_keys = ON;

-- Q01 | 기본 조회 | 2026년에 가입한 회원을 확인한다.
SELECT id, name, email, joined_at
FROM member
WHERE joined_at >= '2026-01-01'
ORDER BY joined_at, id;

-- Q02 | 기본 조회 | 프로그래밍 카테고리(id 4)의 도서를 확인한다.
SELECT id, title, author, category_id
FROM book
WHERE category_id = 4
ORDER BY id;

-- Q03 | 기본 조회 | 가장 최근의 대여 기록 5건을 확인한다.
SELECT id, member_id, book_id, rented_at, due_at, returned_at, rental_fee
FROM rental
ORDER BY rented_at DESC, id DESC
LIMIT 5;

-- Q04 | 기본 조회 | 아직 반납하지 않은 대여 기록을 최근순으로 확인한다.
SELECT id, member_id, book_id, rented_at, due_at, rental_fee
FROM rental
WHERE returned_at IS NULL
ORDER BY rented_at DESC, id DESC;

-- Q05 | 조인 | 도서명과 해당 카테고리명을 함께 확인한다.
SELECT b.id AS book_id, b.title, c.name AS category_name
FROM book AS b
INNER JOIN category AS c ON b.category_id = c.id
ORDER BY b.id;

-- Q06 | 조인 | 회원명, 도서명, 대여일을 포함한 대여 내역을 확인한다.
SELECT r.id AS rental_id, m.name AS member_name, b.title AS book_title, r.rented_at
FROM member AS m
INNER JOIN rental AS r ON r.member_id = m.id
INNER JOIN book AS b ON r.book_id = b.id
ORDER BY m.id, r.rented_at, r.id;

-- Q07 | 조인 | 대여 이력이 없는 회원까지 모든 회원의 대여 기록을 확인한다.
SELECT m.id AS member_id, m.name AS member_name, r.id AS rental_id, r.rented_at
FROM member AS m
LEFT JOIN rental AS r ON r.member_id = m.id
ORDER BY m.id, r.id;

-- Q08 | 조인 | 대여 이력이 없는 도서까지 모든 도서의 대여 기록을 확인한다.
SELECT b.id AS book_id, b.title, r.id AS rental_id, r.rented_at
FROM book AS b
LEFT JOIN rental AS r ON r.book_id = b.id
ORDER BY b.id, r.id;

-- Q09 | 집계 | 대여 이력이 없는 회원을 0건으로 포함하여 회원별 건수를 센다.
SELECT m.id AS member_id, m.name AS member_name, COUNT(r.id) AS rental_count
FROM member AS m
LEFT JOIN rental AS r ON r.member_id = m.id
GROUP BY m.id, m.name
ORDER BY rental_count DESC, m.id;

-- Q10 | 집계 | 카테고리별 대여료 합계를 확인한다.
SELECT c.id AS category_id, c.name AS category_name,
       COALESCE(SUM(r.rental_fee), 0) AS total_rental_fee
FROM category AS c
LEFT JOIN book AS b ON b.category_id = c.id
LEFT JOIN rental AS r ON r.book_id = b.id
GROUP BY c.id, c.name
ORDER BY c.id;

-- Q11 | 집계 | 카테고리별 대여료 평균을 확인한다.
SELECT c.id AS category_id, c.name AS category_name,
       AVG(r.rental_fee) AS average_rental_fee
FROM category AS c
LEFT JOIN book AS b ON b.category_id = c.id
LEFT JOIN rental AS r ON r.book_id = b.id
GROUP BY c.id, c.name
ORDER BY c.id;

-- Q12 | 집계 | 대여 이력이 없는 도서를 포함하여 도서별 대여 횟수 순위를 확인한다.
SELECT b.id AS book_id, b.title, COUNT(r.id) AS rental_count
FROM book AS b
LEFT JOIN rental AS r ON r.book_id = b.id
GROUP BY b.id, b.title
ORDER BY rental_count DESC, b.id;

-- Q13 | 서브쿼리 | 대여 기록이 한 건도 없는 회원을 찾는다.
SELECT m.id, m.name, m.email
FROM member AS m
WHERE NOT EXISTS (
    SELECT 1
    FROM rental AS r
    WHERE r.member_id = m.id
)
ORDER BY m.id;

-- Q14 | 데이터 수정 | 미반납 대여(id 23) 한 건을 반납 완료로 바꾼다.
-- 보조 확인: 변경 전 대상 행.
SELECT id, member_id, book_id, rented_at, due_at, returned_at
FROM rental
WHERE id = 23;

UPDATE rental
SET returned_at = '2026-10-03'
WHERE id = 23 AND returned_at IS NULL;

-- SQLite 전용 changes(): 직전 UPDATE로 변경된 행 수.
SELECT changes() AS updated_rows;

-- 보조 확인: 변경 후 대상 행.
SELECT id, member_id, book_id, rented_at, due_at, returned_at
FROM rental
WHERE id = 23;

-- Q15 | 데이터 삭제 | 샘플 대여(id 24) 한 건을 삭제한다.
-- 보조 확인: 삭제 전 대상 행.
SELECT id, member_id, book_id, rented_at, due_at, returned_at
FROM rental
WHERE id = 24;

DELETE FROM rental
WHERE id = 24;

-- SQLite 전용 changes(): 직전 DELETE로 삭제된 행 수.
SELECT changes() AS deleted_rows;

-- 보조 확인: 삭제 후 대상이 사라졌는지 확인한다.
SELECT id, member_id, book_id, rented_at, due_at, returned_at
FROM rental
WHERE id = 24;

-- Q16 | 인덱스 | 회원별 대여 조회에서 member_id 검색을 돕는 인덱스를 만든다.
-- rental.member_id로 회원의 대여 기록을 찾을 때 전체 테이블 탐색을 줄일 수 있다.
CREATE INDEX idx_rental_member_id ON rental (member_id);

-- SQLite 전용 PRAGMA: 실제로 생성된 rental 인덱스를 확인한다.
PRAGMA index_list('rental');
