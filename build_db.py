"""Extract all commits from claudes-c-compiler repo into a DuckDB database."""

import subprocess
import re
import duckdb

REPO_PATH = r"D:\projects\ccc\repo"
DB_PATH = r"D:\projects\ccc\commits.db"

COMMIT_DELIMITER = "---COMMIT_DELIM---"
FIELD_DELIMITER = "---FIELD_DELIM---"

GIT_FORMAT = FIELD_DELIMITER.join(["%H", "%an", "%aI", "%s", "%b"]) + COMMIT_DELIMITER


def create_tables(con: duckdb.DuckDBPyConnection) -> None:
    con.execute("""
        CREATE TABLE IF NOT EXISTS commits (
            id INTEGER PRIMARY KEY,
            hash TEXT UNIQUE NOT NULL,
            short_hash TEXT NOT NULL,
            author TEXT NOT NULL,
            date TEXT NOT NULL,
            subject TEXT NOT NULL,
            body TEXT,
            files_changed INTEGER DEFAULT 0,
            insertions INTEGER DEFAULT 0,
            deletions INTEGER DEFAULT 0
        )
    """)
    con.execute("""
        CREATE TABLE IF NOT EXISTS commit_files (
            id INTEGER PRIMARY KEY,
            commit_hash TEXT NOT NULL,
            file_path TEXT NOT NULL,
            insertions INTEGER DEFAULT 0,
            deletions INTEGER DEFAULT 0,
            FOREIGN KEY (commit_hash) REFERENCES commits(hash)
        )
    """)
    con.execute("CREATE INDEX IF NOT EXISTS idx_commits_date ON commits(date)")
    con.execute("CREATE INDEX IF NOT EXISTS idx_commits_subject ON commits(subject)")
    con.execute("CREATE INDEX IF NOT EXISTS idx_commit_files_hash ON commit_files(commit_hash)")
    con.execute("CREATE INDEX IF NOT EXISTS idx_commit_files_path ON commit_files(file_path)")


def run_git_log() -> str:
    result = subprocess.run(
        [
            "git", "-C", REPO_PATH, "log",
            f"--format={GIT_FORMAT}",
            "--reverse", "--numstat",
        ],
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
    )
    if result.returncode != 0:
        raise RuntimeError(f"git log failed: {result.stderr}")
    return result.stdout


def parse_commits(raw: str) -> list[dict]:
    """Parse the git log output into a list of commit dicts.

    The format is:
        hash---FIELD_DELIM---author---FIELD_DELIM---date---FIELD_DELIM---subject---FIELD_DELIM---body---COMMIT_DELIM---
        <numstat lines>
        <blank line>
        hash---FIELD_DELIM---...

    Numstat lines are: insertions\tdeletions\tfilepath
    Binary files show as: -\t-\tfilepath
    """
    commits = []
    # Split on the commit delimiter to get blocks
    blocks = raw.split(COMMIT_DELIMITER)

    for block in blocks:
        block = block.strip()
        if not block:
            continue

        # The block contains:
        # 1. Possibly numstat lines from the PREVIOUS commit (at the top)
        # 2. The commit metadata fields
        #
        # Since numstat comes AFTER the delimiter of its own commit,
        # we need a different approach: find the field delimiter pattern
        # to locate the metadata, and everything before it is numstat from prev commit.

        # Split into lines
        lines = block.split("\n")

        # Find the line containing the field delimiter (that's where metadata starts)
        metadata_line_idx = None
        for i, line in enumerate(lines):
            if FIELD_DELIMITER in line:
                metadata_line_idx = i
                break

        if metadata_line_idx is None:
            # This block has only numstat lines (belongs to the last commit)
            if commits:
                _parse_numstat_lines(lines, commits[-1])
            continue

        # Lines before the metadata line are numstat from the previous commit
        if metadata_line_idx > 0 and commits:
            numstat_lines = lines[:metadata_line_idx]
            _parse_numstat_lines(numstat_lines, commits[-1])

        # Parse the metadata - rejoin from the metadata line onward
        # The metadata is all on one line (fields joined by FIELD_DELIM)
        metadata_text = lines[metadata_line_idx]
        parts = metadata_text.split(FIELD_DELIMITER)

        if len(parts) < 4:
            continue

        commit_hash = parts[0].strip()
        author = parts[1].strip()
        date = parts[2].strip()
        subject = parts[3].strip()
        body = parts[4].strip() if len(parts) > 4 else ""

        commit = {
            "hash": commit_hash,
            "short_hash": commit_hash[:7],
            "author": author,
            "date": date,
            "subject": subject,
            "body": body,
            "files": [],
            "files_changed": 0,
            "insertions": 0,
            "deletions": 0,
        }
        commits.append(commit)

        # Lines after the metadata line are numstat for THIS commit
        if metadata_line_idx + 1 < len(lines):
            numstat_lines = lines[metadata_line_idx + 1:]
            _parse_numstat_lines(numstat_lines, commit)

    return commits


