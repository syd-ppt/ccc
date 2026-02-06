"""Phase 2: Survival Analysis — what % of written lines exist in final state."""

import sys
from collections import defaultdict

import duckdb

from analysis.utils.git_helpers import blame_file, list_files_at_head
from analysis.utils.file_classify import classify_file

DB_PATH = r"D:\projects\ccc\commits.db"


def run_survival_analysis() -> dict:
    """Run git blame on all files at HEAD, map lines to commits.

    Returns dict with:
        - per_commit: {hash: {added: int, survived: int}}
        - per_type: {type: {added: int, survived: int}}
        - overall: {added: int, survived: int}
    """
    con = duckdb.connect(DB_PATH, read_only=True)

    # Get total lines added per commit from DB
    commit_added: dict[str, int] = {}
    rows = con.execute("SELECT hash, insertions FROM commits ORDER BY id").fetchall()
    for h, ins in rows:
        commit_added[h] = ins

    # Get commit ordering
    commit_order: dict[str, int] = {}
    rows = con.execute("SELECT hash, id FROM commits").fetchall()
    for h, cid in rows:
        commit_order[h] = cid

    con.close()

    # Blame every file at HEAD
    files = list_files_at_head()
    print(f"  Running git blame on {len(files)} files...")

    survived_per_commit: dict[str, int] = defaultdict(int)
    survived_per_type: dict[str, int] = defaultdict(int)
    added_per_type: dict[str, int] = defaultdict(int)
    total_survived = 0
    errors = 0

    for i, fpath in enumerate(files):
        if i % 100 == 0 and i > 0:
            print(f"    Blamed {i}/{len(files)} files...")
        ftype = classify_file(fpath)
        try:
            blame_lines = blame_file(fpath)
        except RuntimeError:
            errors += 1
            continue

        for commit_hash, _line_content in blame_lines:
            survived_per_commit[commit_hash] += 1
            survived_per_type[ftype] += 1
            total_survived += 1

    # Compute added_per_type from commit_files
    con = duckdb.connect(DB_PATH, read_only=True)
    rows = con.execute("SELECT file_path, SUM(insertions) FROM commit_files GROUP BY file_path").fetchall()
    for fpath, ins in rows:
        ftype = classify_file(fpath)
        added_per_type[ftype] += ins
    con.close()

    total_added = sum(commit_added.values())

    # Build per-commit results
    per_commit = {}
    for h, added in commit_added.items():
        per_commit[h] = {
            "order": commit_order.get(h, 0),
            "added": added,
            "survived": survived_per_commit.get(h, 0),
        }

    # Per-type results
    per_type = {}
    for ftype in set(list(survived_per_type.keys()) + list(added_per_type.keys())):
        added = added_per_type.get(ftype, 0)
        surv = survived_per_type.get(ftype, 0)
        per_type[ftype] = {"added": added, "survived": surv}

    if errors:
        print(f"    {errors} files failed blame (binary or deleted)")

    return {
        "per_commit": per_commit,
        "per_type": per_type,
        "overall": {"added": total_added, "survived": total_survived},
    }


def format_survival_report(data: dict) -> str:
    out = []
    out.append("=" * 70)
    out.append("SURVIVAL ANALYSIS")
    out.append("=" * 70)

    overall = data["overall"]
    rate = 100 * overall["survived"] / overall["added"] if overall["added"] else 0
    out.append(f"\n  Lines added (total):     {overall['added']:,}")
    out.append(f"  Lines in final state:    {overall['survived']:,}")
    out.append(f"  Overall survival rate:   {rate:.1f}%")
    out.append(f"  Exploration cost:        {overall['added'] - overall['survived']:,} lines")

    # Per file type
    out.append("\n--- Survival by File Type ---")
    out.append(f"  {'Type':<12s} {'Added':>8s} {'Survived':>9s} {'Rate':>6s}")
    out.append(f"  {'-'*12} {'-'*8} {'-'*9} {'-'*6}")
    for ftype, vals in sorted(data["per_type"].items(), key=lambda x: -x[1]["added"]):
        added = vals["added"]
        surv = vals["survived"]
        rate = 100 * surv / added if added else 0
        out.append(f"  {ftype:<12s} {added:>8,} {surv:>9,} {rate:>5.1f}%")

    # Phase survival (quartiles by commit order)
    per_commit = data["per_commit"]
    sorted_commits = sorted(per_commit.values(), key=lambda x: x["order"])
    n = len(sorted_commits)
    quartile_size = n // 4

    out.append("\n--- Convergence: Survival by Project Phase ---")
    for q in range(4):
        start = q * quartile_size
        end = (q + 1) * quartile_size if q < 3 else n
        phase = sorted_commits[start:end]
        added = sum(c["added"] for c in phase)
        survived = sum(c["survived"] for c in phase)
        rate = 100 * survived / added if added else 0
        pct_start = q * 25
        pct_end = (q + 1) * 25 if q < 3 else 100
        bar_filled = int(rate / 100 * 30)
        bar = "#" * bar_filled + "." * (30 - bar_filled)
        out.append(f"  Phase {q+1} ({pct_start:>2d}-{pct_end:>3d}%):  {bar} {rate:5.1f}%  (+{added:,} lines, {survived:,} survived)")

    # Zero-survival commits
    zero_survival = [c for c in sorted_commits if c["added"] > 0 and c["survived"] == 0]
    out.append(f"\n  Zero-survival commits: {len(zero_survival)} of {n} ({100*len(zero_survival)/n:.1f}%)")

    return "\n".join(out)


def main() -> None:
    print("Running survival analysis...")
    data = run_survival_analysis()
    report = format_survival_report(data)
    print(report)

    report_path = r"D:\projects\ccc\survival_report.txt"
    with open(report_path, "w", encoding="utf-8") as f:
        f.write(report)
    print(f"\nReport written to {report_path}")


if __name__ == "__main__":
    main()
