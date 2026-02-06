"""Main entry point for deep analysis (Phases 2-5 from the spec)."""

import argparse
import sys

from analysis.report import build_header, combine_reports


PHASES = {
    "survival": "Phase 2: Survival Analysis (git blame)",
    "trajectory": "Phase 3: Trajectory / Learning vs Thrashing",
    "coordination": "Phase 4: Coordination / Thrashing Detection",
    "abandoned": "Phase 5: Abandoned Paths",
}


def run_phase(phase: str) -> str:
    if phase == "survival":
        from analysis.survival import run_survival_analysis, format_survival_report
        data = run_survival_analysis()
        return format_survival_report(data)
    elif phase == "trajectory":
        from analysis.trajectory import run_trajectory_analysis, format_trajectory_report
        results = run_trajectory_analysis()
        return format_trajectory_report(results)
    elif phase == "coordination":
        from analysis.coordination import run_coordination_analysis, format_coordination_report
        data = run_coordination_analysis()
        return format_coordination_report(data)
    elif phase == "abandoned":
        from analysis.abandoned import run_abandoned_analysis, format_abandoned_report
        data = run_abandoned_analysis()
        return format_abandoned_report(data)
    else:
        raise ValueError(f"Unknown phase: {phase}")


def main() -> None:
    parser = argparse.ArgumentParser(description="Deep analysis of AI-authored git repository")
    parser.add_argument(
        "--phase",
        choices=list(PHASES.keys()) + ["all"],
        default="all",
        help="Which analysis phase to run (default: all)",
    )
    parser.add_argument(
        "--output",
        default=r"D:\projects\ccc\deep_analysis_report.txt",
        help="Output file path",
    )
    args = parser.parse_args()

    phases_to_run = list(PHASES.keys()) if args.phase == "all" else [args.phase]

    sections = [build_header()]
    for phase in phases_to_run:
        print(f"\n{'='*60}")
        print(f"Running {PHASES[phase]}...")
        print(f"{'='*60}")
        report = run_phase(phase)
        sections.append(report)
        print(report)

    full_report = "\n\n".join(sections)
    with open(args.output, "w", encoding="utf-8") as f:
        f.write(full_report)
    print(f"\nFull report written to {args.output}")


if __name__ == "__main__":
    main()
