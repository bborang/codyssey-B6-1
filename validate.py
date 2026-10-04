"""과제 요구사항을 실제 SQLite DB와 SQL 결과 파일로 검증한다."""

import re
import sqlite3
import sys
from collections import Counter

sys.dont_write_bytecode = True
from run import APP_ID, DB_PATH, RESULTS_DIR, ROOT, read_sql, split_queries


TABLES = ("member", "category", "book", "rental")
EXPECTED_FKS = {
    ("book", "category_id", "category", "id"),
    ("rental", "member_id", "member", "id"),
    ("rental", "book_id", "book", "id"),
}
EXPECTED_CATEGORIES = {
    "기본 조회": 4,
    "조인": 4,
    "집계": 4,
    "서브쿼리": 1,
    "데이터 수정": 1,
    "데이터 삭제": 1,
    "인덱스": 1,
}


def counts(conn):
    return {table: conn.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0]
            for table in TABLES}


def rejected(conn, sql):
    try:
        conn.execute(sql)
    except sqlite3.IntegrityError:
        return True
    return False


def main():
    lines = ["B6-1 도서 대여 관리 실제 검증 결과",
             f"대상 DB: {DB_PATH.name}",
             f"SQLite 라이브러리 버전: {sqlite3.sqlite_version}", ""]
    failed = []

    def check(label, passed, detail):
        lines.append(f"[{'PASS' if passed else 'FAIL'}] {label}: {detail}")
        if not passed:
            failed.append(label)

    # 시드 입력 직후 상태를 새 메모리 DB에서 확인한다.
    with sqlite3.connect(":memory:") as fresh:
        fresh.executescript(read_sql("schema.sql"))
        fresh.executescript(read_sql("seed.sql"))
        seed_counts = counts(fresh)
        check("시드 직후 행 수", all(n >= 10 for n in seed_counts.values()),
              str(seed_counts))
        check("시드 연결 FK 활성화", fresh.execute("PRAGMA foreign_keys").fetchone()[0] == 1,
              f"PRAGMA foreign_keys={fresh.execute('PRAGMA foreign_keys').fetchone()[0]}")
        check("시드 FK 위반", not fresh.execute("PRAGMA foreign_key_check").fetchall(),
              "위반 0건" if not fresh.execute("PRAGMA foreign_key_check").fetchall() else "위반 발견")

        no_member = fresh.execute("""SELECT COUNT(*) FROM member AS m WHERE NOT EXISTS
                                  (SELECT 1 FROM rental AS r WHERE r.member_id = m.id)""").fetchone()[0]
        no_book = fresh.execute("""SELECT COUNT(*) FROM book AS b WHERE NOT EXISTS
                                (SELECT 1 FROM rental AS r WHERE r.book_id = b.id)""").fetchone()[0]
        open_count = fresh.execute("SELECT COUNT(*) FROM rental WHERE returned_at IS NULL").fetchone()[0]
        closed_count = fresh.execute("SELECT COUNT(*) FROM rental WHERE returned_at IS NOT NULL").fetchone()[0]
        check("샘플 데이터 구성", no_member >= 1 and no_book >= 1 and open_count > 0 and closed_count > 0,
              f"대여 없는 회원 {no_member}명, 도서 {no_book}권, 미반납 {open_count}건, 반납 {closed_count}건")

        multiple_members = fresh.execute("""SELECT COUNT(*) FROM
                (SELECT member_id FROM rental GROUP BY member_id HAVING COUNT(*) > 1)""").fetchone()[0]
        multiple_books = fresh.execute("""SELECT COUNT(*) FROM
                (SELECT book_id FROM rental GROUP BY book_id HAVING COUNT(*) > 1)""").fetchone()[0]
        check("여러 시점의 대여", multiple_members > 0 and multiple_books > 0,
              f"여러 건 대여한 회원 {multiple_members}명, 여러 번 대여된 도서 {multiple_books}권")

        invalid_fk = rejected(fresh, "INSERT INTO book (title, category_id) VALUES ('검증용', 999)")
        invalid_null = rejected(fresh, "INSERT INTO member (name, email, joined_at) VALUES (NULL, 'check@example.com', '2026-10-04')")
        invalid_unique = rejected(fresh, "INSERT INTO member (name, email, joined_at) VALUES ('검증용', 'member01@example.com', '2026-10-04')")
        check("제약조건 실제 동작", invalid_fk and invalid_null and invalid_unique,
              f"없는 FK 거부={invalid_fk}, NOT NULL 거부={invalid_null}, UNIQUE 거부={invalid_unique}")

    # Q01~Q16 실행 후 저장된 DB를 읽기 전용 연결로 확인한다.
    with sqlite3.connect(DB_PATH.as_uri() + "?mode=ro", uri=True) as conn:
        conn.execute("PRAGMA foreign_keys = ON")
        app_id = conn.execute("PRAGMA application_id").fetchone()[0]
        check("과제 DB 식별", app_id == APP_ID, f"application_id={app_id}")

        tables = {row[0] for row in conn.execute("""SELECT name FROM sqlite_master
                    WHERE type = 'table' AND name NOT LIKE 'sqlite_%'""")}
        check("테이블 4개", tables == set(TABLES), f"실제 테이블={sorted(tables)}")

        pk = {table: [row[1] for row in conn.execute(f"PRAGMA table_info('{table}')")
                      if row[5] > 0] for table in TABLES}
        check("각 테이블의 PK", all(columns == ["id"] for columns in pk.values()), str(pk))

        fks = {(table, row[3], row[2], row[4]) for table in TABLES
               for row in conn.execute(f"PRAGMA foreign_key_list('{table}')")}
        check("FK 3개와 1:N 관계", fks == EXPECTED_FKS,
              ", ".join(f"{child}.{column} -> {parent}.{target}"
                        for child, column, parent, target in sorted(fks)))

        not_null = {(table, row[1]) for table in TABLES
                    for row in conn.execute(f"PRAGMA table_info('{table}')") if row[3] == 1}
        required_not_null = {("member", "name"), ("member", "email"),
                             ("category", "name"), ("book", "title")}
        check("NOT NULL 제약", required_not_null <= not_null,
              ", ".join(f"{table}.{column}" for table, column in sorted(required_not_null)))

        unique = set()
        for table in TABLES:
            for index in conn.execute(f"PRAGMA index_list('{table}')"):
                if index[2] == 1:
                    columns = [row[2] for row in conn.execute(f"PRAGMA index_info('{index[1]}')")]
                    if len(columns) == 1:
                        unique.add((table, columns[0]))
        required_unique = {("member", "email"), ("category", "name")}
        check("UNIQUE 제약", required_unique <= unique,
              ", ".join(f"{table}.{column}" for table, column in sorted(unique)))

        fk_enabled = conn.execute("PRAGMA foreign_keys").fetchone()[0]
        violations = conn.execute("PRAGMA foreign_key_check").fetchall()
        check("실행 DB FK 활성화와 무결성", fk_enabled == 1 and len(violations) == 0,
              f"foreign_keys={fk_enabled}, 위반={len(violations)}건")

        after_counts = counts(conn)
        check("수정·삭제 후 행 수", all(n >= 10 for n in after_counts.values()),
              str(after_counts))

        bad_dates = conn.execute("""SELECT COUNT(*) FROM rental
                WHERE due_at < rented_at OR returned_at < rented_at""").fetchone()[0]
        check("대여 날짜 순서", bad_dates == 0, f"모순 {bad_dates}건")

        q14_value = conn.execute("SELECT returned_at FROM rental WHERE id = 23").fetchone()
        q15_count = conn.execute("SELECT COUNT(*) FROM rental WHERE id = 24").fetchone()[0]
        q16_indexes = [row[1] for row in conn.execute("PRAGMA index_list('rental')")]
        index_cols = [row[2] for row in conn.execute("PRAGMA index_info('idx_rental_member_id')")]

    source = read_sql("queries.sql")
    _, sections = split_queries(source)
    categories = Counter(category for _, category, _, _ in sections)
    check("Q01~Q16 범주별 개수", categories == EXPECTED_CATEGORIES, str(dict(categories)))

    sql_only = re.sub(r"--[^\n]*", "", source).upper()
    inner = len(re.findall(r"\bINNER\s+JOIN\b", sql_only))
    left = len(re.findall(r"\bLEFT\s+JOIN\b", sql_only))
    check("조인 종류", inner >= 2 and left >= 1,
          f"INNER JOIN {inner}개, LEFT JOIN {left}개")
    required_sql = ["WHERE", "ORDER BY", "LIMIT", "COUNT(", "SUM(",
                    "AVG(", "GROUP BY", "NOT EXISTS", "UPDATE", "DELETE", "CREATE INDEX"]
    missing_sql = [keyword for keyword in required_sql if keyword not in sql_only]
    check("필수 SQL 구문", not missing_sql,
          "모두 사용" if not missing_sql else f"누락={missing_sql}")

    files = [RESULTS_DIR / f"Q{number:02d}.txt" for number in range(1, 17)]
    missing_files = [path.name for path in files if not path.is_file()]
    check("Q01~Q16 결과 파일", not missing_files,
          "16개 존재" if not missing_files else f"누락={missing_files}")
    if not missing_files:
        valid_reports = all(path.read_text(encoding="utf-8").startswith(path.stem + " |")
                            and "실행 SQL:" in path.read_text(encoding="utf-8")
                            and "상태: 실행 성공" in path.read_text(encoding="utf-8")
                            for path in files)
        check("결과 파일 내용", valid_reports, "번호·실행 SQL·성공 상태 확인")

        q14 = files[13].read_text(encoding="utf-8")
        q15 = files[14].read_text(encoding="utf-8")
        check("Q14 한 건 수정", "변경된 행 수: 1" in q14 and "updated_rows\n1" in q14
              and q14_value == ("2026-10-03",), f"변경된 행 수=1, id 23 returned_at={q14_value[0] if q14_value else None}")
        check("Q15 한 건 삭제", "변경된 행 수: 1" in q15 and "deleted_rows\n1" in q15
              and "결과 0행" in q15 and q15_count == 0,
              f"삭제된 행 수=1, id 24 남은 행={q15_count}")
    else:
        check("Q14 한 건 수정", False, "결과 파일 누락")
        check("Q15 한 건 삭제", False, "결과 파일 누락")
    check("Q16 인덱스 생성", "idx_rental_member_id" in q16_indexes
          and index_cols == ["member_id"],
          f"인덱스={q16_indexes}, 컬럼={index_cols}")

    lines.extend(["", f"최종 결과: {'모든 항목 통과' if not failed else f'{len(failed)}개 항목 실패'}"])
    RESULTS_DIR.mkdir(exist_ok=True)
    output = RESULTS_DIR / "validation.txt"
    output.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(f"검증 결과 저장: {output.relative_to(ROOT)}")
    print(lines[-1])
    if failed:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
