"""Report generation — combines all phase outputs into a single report."""

import datetime


def build_header() -> str:
    now = datetime.datetime.now().strftime("%Y-%m-%d %H:%M")
    return (
        "=" * 70 + "\n"
        "AI MULTI-AGENT DEVELOPMENT ANALYSIS\n"
        "claudes-c-compiler (anthropics/claudes-c-compiler)\n"
        f"Generated: {now}\n"
        "=" * 70 + "\n"
    )


def combine_reports(*sections: str) -> str:
    """Combine multiple report sections into one document."""
    return build_header() + "\n\n".join(sections)
