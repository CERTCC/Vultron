"""Point every docs/ link to a requirement at the page that defines its anchor.

A requirement, group or file anchor is defined only where its items render: a
``protocol`` or ``foundation`` item on its Requirements Catalog page in the
Protocol Specification, any other kind on its per-kind page under
``docs/reference/specs/`` (SR-09-001, SR-09-002, DF-12-002). A ``kind:``
relabel, or a change to the catalog placement table, moves the anchor and
every prose link to the old page dangles. This script rewrites those links;
the rules are in :mod:`vultron.metadata.docs.requirement_links`, which the
``test/metadata/docs/test_requirement_links.py`` gate also applies to the
whole tree.

Usage:
    uv run python scripts/relink_requirement_anchors.py [--check]

``--check`` reports what would change and exits 1 if anything would, without
writing.
"""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DOCS_DIR = ROOT / "docs"
sys.path.insert(0, str(ROOT))

from vultron.metadata.docs.requirement_links import (  # noqa: E402
    RelinkStats,
    RequirementLinker,
)
from vultron.metadata.specs.registry import load_registry  # noqa: E402


def main(argv: list[str]) -> int:
    check = "--check" in argv
    linker = RequirementLinker(load_registry())
    stats = RelinkStats()
    changed_files = 0

    for path in sorted(DOCS_DIR.rglob("*.md")):
        before = path.read_text(encoding="utf-8")
        after, file_stats = linker.relink(
            before, path.relative_to(DOCS_DIR).as_posix()
        )
        stats.add(file_stats)
        if after != before:
            changed_files += 1
            print(f"{path.relative_to(ROOT)}")
            if not check:
                path.write_text(after, encoding="utf-8")

    print(
        f"{stats.repointed} requirement link(s) repointed at their own "
        f"anchor; {stats.moved} link(s) moved to the page their anchor "
        f"renders on; {changed_files} file(s) changed"
    )
    for name, count in sorted(stats.unknown.items()):
        print(f"unknown anchor left as-is: {name} ({count})")
    if check and changed_files:
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
