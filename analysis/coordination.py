"""Phase 4: Coordination Analysis — thrashing detection on file-level edits."""

from collections import defaultdict

import duckdb

from analysis.utils.file_classify import classify_file

DB_PATH = r"D:\projects\ccc\commits.db"

# Thresholds (adapted for single-author AI with high commit velocity)
THRASH_WINDOW_MINUTES = 30  # Consecutive edits within 30 min = thrash incident
RAPID_OVERWRITE_MINUTES = 10  # Edits within 10 min that delete >50% of previous additions
RAPID_OVERWRITE_RATIO = 0.5


def run_coordination_analysis() -> dict:
    """Detect thrashing: rapid consecutive edits to the same file."""
    con = duckdb.connect(DB_PATH, read_only=True)

    # Get all file touches ordered by file then time
    rows = con.execute("""
        SELECT cf.file_path, c.date, c.hash, cf.insertions, cf.deletions, c.id
        FROM commit_files cf
        JOIN commits c ON cf.commit_hash = c.hash
        ORDER BY cf.file_path, c.id
    """).fetchall()
    con.close()

    # Group by file
    file_touches: dict[str, list] = defaultdict(list)
    for fpath, date, chash, ins, dels, cid in rows:
        file_touches[fpath].append({
            "date": date,
            "hash": chash,
            "insertions": ins,
            "deletions": dels,
            "commit_id": cid,
        })

    thrash_incidents = []
    rapid_overwrites = []
    file_thrash_counts: dict[str, int] = defaultdict(int)

    for fpath, touches in file_touches.items():
        for i in range(1, len(touches)):
            prev = touches[i - 1]
            curr = touches[i]

            # Compute time delta using commit IDs as proxy
            # ~3982 commits in ~14 days = ~5 min per commit average
            commit_delta = curr["commit_id"] - prev["commit_id"]
            approx_minutes = commit_delta * (14 * 24 * 60 / 3982)

            if approx_minutes < THRASH_WINDOW_MINUTES:
                thrash_incidents.append({
                    "file_path": fpath,
                    "type": classify_file(fpath),
                    "prev_hash": prev["hash"],
                    "curr_hash": curr["hash"],
                    "prev_commit_id": prev["commit_id"],
                    "curr_commit_id": curr["commit_id"],
                    "delta_minutes": approx_minutes,
                    "prev_insertions": prev["insertions"],
                    "curr_deletions": curr["deletions"],
                })
                file_thrash_counts[fpath] += 1

                # Check rapid overwrite
                if (approx_minutes < RAPID_OVERWRITE_MINUTES
                        and prev["insertions"] > 0
                        and curr["deletions"] > RAPID_OVERWRITE_RATIO * prev["insertions"]):
                    rapid_overwrites.append({
                        "file_path": fpath,
                        "type": classify_file(fpath),
                        "prev_hash": prev["hash"],
                        "curr_hash": curr["hash"],
                        "delta_minutes": approx_minutes,
                        "prev_insertions": prev["insertions"],
                        "curr_deletions": curr["deletions"],
                    })

    return {
        "thrash_incidents": thrash_incidents,
        "rapid_overwrites": rapid_overwrites,
        "file_thrash_counts": file_thrash_counts,
        "total_file_touches": sum(len(t) for t in file_touches.values()),
    }


def format_coordination_report(data: dict) -> str:
    out = []
    out.append("=" * 70)
    out.append("COORDINATION / THRASHING ANALYSIS")
    out.append("=" * 70)

    incidents = data["thrash_incidents"]
    overwrites = data["rapid_overwrites"]
    file_counts = data["file_thrash_counts"]

    out.append(f"\n  Total file touches:     {data['total_file_touches']:,}")
    out.append(f"  Thrash incidents (<{THRASH_WINDOW_MINUTES}min): {len(incidents):,}")
    out.append(f"  Rapid overwrites (<{RAPID_OVERWRITE_MINUTES}min, >{int(RAPID_OVERWRITE_RATIO*100)}% deleted): {len(overwrites):,}")

    # Thrashing by file type
    out.append("\n--- Thrash Incidents by File Type ---")
    type_counts: dict[str, int] = defaultdict(int)
    for inc in incidents:
        type_counts[inc["type"]] += 1
    for ftype, count in sorted(type_counts.items(), key=lambda x: -x[1]):
        out.append(f"  {ftype:<12s} {count:>6,} incidents")

    # Top thrash hotspots
    out.append("\n--- Top 30 Thrash Hotspots ---")
    sorted_files = sorted(file_counts.items(), key=lambda x: -x[1])
    for fpath, count in sorted_files[:30]:
        ftype = classify_file(fpath)
        out.append(f"  {count:>4d} incidents  {ftype:<8s}  {fpath}")

    # Rapid overwrite details
    if overwrites:
        out.append(f"\n--- Top 20 Rapid Overwrites ---")
        sorted_ow = sorted(overwrites, key=lambda x: -x["curr_deletions"])
        for ow in sorted_ow[:20]:
            out.append(
                f"  {ow['file_path']}\n"
                f"    Commit #{ow['prev_hash'][:7]} added {ow['prev_insertions']} lines, "
                f"then #{ow['curr_hash'][:7]} deleted {ow['curr_deletions']} lines "
                f"({ow['delta_minutes']:.0f} min later)"
            )

    # Thrashing over time (by project quartile)
    out.append("\n--- Thrashing Over Project Phases ---")
    quartile_size = 3982 // 4
    for q in range(4):
        lo = q * quartile_size
        hi = (q + 1) * quartile_size if q < 3 else 9999
        count = sum(1 for inc in incidents if lo < inc["curr_commit_id"] <= hi)
        pct_start = q * 25
        pct_end = (q + 1) * 25 if q < 3 else 100
        out.append(f"  Phase {q+1} ({pct_start:>2d}-{pct_end:>3d}%): {count:>5,} incidents")

    return "\n".join(out)


def main() -> None:
    print("Running coordination/thrashing analysis...")
    data = run_coordination_analysis()
    report = format_coordination_report(data)
    print(report)

    report_path = r"D:\projects\ccc\coordination_report.txt"
    with open(report_path, "w", encoding="utf-8") as f:
        f.write(report)
    print(f"\nReport written to {report_path}")


if __name__ == "__main__":
    main()
