# AI Multi-Agent Development Analysis Specification

## Overview

A systematic approach to analyzing git repositories produced by AI multi-agent systems. Combines visual inspection (Gource) with quantitative metrics to identify:

- Exploration efficiency
- Coordination quality
- Learning vs thrashing patterns
- Wasted effort quantification

**Target Context**: Single-branch repositories with high commit velocity (hundreds/thousands of commits over days), produced by autonomous AI agents working 24/7.

---

## Core Concepts

### Why AI Agent Analysis Differs from Human Analysis

| Human Development | AI Multi-Agent Development |
|-------------------|---------------------------|
| Commits reflect individual decisions | Commits reflect agent outputs |
| "Mistakes" indicate learning | "Mistakes" indicate exploration branches that lost |
| Commit messages convey intent | Commit messages are synthetic artifacts |
| Sequential, time-bounded work | Parallel, continuous operation |
| Learning persists across sessions | No cross-session learning |

### Key Metrics

| Metric | Definition | Purpose |
|--------|------------|---------|
| **Survival Rate** | % of lines written that exist in final state | Overall efficiency |
| **Convergence Efficiency** | Survival rate trend over project phases | Learning trajectory |
| **Thrashing Rate** | Oscillating edits with no net progress | Coordination failures |
| **Exploration Cost** | Total lines written minus lines in final | Price of finding solution |

---

## Analysis Pipeline

### Phase 1: Visual Analysis (Gource)

**Purpose**: Rapid pattern identification before quantitative analysis.

#### Configuration

```bash
gource \
  --seconds-per-day 0.3 \
  --auto-skip-seconds 0.5 \
  --file-idle-time 0 \
  --max-file-lag 0.1 \
  --hide usernames,mouse \
  --highlight-dirs \
  --dir-name-depth 2 \
  --filename-time 2 \
  --bloom-intensity 0.3 \
  --title "AI Agent Development" \
  --date-format "%Y-%m-%d %H:%M" \
  -1920x1080 \
  --output-framerate 60 \
  -o - \
  /path/to/repo \
| ffmpeg -y -r 60 -f image2pipe -vcodec ppm -i - \
  -c:v libx264 -preset fast -crf 18 -pix_fmt yuv420p evolution.mp4
```

#### Visual Pattern Recognition Guide

| Visual Pattern | Interpretation | Action |
|----------------|----------------|--------|
| File pulses rapidly (same color) | Thrashing on single file | Flag for trajectory analysis |
| Branch grows then fades entirely | Abandoned approach | Quantify in deletion analysis |
| Multiple areas active simultaneously | Parallel exploration | Measure coordination overhead |
| Activity narrows over time | Healthy convergence | Confirm with survival metrics |
| File color changes rapidly | Multiple agents on same file | Check for overwrites |
| Directory vanishes | Major architectural pivot | Document in abandoned paths |
| Steady outward growth | Incremental development | Baseline healthy pattern |

#### Output

- `evolution.mp4`: Full animation
- Timestamp notes of observed anomalies for Phase 2 investigation

---

### Phase 2: Survival Analysis

**Purpose**: Measure what percentage of work contributed to final state.

#### Algorithm

```
1. Extract final state: all files at HEAD
2. For each file in final state:
   - Run git blame to get commit attribution per line
   - Accumulate lines per commit
3. For each historical commit:
   - Sum lines added across all modified files
   - Compare to blamed lines in final state
   - Calculate survival rate
4. Aggregate by file type and project phase
```

#### File Type Stratification

Files have different expected survival rates. Stratify analysis:

| File Type | Patterns | Expected Survival | Anomaly If... |
|-----------|----------|-------------------|---------------|
| `docs` | readme, license, .md, docs/ | >90% | Deleted (scope changed) |
| `config` | .json, .yaml, .toml, .gitignore | >90% | High churn (tooling indecision) |
| `source` | .py, .js, .ts, .go, .rs, etc. | 40-80% | <40% or >90% |
| `test` | test, spec, __test__ | Tracks source | Deleted without source deletion |
| `asset` | .png, .jpg, .svg | High | High churn |

#### Metrics Produced

| Metric | Formula | Interpretation |
|--------|---------|----------------|
| Overall Survival Rate | `lines_in_final / lines_added` | Project efficiency |
| Zero-Survival Commit Count | Commits where survived=0 | Completely discarded work |
| Phase Survival Rates | Survival per quartile of project | Convergence trajectory |
| Exploration Cost | `lines_added - lines_in_final` | Total discarded work |

