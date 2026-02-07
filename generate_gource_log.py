"""Generate a Gource custom log from commits.db with action-based coloring."""

import duckdb
from datetime import datetime, timezone

DB_PATH = "D:/projects/ccc/commits.db"
OUTPUT_PATH = "D:/projects/ccc/gource_custom.log"

# Action-based colors: green=create, red=delete, neutral=modify
COLOR_ADD = "00FF00"
COLOR_DELETE = "FF3333"
COLOR_MODIFY = "CCCCFF"


def iso_to_unix(iso_str: str) -> int:
    dt = datetime.fromisoformat(iso_str.replace("Z", "+00:00"))
    return int(dt.timestamp())


def main() -> None:
    con = duckdb.connect(DB_PATH, read_only=True)

    rows = con.sql("""
        SELECT c.date, c.author, cf.file_path, cf.insertions, cf.deletions
        FROM commits c
        JOIN commit_files cf ON c.hash = cf.commit_hash
        ORDER BY c.date ASC, c.id ASC, cf.id ASC
    """).fetchall()

    # Track which files have been seen to determine A vs M vs D
    seen_files: set[str] = set()
    lines: list[str] = []

    for date_str, author, file_path, insertions, deletions in rows:
        timestamp = iso_to_unix(date_str)

        if deletions > 0 and insertions == 0:
            action = "D"
            color = COLOR_DELETE
            seen_files.discard(file_path)
        elif file_path not in seen_files:
            action = "A"
            color = COLOR_ADD
            seen_files.add(file_path)
        else:
            action = "M"
            color = COLOR_MODIFY

        lines.append(f"{timestamp}|{author}|{action}|/{file_path}|{color}")

    con.close()

    with open(OUTPUT_PATH, "w", encoding="utf-8") as f:
        f.write("\n".join(lines))
        f.write("\n")

    print(f"Wrote {len(lines)} entries to {OUTPUT_PATH}")
    print(f"First: {lines[0]}")
    print(f"Last:  {lines[-1]}")

    # Stats
    actions = {"A": 0, "M": 0, "D": 0}
    for line in lines:
        actions[line.split("|")[2]] += 1
    print(f"Actions: {actions}")


if __name__ == "__main__":
    main()
