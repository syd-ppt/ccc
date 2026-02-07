"""Generate a Gource custom log from commits.db with creative iteration tracking.

5-color scheme:
  Green  (00FF00) - Creation: first appearance of a file
  Red    (FF3333) - Destruction: pure deletion
  Blue   (CCCCFF) - Routine edit: normal modification
  Orange (FFAA00) - Rethinking: heavy rewrite (min(ins,del) >= 10, ratio > 0.2)
  Gold   (FFD700) - Eureka: last heavy rewrite for a file with 4+ rewrites

Also generates:
  gource_captions.txt  - narrative captions for Gource --caption-file
  counter_overlay.ass  - ASS subtitle overlay with running eureka counter
"""

import duckdb
from datetime import datetime, timezone

DB_PATH = "D:/projects/ccc/commits.db"
OUTPUT_DIR = "D:/projects/ccc"
OUTPUT_LOG = f"{OUTPUT_DIR}/gource_custom.log"
OUTPUT_CAPTIONS = f"{OUTPUT_DIR}/gource_captions.txt"
OUTPUT_ASS = f"{OUTPUT_DIR}/counter_overlay.ass"

# 5-color scheme
COLOR_ADD = "00FF00"
COLOR_DELETE = "FF3333"
COLOR_MODIFY = "CCCCFF"
COLOR_REWRITE = "FFAA00"
COLOR_EUREKA = "FFD700"

# Rewrite detection thresholds
REWRITE_MIN_LINES = 10
REWRITE_RATIO = 0.2
EUREKA_REWRITE_THRESHOLD = 4

# Gource timing parameters (must match render_gource.sh)
SECONDS_PER_DAY = 17


def iso_to_unix(iso_str: str) -> int:
    dt = datetime.fromisoformat(iso_str.replace("Z", "+00:00"))
    return int(dt.timestamp())


def is_heavy_rewrite(insertions: int, deletions: int) -> bool:
    if insertions <= 0 or deletions <= 0:
        return False
    min_val = min(insertions, deletions)
    max_val = max(insertions, deletions)
    return min_val >= REWRITE_MIN_LINES and (min_val / max_val) > REWRITE_RATIO