#### Expected Patterns

| Pattern | Interpretation |
|---------|----------------|
| Low early, high late | Healthy: exploration → convergence |
| High early, low late | Unhealthy: requirements changed or late panic |
| Flat throughout | No convergence strategy |
| Consistently low | Chaotic development |

---

### Phase 3: Thrashing vs Learning Differentiation

**Purpose**: Objectively distinguish productive iteration from unproductive oscillation.

#### Definition

| Behavior | Trajectory Characteristic |
|----------|--------------------------|
| **Learning** | Monotonic progress toward final state |
| **Thrashing** | Oscillation with no net progress |

#### Algorithm: Distance-to-Final Trajectory

```
For each file that exists in final state:
  1. Get final content
  2. For each commit that touched this file:
     - Get content at that commit
     - Calculate edit distance to final (0=identical, 1=completely different)
     - Record (commit_index, distance)
  3. Analyze trajectory:
     - monotonic_decreases: count of times distance decreased
     - direction_changes: count of sign changes in delta
     - net_progress: distance[0] - distance[-1]
```

#### Classification Criteria

| Metric | Learning | Thrashing | Threshold |
|--------|----------|-----------|-----------|
| Decrease Ratio | >60% | <40% | `monotonic_decreases / total_transitions` |
| Oscillation Rate | <30% | >50% | `direction_changes / (edits - 2)` |
| Net Progress | Positive | ≤0.1 | `distance[0] - distance[-1]` |

#### Algorithm: Content Oscillation Detection

Detect specific lines that appear, disappear, then reappear:

```
For each file:
  1. Track line presence across commits: line_content → [(commit_idx, present)]
  2. For each line with 3+ state records:
     - Count transitions (present↔absent)
     - If transitions >= 2: line oscillated
  3. Aggregate oscillating lines per file
```

Files with high oscillating line counts are definitively thrashing.

#### Algorithm: Cumulative Retention

Measure how long work survives:

```
For each commit at index i:
  1. Get lines added in this commit
  2. Check presence in commit at index i + N (window)
  3. Calculate retention rate: surviving_lines / added_lines
  4. Aggregate by project phase
```

| Retention Rate | Classification |
|----------------|----------------|
| >50% @ N commits | Building on work (learning) |
| <30% @ N commits | Discarding work (thrashing) |

---

### Phase 4: Coordination Analysis

**Purpose**: Identify agent coordination failures.

#### Algorithm: Thrashing Detection

```
For each file:
  1. Collect all touches: [(commit_time, commit_hash, lines_added, lines_removed)]
  2. Sort by time
  3. For consecutive touches:
     - If delta < 1 hour: thrash incident
     - If delta < 10 min AND removed > 0.5 * previous_added: rapid overwrite
```

#### Metrics Produced

| Metric | Formula | Interpretation |
|--------|---------|----------------|
| Thrash Incident Count | Consecutive edits <1hr apart | Coordination overhead |
| Thrash Hotspots | Files with most incidents | Contention points |
| Rapid Overwrite Count | Edits <10min that delete >50% of previous | Agent conflicts |

#### Expected Patterns

Healthy:
- Thrashing concentrated on interface/config files
- Source file thrashing rare
- Rapid overwrites minimal

Unhealthy:
- Source files are top thrashers
- Overwrite rate increases toward end
- Same files appear in thrashing and low-survival lists

---

### Phase 5: Abandoned Paths Analysis

**Purpose**: Quantify dead-end exploration.

#### Algorithm

```
1. Collect all files ever created (ADD events)
2. Compare to final state files
3. Abandoned = created - final
4. For each abandoned file:
   - Lifespan: deletion_date - creation_date
   - Investment: sum of lines added across all modifications
   - Modification count
```

#### Classification by Lifespan

| Lifespan | Classification | Interpretation |
|----------|----------------|----------------|
| <3 days | Immediate error | Caught fast, minimal cost |
| 3-14 days | Quick pivot | Tried briefly, abandoned |
| 14-90 days | Abandoned approach | Significant investment, didn't pan out |
| >90 days | Architectural shift | Strategic decision |

#### Metrics Produced

