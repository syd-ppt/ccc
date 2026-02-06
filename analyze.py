"""Commit-level analysis of claudes-c-compiler evolution from DuckDB data."""

import re
import duckdb

DB_PATH = r"D:\projects\ccc\commits.db"
REPORT_PATH = r"D:\projects\ccc\evolution_report.txt"

# Phase detection keywords mapped to phase names
PHASE_KEYWORDS = [
    ("Scaffolding", r"scaffold|initial|setup|skeleton|stub"),
    ("Lexer", r"\blex\b|token|lexer|tokeniz"),
    ("Parser", r"\bpars\b|parser|ast\b|parse[rd]|parsing|recursive.descent|precedence"),
    ("Preprocessor", r"preprocess|#include|#define|#ifdef|macro|cpp\b"),
    ("Type System / Sema", r"\btype\b|sema|semantic|type.check|type.system|typedef|sizeof|alignof"),
    ("IR / SSA", r"\bir\b|\bssa\b|lowering|mem2reg|alloca|basic.block|phi\b|cfg\b"),
    ("Optimization", r"optim|pass\b|fold|dce|dead.code|inline|peephole|regalloc|register.alloc"),
    ("Codegen (x86)", r"x86|x86.64|i686|x86_64"),
    ("Codegen (ARM/AArch64)", r"aarch64|arm\b|aarch"),
    ("Codegen (RISC-V)", r"riscv|risc.v"),
    ("Assembler / ELF", r"assembl|elf\b|object.file|\.o\b|machine.code|encod"),
    ("Linker", r"\blink\b|linker|reloc|symbol.resol"),
    ("DWARF / Debug", r"dwarf|debug.info|debug|\.debug_"),
    ("Testing / Fixes", r"\bfix\b|\bbug\b|\btest\b|regress|failing|pass rate|passing"),
    ("Lock (task mgmt)", r"^Lock:"),
    ("Real-world compilation", r"postgres|postgresql|sqlite|ffmpeg|linux|kernel|duckdb|curl|nginx|redis|git\b|lua\b|tcc\b|zlib"),
]


def connect() -> duckdb.DuckDBPyConnection:
    return duckdb.connect(DB_PATH, read_only=True)


def section(title: str) -> str:
    return f"\n{'=' * 70}\n{title}\n{'=' * 70}\n"


def subsection(title: str) -> str:
    return f"\n--- {title} ---\n"


