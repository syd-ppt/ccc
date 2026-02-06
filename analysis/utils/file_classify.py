"""File type classification for analysis stratification."""

import os

# Extension to category mapping
_EXT_MAP: dict[str, str] = {
    ".md": "docs",
    ".txt": "docs",
    ".rst": "docs",
    ".json": "config",
    ".yaml": "config",
    ".yml": "config",
    ".toml": "config",
    ".gitignore": "config",
    ".lock": "config",
    ".cfg": "config",
    ".ini": "config",
    ".png": "asset",
    ".jpg": "asset",
    ".jpeg": "asset",
    ".svg": "asset",
    ".ico": "asset",
    ".gif": "asset",
    ".sh": "script",
    ".bash": "script",
    ".py": "source",
    ".js": "source",
    ".ts": "source",
    ".go": "source",
    ".rs": "source",
    ".c": "source",
    ".h": "source",
    ".cpp": "source",
    ".hpp": "source",
    ".java": "source",
    ".rb": "source",
    ".zig": "source",
}


def classify_file(path: str) -> str:
    """Classify a file path into a category.

    Returns one of: docs, config, source, test, asset, script, other
    """
    basename = os.path.basename(path).lower()
    ext = os.path.splitext(path)[1].lower()

    # Test detection by path patterns
    lower_path = path.lower()
    if ("test" in lower_path or "spec" in lower_path or "__test__" in lower_path
            or "tests/" in lower_path or "test/" in lower_path):
        return "test"

    # License/readme
    if basename in ("license", "licence", "readme", "readme.md", "license.md"):
        return "docs"

    # Known extensions
    if ext in _EXT_MAP:
        return _EXT_MAP[ext]

    # .keep files
    if basename == ".keep":
        return "config"

    return "other"