| Metric | Interpretation |
|--------|----------------|
| Abandoned file count by type | Which categories had most dead ends |
| Lifespan distribution | How quickly bad paths were identified |
| Investment in abandoned files | Cost of exploration |
| Replacement rate | Deleted with replacement vs without |

---

## Output Specification

### Summary Report

```
=================================================================
AI MULTI-AGENT DEVELOPMENT ANALYSIS
=================================================================

PROJECT OVERVIEW
  Commits:              4,000
  Duration:             14 days
  Avg commits/hour:     11.9
  
EFFICIENCY METRICS
  Lines added:          150,000
  Lines in final:       85,000
  Survival rate:        56.7%
  Exploration cost:     65,000 lines
  
CONVERGENCE PATTERN
  Phase 1 (0-25%):      ████████░░░░░░░░░░░░░░░░░░░░░░ 28%
  Phase 2 (25-50%):     ██████████████░░░░░░░░░░░░░░░░ 45%
  Phase 3 (50-75%):     ████████████████████░░░░░░░░░░ 67%
  Phase 4 (75-100%):    ██████████████████████████░░░░ 85%
  Verdict:              HEALTHY CONVERGENCE
  
COORDINATION QUALITY
  Thrash incidents:     342
  Rapid overwrites:     28
  Top thrash file:      src/core/engine.py (47 incidents)
  
LEARNING VS THRASHING (source files)
  Learning pattern:     156 files
  Thrashing pattern:    23 files
  Mixed pattern:        41 files
  
ABANDONED PATHS
  Files created:        890
  Files in final:       412
  Abandoned:            478 (53.7%)
  By lifespan:
    Immediate (<3d):    234
    Quick pivot (3-14d): 156
    Abandoned (14-90d): 88
    Architectural (>90d): 0
```

### Detailed Outputs

| File | Contents |
|------|----------|
| `survival_by_commit.csv` | Per-commit survival data |
| `file_trajectories.json` | Distance-to-final over time per file |
| `thrash_incidents.csv` | All thrashing events with timestamps |
| `abandoned_files.csv` | All deleted files with lifespan and investment |
| `classification_summary.json` | Learning/thrashing/mixed per file |

---

## Implementation

### Dependencies

| Tool | Purpose | Install |
|------|---------|---------|
| Gource | Visual animation | `winget install Gource` |
| ffmpeg | Video encoding | `winget install ffmpeg` |
| Python 3.10+ | Analysis scripts | - |
| PyDriller | Git traversal | `pip install pydriller` |
| Git | Blame, log access | - |

### Script Structure

```
analysis/
├── analyze.py           # Main entry point
├── survival.py          # Phase 2: Survival analysis
├── trajectory.py        # Phase 3: Learning vs thrashing
├── coordination.py      # Phase 4: Thrashing detection
├── abandoned.py         # Phase 5: Dead-end analysis
├── report.py            # Output generation
└── utils/
    ├── git_helpers.py   # Blame, file-at-commit, etc.
    └── file_classify.py # File type classification
```

### Execution

```bash
# Full analysis
python analyze.py /path/to/repo --output ./results

# Visual only
./gource.sh /path/to/repo

# Specific phase
python analyze.py /path/to/repo --phase survival
python analyze.py /path/to/repo --phase trajectory --files src/
```

---

## Interpretation Guide

### Healthy Project Indicators

- Survival rate 50-80%
- Convergence: each phase higher than previous
- Thrashing concentrated in config/interface files
- Retention rate increases over time
- Abandoned file lifespan skews toward <14 days

### Warning Signs

| Observation | Likely Cause |
|-------------|--------------|
| Flat survival across phases | No convergence strategy |
| Source files top thrashers | Poor task allocation |
| Late-stage rapid overwrites | Agents fighting at deadline |
| >70% abandoned files | Excessive exploration |
| Long-lived abandoned files | Slow failure detection |
| Low replacement rate on deletions | Features dying, not evolving |

### Quantifying Waste vs Investment

| Category | Calculation | Interpretation |
|----------|-------------|----------------|
| Pure waste | Lines in files with <3 day lifespan | Should minimize |
| Exploration cost | Lines in files with 3-14 day lifespan | Acceptable if decreasing |
| Sunk cost | Lines in files with 14-90 day lifespan | Expensive learning |
| Pivot investment | Lines in files with >90 day lifespan | Strategic decisions |

---

## Appendix: Full Analysis Script

See accompanying `analysis.py` for complete implementation.
