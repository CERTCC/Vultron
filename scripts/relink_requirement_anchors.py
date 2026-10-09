"""Point docs citations of spec anchors at the kind page that renders them.

Two passes over every ``docs/**/*.md``:

1. **Requirement citations linking a group anchor.** Before the ``anchor_ids``
   MkDocs hook (#3735), a ``<a id="mv-03-002">`` printed by the spec renderer's
   exec block was invisible to ``mkdocs build --strict``, so every prose
   citation of a single requirement linked its *group* heading instead:
   ``[MV-03-002](../specs/protocol.md#mv-03)``. With the hook in place the
   requirement's own anchor is a valid target, so each such link — link text a
   single requirement ID, href a group anchor on a spec kind page — is
   repointed at ``#mv-03-002``.

2. **Any link whose anchor does not render on the page it names.** A
   requirement, group or file anchor appears only on the page(s) of the kinds
   its items carry (SR-09-001, SR-09-002), so a ``kind:`` relabel (the MS-12
   passes, #3600) silently moves the anchor to another page and every prose
   link to it dangles. This pass rewrites the page slug to the one the anchor
   renders on — for a group or file that straddles pages, the page holding the
   most of its items.

Both passes read the spec registry; an anchor the registry does not know is
reported and left untouched.

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
from vultron.metadata.specs.schema import SpecKind  # noqa: E402

_SLUGS = "|".join(sorted(_KIND_SLUG.values()))

#: ``[XX-NN-NNN](<prefix>specs/<slug>.md#xx-nn)`` — a requirement ID as link
#: text, a group anchor on a spec kind page as href.
_GROUP_LINK_RE = re.compile(
    r"\[(?P<id>[A-Z][A-Z0-9]{1,7}-\d{2}-\d{3})\]"
    r"\((?P<prefix>[^)#\s]*?)specs/(?P<slug>" + _SLUGS + r")\.md"
    r"#(?P<group>[a-z0-9]+-\d{2})\)"
)

#: ``(<prefix>specs/<slug>.md#anchor)`` — any link into a spec kind page whose
#: anchor is a file (``xx``), group (``xx-nn``) or requirement (``xx-nn-nnn``)
#: ID, regardless of link text.
_KIND_PAGE_LINK_RE = re.compile(
    r"\((?P<prefix>[^)#\s]*?)specs/(?P<slug>" + _SLUGS + r")\.md"
    r"#(?P<anchor>[a-z][a-z0-9]{1,7}(?:-\d{2}(?:-\d{3}[a-z]?)?)?)\)"
)

#: Tie-break for a group or file whose items are split evenly across pages.
_KIND_ORDER = [_KIND_SLUG[k] for k in SpecKind]


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


class _Rerouter:
    """Move a kind-page link to the page its anchor renders on (pass 2)."""

    def __init__(self, registry: SpecRegistry) -> None:
        # anchor -> {slug: item count} for every file, group and requirement ID
        pages: dict[str, Counter[str]] = {}
        for spec_file in registry.files:
            for group in spec_file.groups:
                for spec in group.specs:
                    slug = _KIND_SLUG[spec.kind]
                    for anchor in (
                        spec_file.id.lower(),
                        group.id.lower(),
                        spec.id.lower(),
                    ):
                        pages.setdefault(anchor, Counter())[slug] += 1
        self._pages = pages
        self.unknown: Counter[str] = Counter()
        self.rerouted = 0

    def _page_for(self, anchor: str) -> str | None:
        counts = self._pages.get(anchor)
        if not counts:
            return None
        best = max(counts.values())
        return next(s for s in _KIND_ORDER if counts.get(s) == best)

    def __call__(self, match: re.Match[str]) -> str:
        anchor = match.group("anchor")
        counts = self._pages.get(anchor)
        if counts is None:
            self.unknown[anchor] += 1
            return match.group(0)
        slug = match.group("slug")
        if slug in counts:
            return match.group(0)
        target = self._page_for(anchor)
        self.rerouted += 1
        return f"({match.group('prefix')}specs/{target}.md#{anchor})"


def main(argv: list[str]) -> int:
    check = "--check" in argv
    registry = load_registry()
    repoint = _Repointer(registry)
    reroute = _Rerouter(registry)
    changed_files = 0

    for path in sorted(DOCS_DIR.rglob("*.md")):
        before = path.read_text(encoding="utf-8")
        after = _GROUP_LINK_RE.sub(repoint, before)
        after = _KIND_PAGE_LINK_RE.sub(reroute, after)
        if after != before:
            changed_files += 1
            print(f"{path.relative_to(ROOT)}")
            if not check:
                path.write_text(after, encoding="utf-8")

    print(
        f"{repoint.rewritten} requirement link(s) repointed at their own "
        f"anchor, {repoint.rerouted} of them moved to a different kind page; "
        f"{reroute.rerouted} link(s) moved to the page their anchor renders "
        f"on; {changed_files} file(s) changed"
    )
    for spec_id, count in sorted(repoint.unknown.items()):
        print(f"unknown requirement left as-is: {spec_id} ({count})")
    for anchor, count in sorted(reroute.unknown.items()):
        print(f"unknown anchor left as-is: #{anchor} ({count})")
    if check and changed_files:
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
