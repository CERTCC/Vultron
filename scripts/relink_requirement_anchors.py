"""One-shot rewrite: point requirement citations at their own spec anchors.

Before the ``anchor_ids`` MkDocs hook (#3735), a ``<a id="mv-03-002">`` printed
by the spec renderer's exec block was invisible to ``mkdocs build --strict``,
so every prose citation of a single requirement linked its *group* heading
instead: ``[MV-03-002](../specs/protocol.md#mv-03)``. With the hook in place
the requirement's own anchor is a valid target, so this script repoints each
such link — link text a single requirement ID, href a group anchor on a spec
kind page — at ``#mv-03-002``.

The target page is the requirement's *effective kind* page (SR-09-002 routes an
item to its own kind's page only), read from the spec registry, so a link that
cited a group on one kind page for a requirement that lives on another is
corrected at the same time rather than left dangling. A requirement ID the
registry does not know is reported and left untouched.

Usage:
    uv run python scripts/relink_requirement_anchors.py [--check]

``--check`` reports what would change and exits 1 if anything would, without
writing.
"""

from __future__ import annotations

import re
import sys
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DOCS_DIR = ROOT / "docs"
sys.path.insert(0, str(ROOT))

from vultron.metadata.specs.docs_render import _KIND_SLUG  # noqa: E402
from vultron.metadata.specs.registry import (  # noqa: E402
    SpecRegistry,
    load_registry,
)

_SLUGS = "|".join(sorted(_KIND_SLUG.values()))

#: ``[XX-NN-NNN](<prefix>specs/<slug>.md#xx-nn)`` — a requirement ID as link
#: text, a group anchor on a spec kind page as href.
_GROUP_LINK_RE = re.compile(
    r"\[(?P<id>[A-Z][A-Z0-9]{1,7}-\d{2}-\d{3})\]"
    r"\((?P<prefix>[^)#\s]*?)specs/(?P<slug>" + _SLUGS + r")\.md"
    r"#(?P<group>[a-z0-9]+-\d{2})\)"
)


class _Repointer:
    """Rewrite one matched group-anchor citation; keep the running tallies."""

    def __init__(self, registry: SpecRegistry) -> None:
        self._registry = registry
        self.unknown: Counter[str] = Counter()
        self.rewritten = 0
        self.rerouted = 0

    def __call__(self, match: re.Match[str]) -> str:
        spec_id = match.group("id")
        if match.group("group") != spec_id.lower().rsplit("-", 1)[0]:
            return match.group(0)  # not this requirement's group anchor
        try:
            kind = self._registry.get_effective_kind(spec_id)
        except KeyError:
            self.unknown[spec_id] += 1
            return match.group(0)
        slug = _KIND_SLUG[kind]
        if slug != match.group("slug"):
            self.rerouted += 1
        self.rewritten += 1
        prefix = match.group("prefix")
        return f"[{spec_id}]({prefix}specs/{slug}.md#{spec_id.lower()})"


def main(argv: list[str]) -> int:
    check = "--check" in argv
    repoint = _Repointer(load_registry())
    changed_files = 0

    for path in sorted(DOCS_DIR.rglob("*.md")):
        before = path.read_text(encoding="utf-8")
        after = _GROUP_LINK_RE.sub(repoint, before)
        if after != before:
            changed_files += 1
            print(f"{path.relative_to(ROOT)}")
            if not check:
                path.write_text(after, encoding="utf-8")

    print(
        f"{repoint.rewritten} link(s) repointed in {changed_files} file(s); "
        f"{repoint.rerouted} moved to a different kind page"
    )
    for spec_id, count in sorted(repoint.unknown.items()):
        print(f"unknown requirement left as-is: {spec_id} ({count})")
    if check and changed_files:
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
