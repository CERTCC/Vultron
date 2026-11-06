"""The requirement file every throwaway ``docs-site`` checkout needs.

``uv run docs-site`` generates the Protocol Specification's known-gaps
fragment from the coverage state of each ``protocol`` and ``foundation``
requirement (DF-12-019), and it refuses a registry that holds none, since the
fragment would then read as no gaps (DF-09-009). A test tree built for another
artifact writes :data:`SEED_SPECS` through :func:`write_seed_specs`.

One requirement is enough. Its file is one a Requirements Catalog page
places, and a tree with no ``test/`` directory marks no test for it, so it
renders as untested. A test about the fragment itself builds its own
registry (``test_known_gaps.py``).
"""

from __future__ import annotations

from pathlib import Path

#: The one requirement ID the seed registry holds.
SEED_SPEC_ID = "VP-01-001"

#: Repository-relative files: one ``VP`` requirement file, which the
#: ``vultron-protocol`` catalog page places.
SEED_SPECS: dict[str, str] = {
    "specs/vultron-protocol-spec.yaml": f"""\
id: VP
title: Vultron Protocol
description: >-
  A seed requirement file for docs-site test trees.
scope:
- prototype
tags:
- protocol
groups:
- id: VP-01
  title: Seed
  specs:
  - id: {SEED_SPEC_ID}
    priority: SHOULD
    kind: protocol
    statement: >-
      Participants SHOULD track the state of other Participants in a case.
    rationale: >-
      A seed requirement, so the known-gaps fragment has one to list.
"""
}


def write_seed_specs(root: Path) -> None:
    """Write :data:`SEED_SPECS` under *root*, keeping a file already there."""
    for rel, text in SEED_SPECS.items():
        path = root / rel
        if path.exists():
            continue
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text, encoding="utf-8")