def timeline_overview(con: duckdb.DuckDBPyConnection) -> str:
    out = section("TIMELINE OVERVIEW")

    # Project span
    row = con.execute("""
        SELECT MIN(date), MAX(date), COUNT(*),
               SUM(insertions), SUM(deletions),
               SUM(files_changed)
        FROM commits
    """).fetchone()
    start, end, total, ins, dels, files = row
    out += f"  First commit:   {start}\n"
    out += f"  Last commit:    {end}\n"
    out += f"  Total commits:  {total:,}\n"
    out += f"  Total files:    {files:,} modifications\n"
    out += f"  Insertions:     {ins:,}\n"
    out += f"  Deletions:      {dels:,}\n"
    out += f"  Net lines:      {ins - dels:,}\n"

    # Commits per day
    out += subsection("Commits per Day")
    rows = con.execute("""
        SELECT date::DATE as day, COUNT(*) as n,
               SUM(insertions) as ins, SUM(deletions) as del
        FROM commits GROUP BY day ORDER BY day
    """).fetchall()
    for day, n, ins, del_ in rows:
        bar = "#" * min(n // 5, 60)
        out += f"  {day}  {n:4d} commits  +{ins:>6,} -{del_:>6,}  {bar}\n"

    # Commits per hour of day
    out += subsection("Commits per Hour of Day (UTC)")
    rows = con.execute("""
        SELECT EXTRACT(HOUR FROM date::TIMESTAMP) as hour, COUNT(*) as n
        FROM commits GROUP BY hour ORDER BY hour
    """).fetchall()
    for hour, n in rows:
        bar = "#" * (n // 5)
        out += f"  {int(hour):02d}:00  {n:4d}  {bar}\n"

    # Cumulative lines over time (sampled every 100 commits)
    out += subsection("Cumulative Net Lines (every 100 commits)")
    rows = con.execute("""
        SELECT id, date,
               SUM(insertions) OVER (ORDER BY id) as cum_ins,
               SUM(deletions) OVER (ORDER BY id) as cum_del
        FROM commits
        QUALIFY id % 100 = 0 OR id = (SELECT MAX(id) FROM commits)
        ORDER BY id
    """).fetchall()
    for cid, date, cum_ins, cum_del in rows:
        net = cum_ins - cum_del
        out += f"  #{cid:>4d}  {date[:16]}  net {net:>7,} lines  (+{cum_ins:>7,} -{cum_del:>7,})\n"

    return out


def phase_detection(con: duckdb.DuckDBPyConnection) -> str:
    out = section("PHASE DETECTION")
    out += "Commits classified by subject line keyword matching.\n"
    out += "A commit can match multiple phases.\n\n"

    all_commits = con.execute("SELECT id, subject FROM commits ORDER BY id").fetchall()

    phase_commits: dict[str, list[int]] = {name: [] for name, _ in PHASE_KEYWORDS}

    for cid, subject in all_commits:
        for phase_name, pattern in PHASE_KEYWORDS:
            if re.search(pattern, subject, re.IGNORECASE):
                phase_commits[phase_name].append(cid)

    out += f"  {'Phase':<30s} {'Count':>6s}  {'First':>6s}  {'Last':>6s}  {'Span':>10s}\n"
    out += f"  {'-' * 30} {'-' * 6}  {'-' * 6}  {'-' * 6}  {'-' * 10}\n"

    for phase_name, cids in phase_commits.items():
        if not cids:
            out += f"  {phase_name:<30s} {'0':>6s}\n"
            continue
        first, last = min(cids), max(cids)
        out += f"  {phase_name:<30s} {len(cids):>6d}  #{first:>5d}  #{last:>5d}  #{first}-{last}\n"

    # Unclassified commits
    classified = set()
    for cids in phase_commits.values():
        classified.update(cids)
    unclassified = [cid for cid, _ in all_commits if cid not in classified]
    out += f"\n  Unclassified commits: {len(unclassified)}\n"

    return out


def evolution_narrative(con: duckdb.DuckDBPyConnection) -> str:
    out = section("EVOLUTION NARRATIVE")
    out += "Chronological walk through development phases.\n"

    # Get all commits
    rows = con.execute("""
        SELECT id, short_hash, date, subject, files_changed, insertions, deletions
        FROM commits ORDER BY id
    """).fetchall()

    # Group into time-based chunks (by day)
    days: dict[str, list] = {}
    for row in rows:
        day = row[2][:10]  # YYYY-MM-DD
        days.setdefault(day, []).append(row)

    for day, commits in days.items():
        total_ins = sum(c[5] for c in commits)
        total_del = sum(c[6] for c in commits)
        out += f"\n  {day} — {len(commits)} commits (+{total_ins:,} -{total_del:,})\n"

        # Show notable commits (large changes, milestone subjects)
        for cid, shash, date, subject, nfiles, ins, dels in commits:
            # Always show first 5 per day and any with >100 lines changed
            notable = (ins + dels) > 200 or nfiles > 10
            milestone_kw = re.search(
                r"scaffold|milestone|postgres|sqlite|ffmpeg|linux|kernel|duckdb|"
                r"self.host|bootstrap|pass rate|passing|100%|ELF|DWARF|linker|"
                r"assembl|real.world|Lock:|initial",
                subject, re.IGNORECASE
            )
            if notable or milestone_kw:
                time_part = date[11:16] if len(date) > 11 else ""
                out += f"    {time_part} {shash} {subject[:90]}\n"
                if ins + dels > 500:
                    out += f"           (+{ins:,} -{dels:,}, {nfiles} files)\n"

    return out


def interesting_patterns(con: duckdb.DuckDBPyConnection) -> str:
    out = section("INTERESTING PATTERNS")

    # Lock: prefixed commits
    out += subsection("Lock: Prefixed Commits (Task Management)")
    rows = con.execute("""
        SELECT id, short_hash, date, subject
        FROM commits WHERE subject LIKE 'Lock:%' ORDER BY id
    """).fetchall()
    out += f"  Total Lock: commits: {len(rows)}\n"
    for cid, shash, date, subject in rows[:30]:
        out += f"    #{cid:>4d} {shash} {date[:16]} {subject}\n"
    if len(rows) > 30:
        out += f"    ... and {len(rows) - 30} more\n"

    # Largest commits by insertions
    out += subsection("Top 20 Largest Commits (by insertions)")
    rows = con.execute("""
        SELECT id, short_hash, date, subject, files_changed, insertions, deletions
        FROM commits ORDER BY insertions DESC LIMIT 20
    """).fetchall()
    for cid, shash, date, subject, nf, ins, dels in rows:
        out += f"  #{cid:>4d} {shash} +{ins:>6,} -{dels:>6,} ({nf:>3d} files) {subject[:70]}\n"

    # Largest commits by files changed
    out += subsection("Top 20 Largest Commits (by files changed)")
    rows = con.execute("""
        SELECT id, short_hash, date, subject, files_changed, insertions, deletions
        FROM commits ORDER BY files_changed DESC LIMIT 20
    """).fetchall()
    for cid, shash, date, subject, nf, ins, dels in rows:
        out += f"  #{cid:>4d} {shash} +{ins:>6,} -{dels:>6,} ({nf:>3d} files) {subject[:70]}\n"

    # Most frequently modified files (hotspots)
    out += subsection("Top 30 Most Modified Files (Hotspots)")
    rows = con.execute("""
        SELECT file_path, COUNT(*) as touches,
               SUM(insertions) as ins, SUM(deletions) as del
        FROM commit_files
        GROUP BY file_path ORDER BY touches DESC LIMIT 30
    """).fetchall()
    for path, touches, ins, dels in rows:
        out += f"  {touches:>4d} touches  +{ins:>6,} -{dels:>6,}  {path}\n"

    # Commit message length distribution
    out += subsection("Commit Message Length Distribution")
    rows = con.execute("""
        SELECT
            CASE
                WHEN LENGTH(subject) < 30 THEN '< 30 chars'
                WHEN LENGTH(subject) < 50 THEN '30-49 chars'
                WHEN LENGTH(subject) < 80 THEN '50-79 chars'
                WHEN LENGTH(subject) < 120 THEN '80-119 chars'
                ELSE '120+ chars'
            END as bucket,
            COUNT(*) as n
        FROM commits GROUP BY bucket ORDER BY bucket
    """).fetchall()
    for bucket, n in rows:
        bar = "#" * (n // 10)
        out += f"  {bucket:<15s} {n:>5d}  {bar}\n"

    # Body presence
    row = con.execute("""
        SELECT COUNT(*) FILTER (WHERE body IS NOT NULL AND body != ''),
               COUNT(*)
        FROM commits
    """).fetchone()
    out += f"\n  Commits with body text: {row[0]:,} of {row[1]:,} ({100*row[0]/row[1]:.1f}%)\n"

    # Files by extension
    out += subsection("File Modifications by Extension")
    rows = con.execute("""
        SELECT
            CASE
                WHEN file_path LIKE '%.rs' THEN '.rs'
                WHEN file_path LIKE '%.toml' THEN '.toml'
                WHEN file_path LIKE '%.md' THEN '.md'
                WHEN file_path LIKE '%.txt' THEN '.txt'
                WHEN file_path LIKE '%.c' THEN '.c'
                WHEN file_path LIKE '%.h' THEN '.h'
                WHEN file_path LIKE '%.sh' THEN '.sh'
                WHEN file_path LIKE '%.gitignore' THEN '.gitignore'
                ELSE 'other'
            END as ext,
            COUNT(*) as touches,
            SUM(insertions) as ins, SUM(deletions) as del
        FROM commit_files GROUP BY ext ORDER BY touches DESC
    """).fetchall()
    for ext, touches, ins, dels in rows:
        out += f"  {ext:<12s} {touches:>5d} touches  +{ins:>7,} -{dels:>7,}\n"

    # Directory-level hotspots
    out += subsection("Top 20 Directory-Level Hotspots")
    rows = con.execute("""
        SELECT
            CASE
                WHEN file_path LIKE '%/%'
                THEN regexp_replace(file_path, '/[^/]+$', '')
                ELSE '.'
            END as dir,
            COUNT(*) as touches,
            SUM(insertions) as ins, SUM(deletions) as del
        FROM commit_files GROUP BY dir ORDER BY touches DESC LIMIT 20
    """).fetchall()
    for d, touches, ins, dels in rows:
        out += f"  {touches:>5d} touches  +{ins:>7,} -{dels:>7,}  {d}\n"

    return out


def real_world_milestones(con: duckdb.DuckDBPyConnection) -> str:
    out = section("REAL-WORLD COMPILATION MILESTONES")
    out += "Commits mentioning real-world projects in subject or body.\n"

    projects = [
        ("PostgreSQL", r"postgres|postgresql"),
        ("SQLite", r"sqlite"),
        ("DuckDB", r"duckdb"),
        ("FFmpeg", r"ffmpeg"),
        ("Linux kernel", r"linux.kernel|kernel|defconfig|vmlinux"),
        ("curl", r"\bcurl\b"),
        ("nginx", r"nginx"),
        ("Redis", r"redis"),
        ("Git", r"\bgit\b"),
        ("Lua", r"\blua\b"),
        ("TCC", r"\btcc\b"),
        ("zlib", r"\bzlib\b"),
    ]

    for proj_name, pattern in projects:
        rows = con.execute(f"""
            SELECT id, short_hash, date, subject
            FROM commits
            WHERE regexp_matches(subject, '{pattern}')
               OR regexp_matches(body, '{pattern}')
            ORDER BY id
        """).fetchall()
        if rows:
            out += f"\n  {proj_name}: {len(rows)} commits\n"
            out += f"    First mention: #{rows[0][0]} {rows[0][2][:16]} — {rows[0][3][:80]}\n"
            if len(rows) > 1:
                out += f"    Last mention:  #{rows[-1][0]} {rows[-1][2][:16]} — {rows[-1][3][:80]}\n"

    return out


def summary_stats(con: duckdb.DuckDBPyConnection) -> str:
    out = section("PROJECT SUMMARY")

    row = con.execute("""
        SELECT COUNT(*), MIN(date), MAX(date),
               SUM(insertions), SUM(deletions),
               AVG(insertions), AVG(deletions),
               MAX(insertions), MAX(deletions)
        FROM commits
    """).fetchone()
    total, start, end, sum_ins, sum_del, avg_ins, avg_del, max_ins, max_del = row

    # Duration in hours
    dur = con.execute(f"""
        SELECT EXTRACT(EPOCH FROM ('{end}'::TIMESTAMP - '{start}'::TIMESTAMP)) / 3600.0
    """).fetchone()[0]

    out += f"  Commits:             {total:,}\n"
    out += f"  Duration:            {dur:.1f} hours ({dur/24:.1f} days)\n"
    out += f"  Avg commits/hour:    {total/dur:.1f}\n"
    out += f"  Total insertions:    {sum_ins:,}\n"
    out += f"  Total deletions:     {sum_del:,}\n"
    out += f"  Net lines:           {sum_ins - sum_del:,}\n"
    out += f"  Avg insertions/commit: {avg_ins:.1f}\n"
    out += f"  Avg deletions/commit:  {avg_del:.1f}\n"
    out += f"  Max insertions:      {max_ins:,}\n"
    out += f"  Max deletions:       {max_del:,}\n"

    # Unique files ever touched
    row = con.execute("SELECT COUNT(DISTINCT file_path) FROM commit_files").fetchone()
    out += f"  Unique files touched: {row[0]:,}\n"

    # Author breakdown
    out += subsection("Authors")
    rows = con.execute("""
        SELECT author, COUNT(*) as n FROM commits GROUP BY author ORDER BY n DESC
    """).fetchall()
    for author, n in rows:
        out += f"  {author}: {n:,} commits\n"

    return out


def main() -> None:
    con = connect()

    report = ""
    report += summary_stats(con)
    report += timeline_overview(con)
    report += phase_detection(con)
    report += real_world_milestones(con)
    report += interesting_patterns(con)
    report += evolution_narrative(con)

    con.close()

    with open(REPORT_PATH, "w", encoding="utf-8") as f:
        f.write(report)

    import sys
    sys.stdout.reconfigure(encoding="utf-8")
    print(report)
    print(f"\nReport written to {REPORT_PATH}")


if __name__ == "__main__":
    main()
