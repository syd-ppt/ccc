"""Git command helpers for deep analysis."""

import subprocess
from pathlib import Path

REPO_PATH = Path(r"D:\projects\ccc\repo")


def git(*args: str, timeout: int = 120) -> str:
    """Run a git command in the repo and return stdout."""
    result = subprocess.run(
        ["git", "-C", str(REPO_PATH), *args],
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        timeout=timeout,
    )
    if result.returncode != 0:
        raise RuntimeError(f"git {' '.join(args[:3])}... failed: {result.stderr[:500]}")
    return result.stdout


def file_at_commit(commit_hash: str, file_path: str) -> str:
    """Get file contents at a specific commit."""
    return git("show", f"{commit_hash}:{file_path}")


def blame_file(file_path: str) -> list[tuple[str, str]]:
    """Run git blame --porcelain on a file at HEAD.

    Returns list of (commit_hash, line_content) tuples.
    """
    raw = git("blame", "--porcelain", "HEAD", "--", file_path, timeout=60)
    lines = raw.split("\n")

    result = []
    current_hash = None
    for line in lines:
        if line.startswith("\t"):
            # Content line
            if current_hash:
                result.append((current_hash, line[1:]))
        else:
            parts = line.split()
            if parts and len(parts[0]) == 40:
                current_hash = parts[0]

    return result


def list_files_at_head() -> list[str]:
    """List all files in the repo at HEAD."""
    raw = git("ls-tree", "-r", "--name-only", "HEAD")
    return [line for line in raw.strip().split("\n") if line]


def commits_touching_file(file_path: str) -> list[str]:
    """Get list of commit hashes that modified a file, oldest first."""
    raw = git("log", "--reverse", "--format=%H", "--follow", "--", file_path)
    return [h for h in raw.strip().split("\n") if h]