NUMSTAT_RE = re.compile(r"^(\d+|-)\t(\d+|-)\t(.+)$")


def _parse_numstat_lines(lines: list[str], commit: dict) -> None:
    for line in lines:
        line = line.strip()
        m = NUMSTAT_RE.match(line)
        if not m:
            continue
        ins_str, del_str, filepath = m.groups()
        ins = int(ins_str) if ins_str != "-" else 0
        dels = int(del_str) if del_str != "-" else 0
        commit["files"].append({
            "file_path": filepath,
            "insertions": ins,
            "deletions": dels,
        })
        commit["files_changed"] += 1
        commit["insertions"] += ins
        commit["deletions"] += dels


def insert_commits(con: duckdb.DuckDBPyConnection, commits: list[dict]) -> None:
    batch_size = 500
    commit_id = 0
    file_id = 0

    for i in range(0, len(commits), batch_size):
        batch = commits[i:i + batch_size]
        con.begin()

        for c in batch:
            commit_id += 1
            con.execute(
                """INSERT INTO commits (id, hash, short_hash, author, date, subject, body,
                   files_changed, insertions, deletions)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                [commit_id, c["hash"], c["short_hash"], c["author"], c["date"],
                 c["subject"], c["body"], c["files_changed"], c["insertions"], c["deletions"]],
            )
            for f in c["files"]:
                file_id += 1
                con.execute(
                    """INSERT INTO commit_files (id, commit_hash, file_path, insertions, deletions)
                       VALUES (?, ?, ?, ?, ?)""",
                    [file_id, c["hash"], f["file_path"], f["insertions"], f["deletions"]],
                )

        con.commit()
        print(f"  Inserted commits {i + 1}–{min(i + batch_size, len(commits))} of {len(commits)}")


def main() -> None:
    print(f"Extracting commits from {REPO_PATH}...")
    raw = run_git_log()
    print(f"  git log output: {len(raw):,} chars")

    print("Parsing commits...")
    commits = parse_commits(raw)
    print(f"  Parsed {len(commits)} commits")

    print(f"Loading into {DB_PATH}...")
    con = duckdb.connect(DB_PATH)
    create_tables(con)
    insert_commits(con, commits)

    # Summary
    total = con.execute("SELECT COUNT(*) FROM commits").fetchone()[0]
    total_files = con.execute("SELECT COUNT(*) FROM commit_files").fetchone()[0]
    total_ins = con.execute("SELECT SUM(insertions) FROM commits").fetchone()[0]
    total_del = con.execute("SELECT SUM(deletions) FROM commits").fetchone()[0]

    print(f"\nDone.")
    print(f"  Commits:       {total:,}")
    print(f"  File entries:  {total_files:,}")
    print(f"  Insertions:    {total_ins:,}")
    print(f"  Deletions:     {total_del:,}")

    # Spot checks
    print("\nFirst 3 commits:")
    rows = con.execute("SELECT id, short_hash, date, subject FROM commits ORDER BY id LIMIT 3").fetchall()
    for r in rows:
        print(f"  #{r[0]} {r[1]} {r[2]} — {r[3]}")

    print("\nLast 3 commits:")
    rows = con.execute("SELECT id, short_hash, date, subject FROM commits ORDER BY id DESC LIMIT 3").fetchall()
    for r in rows:
        print(f"  #{r[0]} {r[1]} {r[2]} — {r[3]}")

    con.close()


if __name__ == "__main__":
    main()