def format_ass_time(seconds: float) -> str:
    """Format seconds as ASS timestamp H:MM:SS.cc (centiseconds)."""
    h = int(seconds // 3600)
    m = int((seconds % 3600) // 60)
    s = int(seconds % 60)
    cs = int((seconds % 1) * 100)
    return f"{h}:{m:02d}:{s:02d}.{cs:02d}"


def generate_ass_file(
    eureka_timestamps: list[int],
    first_timestamp: int,
    total_hard_problems: int,
    zero_shot_pct: float,
) -> str:
    """Generate ASS subtitle file with running eureka counter in top-right."""
    header = """[Script Info]
Title: CCC Eureka Counter
ScriptType: v4.00+
PlayResX: 1920
PlayResY: 1080
WrapStyle: 0

[V4+ Styles]
Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV, Encoding
Style: Counter,Consolas,28,&H00FFFFFF,&H000000FF,&H00000000,&H80000000,-1,0,0,0,100,100,0,0,1,2,1,9,10,30,20,1

[Events]
Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text
"""
    events = []

    # Initial state: show 0/N from the start
    if eureka_timestamps:
        first_video_sec = max(0, (eureka_timestamps[0] - first_timestamp) / 86400 * SECONDS_PER_DAY - 5)
    else:
        first_video_sec = 0

    # Each eureka moment updates the counter; it persists until the next update
    for i, ts in enumerate(eureka_timestamps):
        count = i + 1
        video_sec = (ts - first_timestamp) / 86400 * SECONDS_PER_DAY

        # This event starts at this eureka and ends at the next (or end of video)
        if i + 1 < len(eureka_timestamps):
            next_sec = (eureka_timestamps[i + 1] - first_timestamp) / 86400 * SECONDS_PER_DAY
        else:
            next_sec = video_sec + 300  # last counter persists

        start = format_ass_time(video_sec)
        end = format_ass_time(next_sec)
        text = f"Hard problems solved: {count} / {total_hard_problems}\\NZero-shot: {zero_shot_pct:.1f}%"
        events.append(f"Dialogue: 0,{start},{end},Counter,,0,0,0,,{text}")

    # Pre-eureka display (0/N) from video start until first eureka
    if eureka_timestamps:
        pre_start = format_ass_time(first_video_sec)
        pre_end = format_ass_time((eureka_timestamps[0] - first_timestamp) / 86400 * SECONDS_PER_DAY)
        pre_text = f"Hard problems solved: 0 / {total_hard_problems}\\NZero-shot: {zero_shot_pct:.1f}%"
        events.insert(0, f"Dialogue: 0,{pre_start},{pre_end},Counter,,0,0,0,,{pre_text}")

    return header + "\n".join(events) + "\n"


# Narrative captions: (unix_timestamp, caption_text)
# Derived from commit history analysis
NARRATIVE_CAPTIONS = [
    ("2026-01-23T01:04:22Z", "Day 1: Empty repo — three backends at once"),
    ("2026-01-23T13:21:39Z", "Trying shared ArchCodegen trait..."),
    ("2026-01-24T09:33:07Z", "Decomposing lowerer: 10-commit refactor"),
    ("2026-01-25T05:34:44Z", "Optimization sprint: peephole, LICM, copy prop"),
    ("2026-01-26T05:34:00Z", "Building native x86 assembler"),
    ("2026-01-27T04:47:31Z", "Splitting monoliths into focused modules"),
    ("2026-01-28T07:20:07Z", "New target: i686 32-bit backend"),
    ("2026-01-29T00:42:25Z", "New run — reward hacks discovered and removed"),
    ("2026-01-30T07:36:44Z", "Peephole optimizers across all backends"),
    ("2026-02-03T22:43:39Z", "Pivoting: native assembler + ELF linker"),
    ("2026-02-04T07:28:45Z", "Deduplicating ELF infrastructure across 4 backends"),
    ("2026-02-05T08:46:47Z", "Linker modularization: 9500 lines → 30 files"),
]


def generate_captions() -> str:
    """Generate Gource caption file: unix_timestamp|caption_text"""
    lines = []
    for iso_date, text in NARRATIVE_CAPTIONS:
        ts = iso_to_unix(iso_date)
        lines.append(f"{ts}|{text}")
    return "\n".join(lines) + "\n"


def main() -> None:
    con = duckdb.connect(DB_PATH, read_only=True)

    rows = con.sql("""
        SELECT c.date, c.hash, c.author, cf.file_path, cf.insertions, cf.deletions
        FROM commits c
        JOIN commit_files cf ON c.hash = cf.commit_hash
        ORDER BY c.date ASC, c.id ASC, cf.id ASC
    """).fetchall()

    # === PASS 1: Pre-compute rewrite stats per file ===
    file_rewrite_count: dict[str, int] = {}
    file_last_rewrite: dict[str, str] = {}  # file_path -> commit_hash

    for date_str, commit_hash, author, file_path, insertions, deletions in rows:
        if is_heavy_rewrite(insertions, deletions):
            file_rewrite_count[file_path] = file_rewrite_count.get(file_path, 0) + 1
            file_last_rewrite[file_path] = commit_hash

    # Build eureka set: (file_path, commit_hash) for files with 4+ rewrites
    eureka_set: set[tuple[str, str]] = set()
    hard_problem_files = 0
    for fp, count in file_rewrite_count.items():
        if count >= EUREKA_REWRITE_THRESHOLD:
            eureka_set.add((fp, file_last_rewrite[fp]))
            hard_problem_files += 1

    # === PASS 2: Generate colored log entries ===
    seen_files: set[str] = set()
    lines: list[str] = []
    color_counts = {
        COLOR_ADD: 0,
        COLOR_DELETE: 0,
        COLOR_MODIFY: 0,
        COLOR_REWRITE: 0,
        COLOR_EUREKA: 0,
    }

    # Track eureka timestamps for the ASS overlay
    eureka_timestamps: list[int] = []
    eureka_seen: set[str] = set()  # dedupe per file

    for date_str, commit_hash, author, file_path, insertions, deletions in rows:
        timestamp = iso_to_unix(date_str)

        if deletions > 0 and insertions == 0:
            action = "D"
            color = COLOR_DELETE
            seen_files.discard(file_path)
        elif (file_path, commit_hash) in eureka_set:
            # Eureka check before Add — file may have been deleted and re-created
            action = "A" if file_path not in seen_files else "M"
            color = COLOR_EUREKA
            seen_files.add(file_path)
            if file_path not in eureka_seen:
                eureka_seen.add(file_path)
                eureka_timestamps.append(timestamp)
        elif file_path not in seen_files:
            action = "A"
            color = COLOR_ADD
            seen_files.add(file_path)
        elif is_heavy_rewrite(insertions, deletions):
            action = "M"
            color = COLOR_REWRITE
        else:
            action = "M"
            color = COLOR_MODIFY

        color_counts[color] += 1
        lines.append(f"{timestamp}|{author}|{action}|/{file_path}|{color}")

    con.close()

    # Sort eureka timestamps for sequential counter
    eureka_timestamps.sort()

    # Compute zero-shot percentage
    total_files = len({line.split("|")[3] for line in lines})
    files_with_rewrites = len(file_rewrite_count)
    zero_shot_pct = (total_files - files_with_rewrites) / total_files * 100

    # === Write gource log ===
    with open(OUTPUT_LOG, "w", encoding="utf-8") as f:
        f.write("\n".join(lines))
        f.write("\n")

    # === Write captions ===
    with open(OUTPUT_CAPTIONS, "w", encoding="utf-8") as f:
        f.write(generate_captions())

    # === Write ASS overlay ===
    first_ts = iso_to_unix(rows[0][0])
    ass_content = generate_ass_file(
        eureka_timestamps, first_ts, hard_problem_files, zero_shot_pct
    )
    with open(OUTPUT_ASS, "w", encoding="utf-8-sig") as f:
        f.write(ass_content)

    # === Report ===
    print(f"Wrote {len(lines)} entries to {OUTPUT_LOG}")
    print(f"First: {lines[0]}")
    print(f"Last:  {lines[-1]}")
    print()
    print("Color distribution:")
    print(f"  Green  (creation):   {color_counts[COLOR_ADD]}")
    print(f"  Red    (deletion):   {color_counts[COLOR_DELETE]}")
    print(f"  Blue   (routine):    {color_counts[COLOR_MODIFY]}")
    print(f"  Orange (rethinking): {color_counts[COLOR_REWRITE]}")
    print(f"  Gold   (eureka):     {color_counts[COLOR_EUREKA]}")
    print()
    print(f"Files with heavy rewrites: {files_with_rewrites}")
    print(f"Hard problems (4+ rewrites): {hard_problem_files}")
    print(f"Eureka moments: {len(eureka_timestamps)}")
    print(f"Zero-shot: {zero_shot_pct:.1f}%")
    print()
    print(f"Wrote {len(NARRATIVE_CAPTIONS)} captions to {OUTPUT_CAPTIONS}")
    print(f"Wrote ASS overlay to {OUTPUT_ASS}")


if __name__ == "__main__":
    main()
