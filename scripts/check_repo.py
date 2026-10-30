"""Check repository documentation and files without the source deck.

This is the lightweight CI check: it does not need the 121 MB source APKG or
any generated data. The full pipeline is documented in docs/BUILDING.md.
"""

from __future__ import annotations

import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

REQUIRED = [
    "README.md",
    "CHANGELOG.md",
    "CONTRIBUTING.md",
    "LICENSE",
    "NOTICE.md",
    "requirements.txt",
    "package.json",
    "package-lock.json",
    ".gitignore",
    ".gitattributes",
    ".editorconfig",
    "docs/BUILDING.md",
    "docs/CUSTOMIZING.md",
    "docs/QUALITY.md",
    "docs/preview-front.png",
    "docs/preview-back.png",
    "source/README.md",
    "data/README.md",
    "dist/README.md",
    ".github/ISSUE_TEMPLATE/deck-correction.yml",
    ".github/ISSUE_TEMPLATE/bug-report.yml",
]

MARKDOWN = [
    ROOT / "README.md",
    ROOT / "CHANGELOG.md",
    ROOT / "CONTRIBUTING.md",
    ROOT / "NOTICE.md",
    *sorted((ROOT / "docs").glob("*.md")),
    ROOT / "source" / "README.md",
    ROOT / "data" / "README.md",
    ROOT / "dist" / "README.md",
]

LINK_RE = re.compile(r"\[[^\]]*\]\(([^)]+)\)")
EXTERNAL_PREFIXES = ("http://", "https://", "mailto:", "/")


def main() -> int:
    problems: list[str] = []

    for relative in REQUIRED:
        if not (ROOT / relative).is_file():
            problems.append(f"missing file: {relative}")

    seen: set[Path] = set()
    for path in MARKDOWN:
        if not path.is_file() or path in seen:
            continue
        seen.add(path)
        text = path.read_text(encoding="utf-8")
        for target in LINK_RE.findall(text):
            target = target.split("#", 1)[0]
            if not target or target.startswith(EXTERNAL_PREFIXES):
                continue
            if not (path.parent / target).resolve().exists():
                problems.append(
                    f"broken local link: {path.relative_to(ROOT)} -> {target}"
                )

    print(
        json.dumps(
            {
                "required_files": len(REQUIRED),
                "markdown_files": len(seen),
                "problems": problems,
            },
            ensure_ascii=False,
            indent=2,
        )
    )
    return 1 if problems else 0


if __name__ == "__main__":
    raise SystemExit(main())
