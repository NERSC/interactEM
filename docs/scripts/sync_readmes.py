"""Sync top-level README files from docs content.

Edit the Markdown files under ``docs/source`` and run this script to
materialize matching README files in the repository. Sections wrapped in
``<!-- docs-only:start -->`` … ``<!-- docs-only:end -->`` are stripped
from the generated README output.
"""

from __future__ import annotations

import argparse
import re
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[2]
DOCS_ROOT = PROJECT_ROOT / "docs"
DOCS_SOURCE = DOCS_ROOT / "source"

README_MAPPINGS = {
    DOCS_SOURCE / "introduction.md": PROJECT_ROOT / "README.md",
    DOCS_SOURCE / "authoring-operators.md": PROJECT_ROOT / "operators" / "README.md",
    DOCS_SOURCE / "launch-agent.md": PROJECT_ROOT / "backend" / "agent" / "README.md",
}

DOCS_ONLY = re.compile(
    r"<!--\s*docs-only:start\s*-->.*?<!--\s*docs-only:end\s*-->",
    flags=re.IGNORECASE | re.DOTALL,
)
LINK = re.compile(r"(\[[^\]]+\])\(([^)]+)\)")


def _strip_blocks(text: str) -> str:
    """Remove docs-only sections."""
    return DOCS_ONLY.sub("", text)


def _rewrite_links(text: str, source_path: Path) -> str:
    """Rewrite relative links so they make sense from the repository root."""

    def replace(match: re.Match[str]) -> str:
        label, target = match.groups()

        if target.startswith("#") or "://" in target or target.startswith("mailto:") or target.startswith("tel:"):
            return match.group(0)

        base, anchor = target.split("#", maxsplit=1) if "#" in target else (target, "")
        resolved = (source_path.parent / base).resolve()

        try:
            resolved_relative = resolved.relative_to(PROJECT_ROOT)
        except ValueError:
            return match.group(0)

        new_target = resolved_relative.as_posix()
        if anchor:
            new_target = f"{new_target}#{anchor}"
        return f"{label}({new_target})"

    return LINK.sub(replace, text)


def render_readme(source_path: Path) -> str:
    content = source_path.read_text(encoding="utf-8")
    content = _strip_blocks(content)
    content = _rewrite_links(content, source_path)
    content = content.strip() + "\n"

    header = (
        f"<!-- Generated from {source_path.relative_to(PROJECT_ROOT)} "
        f"using docs/scripts/sync_readmes.py. Do not edit directly. -->\n\n"
    )
    return header + content


def sync_readmes(check: bool = False) -> list[Path]:
    changed: list[Path] = []

    for source, target in README_MAPPINGS.items():
        rendered = render_readme(source)
        current = target.read_text(encoding="utf-8") if target.exists() else ""

        if rendered != current:
            if not check:
                target.write_text(rendered, encoding="utf-8")
            changed.append(target)

    return changed


def main() -> int:
    parser = argparse.ArgumentParser(description="Sync README files from docs content.")
    parser.add_argument("--check", action="store_true", help="Only check if files would change.")
    args = parser.parse_args()

    changed = sync_readmes(check=args.check)

    if args.check and changed:
        for target in changed:
            print(f"Would update: {target.relative_to(PROJECT_ROOT)}")
        return 1

    if changed:
        for target in changed:
            print(f"Updated: {target.relative_to(PROJECT_ROOT)}")
    else:
        print("README files are up to date.")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
