"""Phase 3: Trajectory Analysis — learning vs thrashing differentiation.

Measures edit distance to final state for files over their modification history.
Computationally expensive: runs on top N hotspot files by default.
"""

import difflib
from collections import defaultdict

import duckdb

from analysis.utils.git_helpers import file_at_commit, list_files_at_head, commits_touching_file
from analysis.utils.file_classify import classify_file

DB_PATH = r"D:\projects\ccc\commits.db"

# Only analyze top N files by modification count (edit distance is expensive)
TOP_N_FILES = 50


def normalized_edit_distance(a: str, b: str) -> float:
    """Compute normalized edit distance between two strings.

    Returns 0.0 for identical, 1.0 for completely different.
    Uses SequenceMatcher ratio (similarity), converted to distance.
    """
    if a == b:
        return 0.0
    if not a and not b:
        return 0.0
    if not a or not b:
        return 1.0
    ratio = difflib.SequenceMatcher(None, a.splitlines(), b.splitlines()).ratio()
    return 1.0 - ratio


def run_trajectory_analysis(top_n: int = TOP_N_FILES) -> dict:
    """For top N most-modified files, compute distance-to-final trajectory.

    Returns dict of file_path -> {
        trajectory: [(commit_hash, commit_order, distance_to_final)],
        classification: "learning" | "thrashing" | "mixed",
        decrease_ratio, oscillation_rate, net_progress
    }
    """
    con = duckdb.connect(DB_PATH, read_only=True)

    # Get top N files by modification count that exist at HEAD
    head_files = set(list_files_at_head())

    rows = con.execute("""
        SELECT file_path, COUNT(*) as mods
        FROM commit_files
        GROUP BY file_path
        ORDER BY mods DESC
    """).fetchall()
    con.close()

    # Filter to files at HEAD with multiple modifications
    target_files = []
    for fpath, mods in rows:
        if fpath in head_files and mods >= 3:
            target_files.append((fpath, mods))
        if len(target_files) >= top_n:
            break

    print(f"  Analyzing trajectories for {len(target_files)} files...")

    results = {}
    for i, (fpath, mod_count) in enumerate(target_files):
        if i % 10 == 0:
            print(f"    Processing file {i+1}/{len(target_files)}: {fpath}")

        # Get final content
        try:
            final_content = file_at_commit("HEAD", fpath)
        except RuntimeError:
            continue

        # Get commits that touched this file
        commit_hashes = commits_touching_file(fpath)
        if len(commit_hashes) < 3:
            continue

        # Sample if too many commits (>50 touching this file)
        if len(commit_hashes) > 50:
            step = len(commit_hashes) // 50
            sampled = commit_hashes[::step]
            if commit_hashes[-1] not in sampled:
                sampled.append(commit_hashes[-1])
            commit_hashes = sampled

        # Compute distance at each commit
        trajectory = []
        for j, chash in enumerate(commit_hashes):
            try:
                content = file_at_commit(chash, fpath)
                dist = normalized_edit_distance(content, final_content)
                trajectory.append((chash, j, dist))
            except RuntimeError:
                continue

        if len(trajectory) < 3:
            continue

        # Analyze trajectory
        distances = [t[2] for t in trajectory]
        deltas = [distances[k+1] - distances[k] for k in range(len(distances) - 1)]

        monotonic_decreases = sum(1 for d in deltas if d < 0)
        total_transitions = len(deltas)
        decrease_ratio = monotonic_decreases / total_transitions if total_transitions else 0

        # Direction changes
        direction_changes = 0
        for k in range(1, len(deltas)):
            if (deltas[k] > 0 and deltas[k-1] < 0) or (deltas[k] < 0 and deltas[k-1] > 0):
                direction_changes += 1
        oscillation_rate = direction_changes / (len(deltas) - 1) if len(deltas) > 1 else 0

        net_progress = distances[0] - distances[-1]

        # Classification
        if decrease_ratio > 0.6 and net_progress > 0.1:
            classification = "learning"
        elif oscillation_rate > 0.5 or net_progress <= 0.1:
            classification = "thrashing"
        else:
            classification = "mixed"

        results[fpath] = {
            "trajectory": trajectory,
            "classification": classification,
            "decrease_ratio": decrease_ratio,
            "oscillation_rate": oscillation_rate,
            "net_progress": net_progress,
            "mod_count": mod_count,
            "type": classify_file(fpath),
        }

    return results


def format_trajectory_report(results: dict) -> str:
    out = []
    out.append("=" * 70)
    out.append("TRAJECTORY ANALYSIS: LEARNING vs THRASHING")
    out.append("=" * 70)

    # Summary counts
    counts = defaultdict(int)
    for fpath, data in results.items():
        counts[data["classification"]] += 1

    total = len(results)
    out.append(f"\n  Files analyzed: {total}")
    for cls in ["learning", "mixed", "thrashing"]:
        n = counts[cls]
        pct = 100 * n / total if total else 0
        out.append(f"  {cls.capitalize():<12s}: {n:>4d} ({pct:.1f}%)")

    # By file type
    out.append("\n--- Classification by File Type ---")
    type_class: dict[str, dict[str, int]] = defaultdict(lambda: defaultdict(int))
    for fpath, data in results.items():
        type_class[data["type"]][data["classification"]] += 1

    for ftype, classes in sorted(type_class.items()):
        parts = [f"{cls}={n}" for cls, n in sorted(classes.items())]
        out.append(f"  {ftype:<12s} {', '.join(parts)}")

    # Detailed per-file results, sorted by classification then name
    out.append("\n--- Per-File Results ---")
    out.append(f"  {'Classification':<12s} {'DecR':>5s} {'OscR':>5s} {'NetP':>5s} {'Mods':>5s} Path")
    out.append(f"  {'-'*12} {'-'*5} {'-'*5} {'-'*5} {'-'*5} {'-'*40}")

    sorted_results = sorted(results.items(), key=lambda x: (
        {"thrashing": 0, "mixed": 1, "learning": 2}[x[1]["classification"]],
        x[0],
    ))

    for fpath, data in sorted_results:
        out.append(
            f"  {data['classification']:<12s} "
            f"{data['decrease_ratio']:>5.2f} "
            f"{data['oscillation_rate']:>5.2f} "
            f"{data['net_progress']:>5.2f} "
            f"{data['mod_count']:>5d} "
            f"{fpath}"
        )

    # Worst thrashers detail
    thrashers = [(f, d) for f, d in results.items() if d["classification"] == "thrashing"]
    if thrashers:
        out.append("\n--- Thrashing Files: Distance Trajectories ---")
        thrashers.sort(key=lambda x: x[1]["oscillation_rate"], reverse=True)
        for fpath, data in thrashers[:10]:
            out.append(f"\n  {fpath}")
            traj = data["trajectory"]
            for _h, idx, dist in traj:
                bar = "#" * int(dist * 40)
                out.append(f"    [{idx:>3d}] {dist:.3f} {bar}")

    return "\n".join(out)


def main() -> None:
    print("Running trajectory analysis...")
    results = run_trajectory_analysis()
    report = format_trajectory_report(results)
    print(report)

    report_path = r"D:\projects\ccc\trajectory_report.txt"
    with open(report_path, "w", encoding="utf-8") as f:
        f.write(report)
    print(f"\nReport written to {report_path}")


if __name__ == "__main__":
    main()
