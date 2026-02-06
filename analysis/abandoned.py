"""Phase 5: Abandoned Paths Analysis — quantify dead-end exploration."""

from collections import defaultdict

import duckdb

from analysis.utils.git_helpers import list_files_at_head
from analysis.utils.file_classify import classify_file

DB_PATH = r"D:\projects\ccc\commits.db"


def run_abandoned_analysis() -> dict:
    """Compare all files ever created vs files at HEAD.

    Returns:
        - abandoned_files: list of dicts with file_path, type, first_commit, last_commit,
          lifespan_hours, total_insertions, total_deletions, modification_count
        - summary stats
    """
    con = duckdb.connect(DB_PATH, read_only=True)

    # All files ever touched
    all_files_data = con.execute("""
        SELECT
            cf.file_path,
            COUNT(*) as mod_count,
            SUM(cf.insertions) as total_ins,
            SUM(cf.deletions) as total_del,
            MIN(c.date) as first_date,
            MAX(c.date) as last_date,
            MIN(c.id) as first_commit_id,
            MAX(c.id) as last_commit_id
        FROM commit_files cf
        JOIN commits c ON cf.commit_hash = c.hash
        GROUP BY cf.file_path
    """).fetchall()

    con.close()

    # Files at HEAD
    head_files = set(list_files_at_head())

    abandoned = []
    surviving = []

    for (fpath, mod_count, total_ins, total_del,
         first_date, last_date, first_id, last_id) in all_files_data:
        ftype = classify_file(fpath)
        entry = {
            "file_path": fpath,
            "type": ftype,
            "modification_count": mod_count,
            "total_insertions": total_ins,
            "total_deletions": total_del,
            "first_date": first_date,
            "last_date": last_date,
            "first_commit_id": first_id,
            "last_commit_id": last_id,
        }
        if fpath in head_files:
            surviving.append(entry)
        else:
            abandoned.append(entry)

    # Compute lifespan using commit IDs as proxy (since project is 14 days)
    total_commits = max(e["last_commit_id"] for e in abandoned + surviving) if (abandoned + surviving) else 1
    for entry in abandoned:
        span = entry["last_commit_id"] - entry["first_commit_id"]
        entry["lifespan_commits"] = span
        # Rough hours: 14 days * 24 hours / total_commits * span
        entry["lifespan_hours"] = (14 * 24 / total_commits) * span

    return {
        "abandoned": abandoned,
        "surviving": surviving,
        "total_files_ever": len(all_files_data),
        "head_file_count": len(head_files),
    }


def format_abandoned_report(data: dict) -> str:
    out = []
    out.append("=" * 70)
    out.append("ABANDONED PATHS ANALYSIS")
    out.append("=" * 70)

    total = data["total_files_ever"]
    at_head = data["head_file_count"]
    abandoned = data["abandoned"]
    n_abandoned = len(abandoned)

    out.append(f"\n  Files ever created:   {total:,}")
    out.append(f"  Files at HEAD:        {at_head:,}")
    out.append(f"  Abandoned files:      {n_abandoned:,} ({100*n_abandoned/total:.1f}%)")

    # Investment in abandoned files
    total_inv = sum(f["total_insertions"] for f in abandoned)
    out.append(f"  Lines invested in abandoned: {total_inv:,}")

    # By file type
    out.append("\n--- Abandoned by File Type ---")
    type_counts: dict[str, dict] = defaultdict(lambda: {"count": 0, "insertions": 0})
    for f in abandoned:
        type_counts[f["type"]]["count"] += 1
        type_counts[f["type"]]["insertions"] += f["total_insertions"]

    out.append(f"  {'Type':<12s} {'Count':>6s} {'Lines Invested':>15s}")
    out.append(f"  {'-'*12} {'-'*6} {'-'*15}")
    for ftype, vals in sorted(type_counts.items(), key=lambda x: -x[1]["count"]):
        out.append(f"  {ftype:<12s} {vals['count']:>6d} {vals['insertions']:>15,}")

    # Lifespan distribution (using commit-count-based thresholds)
    # Project is ~14 days, ~3982 commits. Thresholds:
    # Immediate: <100 commits (~6 hours)
    # Quick pivot: 100-500 commits (~1-2 days)
    # Abandoned approach: 500-2000 commits (~2-7 days)
    # Architectural: >2000 commits (>7 days)
    bins = [
        ("Immediate (<100 commits)", 0, 100),
        ("Quick pivot (100-500)", 100, 500),
        ("Abandoned approach (500-2000)", 500, 2000),
        ("Architectural (>2000)", 2000, float("inf")),
    ]

    out.append("\n--- Lifespan Distribution ---")
    for label, lo, hi in bins:
        files_in_bin = [f for f in abandoned if lo <= f["lifespan_commits"] < hi]
        inv = sum(f["total_insertions"] for f in files_in_bin)
        out.append(f"  {label:<35s} {len(files_in_bin):>5d} files  {inv:>7,} lines invested")

    # Top abandoned files by investment
    out.append("\n--- Top 30 Abandoned Files by Investment ---")
    sorted_abandoned = sorted(abandoned, key=lambda x: -x["total_insertions"])
    out.append(f"  {'Lines':>7s} {'Mods':>5s} {'Lifespan':>8s} {'Type':<8s} Path")
    out.append(f"  {'-'*7} {'-'*5} {'-'*8} {'-'*8} {'-'*40}")
    for f in sorted_abandoned[:30]:
        out.append(
            f"  {f['total_insertions']:>7,} {f['modification_count']:>5d} "
            f"{f['lifespan_commits']:>6d}c  {f['type']:<8s} {f['file_path']}"
        )

    # Abandoned directories
    out.append("\n--- Abandoned by Top-Level Directory ---")
    dir_counts: dict[str, dict] = defaultdict(lambda: {"count": 0, "insertions": 0})
    for f in abandoned:
        parts = f["file_path"].split("/")
        top_dir = parts[0] if len(parts) > 1 else "."
        dir_counts[top_dir]["count"] += 1
        dir_counts[top_dir]["insertions"] += f["total_insertions"]

    for d, vals in sorted(dir_counts.items(), key=lambda x: -x[1]["count"]):
        out.append(f"  {d:<30s} {vals['count']:>5d} files  {vals['insertions']:>7,} lines")

    return "\n".join(out)


def main() -> None:
    print("Running abandoned paths analysis...")
    data = run_abandoned_analysis()
    report = format_abandoned_report(data)
    print(report)

    report_path = r"D:\projects\ccc\abandoned_report.txt"
    with open(report_path, "w", encoding="utf-8") as f:
        f.write(report)
    print(f"\nReport written to {report_path}")


if __name__ == "__main__":
    main()
