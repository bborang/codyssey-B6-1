"""schema.sql, seed.sql, queries.sql을 새 SQLite DB에서 실행하고 결과를 저장한다."""

import os
import re
import sqlite3
import tempfile
from pathlib import Path


ROOT = Path(__file__).resolve().parent
DB_PATH = ROOT / "practice.sqlite3"
RESULTS_DIR = ROOT / "results"
APP_ID = 46593  # 이 과제의 practice.sqlite3임을 확인하는 SQLite application_id


def read_sql(name):
    return (ROOT / name).read_text(encoding="utf-8")


def split_queries(source):
    """Q 번호 주석을 기준으로 queries.sql을 나눈다."""
    pattern = re.compile(r"^-- (Q\d{2}) \| ([^|]+) \| (.+)$", re.MULTILINE)
    matches = list(pattern.finditer(source))
    expected = [f"Q{number:02d}" for number in range(1, 17)]
    found = [match.group(1) for match in matches]
    if found != expected:
        raise ValueError(f"Q01~Q16 번호가 올바르지 않습니다: {found}")

    prefix = source[: matches[0].start()]
    sections = []
    for index, match in enumerate(matches):
        end = matches[index + 1].start() if index + 1 < len(matches) else len(source)
        sections.append((match.group(1), match.group(2).strip(),
                         match.group(3).strip(), source[match.end():end]))
    return prefix, sections


def split_statements(section):
    """SQLite가 완성된 문장으로 판단한 지점에서 SQL을 나눈다."""
    pending = ""
    for line in section.splitlines(keepends=True):
        pending += line
        if sqlite3.complete_statement(pending):
            yield pending.strip()
            pending = ""
    if pending.strip():
        raise ValueError(f"끝나지 않은 SQL 문장: {pending.strip()}")


def format_result(cursor):
    if cursor.description:
        columns = " | ".join(column[0] for column in cursor.description)
        rows = cursor.fetchall()
        lines = [f"컬럼: {columns}"]
        if rows:
            for row in rows:
                lines.append(" | ".join("NULL" if value is None else str(value)
                                        for value in row))
            lines.append(f"결과 {len(rows)}행")
        else:
            lines.append("결과 0행")
        return lines
    if cursor.rowcount >= 0:
        return [f"변경된 행 수: {cursor.rowcount}"]
    return ["실행 성공 (반환 행 없음)"]


def check_existing_db():
    if not DB_PATH.exists() and not DB_PATH.is_symlink():
        return
    if DB_PATH.is_symlink():
        raise RuntimeError(f"심볼릭 링크는 덮어쓰지 않습니다: {DB_PATH}")
    with sqlite3.connect(DB_PATH.as_uri() + "?mode=ro", uri=True) as previous:
        found_id = previous.execute("PRAGMA application_id").fetchone()[0]
    if found_id != APP_ID:
        raise RuntimeError(f"다른 DB 파일은 덮어쓰지 않습니다: {DB_PATH}")


def main():
    check_existing_db()
    prefix, sections = split_queries(read_sql("queries.sql"))

    # 완전히 새 DB에서 실행한 뒤, 성공했을 때만 이 과제의 DB 파일로 교체한다.
    with tempfile.NamedTemporaryFile(dir=ROOT, prefix=".practice-",
                                     suffix=".sqlite3", delete=False) as temp:
        temp_path = Path(temp.name)
    try:
        conn = sqlite3.connect(temp_path)
        try:
            conn.executescript(read_sql("schema.sql"))
            if conn.execute("PRAGMA foreign_keys").fetchone()[0] != 1:
                raise RuntimeError("외래 키 검사가 활성화되지 않았습니다")
            conn.executescript(read_sql("seed.sql"))
            conn.executescript(prefix)

            reports = {}
            for number, category, description, section in sections:
                lines = [f"{number} | {category} | {description}", ""]
                for statement in split_statements(section):
                    lines.extend(["실행 SQL:", statement, ""])
                    try:
                        cursor = conn.execute(statement)
                    except sqlite3.Error as error:
                        raise RuntimeError(f"{number} 실행 오류: {error}") from error
                    lines.extend(format_result(cursor))
                    lines.extend(["상태: 실행 성공", ""])
                reports[number] = "\n".join(lines).rstrip() + "\n"

            # SQLite 전용 application_id로 재실행 시 소유 DB인지 확인한다.
            conn.execute(f"PRAGMA application_id = {APP_ID}")
            conn.commit()
        finally:
            conn.close()

        os.replace(temp_path, DB_PATH)
        RESULTS_DIR.mkdir(exist_ok=True)
        for number, report in reports.items():
            (RESULTS_DIR / f"{number}.txt").write_text(report, encoding="utf-8")
    finally:
        temp_path.unlink(missing_ok=True)

    print(f"새 SQLite DB 생성: {DB_PATH.name}")
    print(f"실행 결과 저장: {RESULTS_DIR.name}/Q01.txt ~ Q16.txt")


if __name__ == "__main__":
    main()
