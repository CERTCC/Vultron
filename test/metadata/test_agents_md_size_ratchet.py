#!/usr/bin/env python

#  Copyright (c) 2026 Carnegie Mellon University and Contributors.
#  - see Contributors.md for a full list of Contributors
#  - see ContributionInstructions.md for information on how you can Contribute to this project
#  Vultron Multiparty Coordinated Vulnerability Disclosure Protocol Prototype is
#  licensed under a MIT (SEI)-style license, please see LICENSE.md distributed
#  with this Software or contact permission@sei.cmu.edu for full terms.
#  Created, in part, with funding and support from the United States Government
#  (see Acknowledgments file). This program may include and/or can make use of
#  certain third party source code, object code, documentation and other files
#  ("Third Party Software"). See LICENSE.md for more details.
#  Carnegie Mellon®, CERT® and CERT Coordination Center® are registered in the
#  U.S. Patent and Trademark Office by Carnegie Mellon University
"""Ratchet: AGENTS.md files stay within their documented size targets.

``notes/agents-md-structure.md`` sets **400 lines** for root ``AGENTS.md`` and
**200 lines** for a per-directory one.  Those targets went unenforced, so root
reached 1166 lines — 2.9x its target — before anyone noticed (ISSUE-2954).

Size matters here because ``orient-agent`` loads root ``AGENTS.md`` at the start
of every workflow skill.  Past the point where an agent reliably reads it end to
end, additional pitfalls stop protecting against the mistakes they describe, so
an unbounded guidance file silently stops working while still costing context on
every session.

Two files are over the per-directory target and are recorded in
:data:`KNOWN_OVERAGE`.  Those ceilings may only be **lowered**: run the
``condense-agents-md`` skill on the file rather than raising its entry.

Lives in ``test/metadata/`` alongside the other markdown and frontmatter checks
rather than in ``test/architecture/``, whose hygiene ratchet (TB-13-003) requires
file discovery to route through the Python-source corpus in ``_corpus.py``.

Source: ISSUE-2954.
"""

from pathlib import Path

import pytest

_REPO_ROOT = Path(__file__).parents[2]

ROOT_TARGET = 400
PER_DIRECTORY_TARGET = 200

# Per-directory files that predate this ratchet and exceed the 200-line target.
# Lower these as the files are condensed; never raise one.  Adding a new entry
# means the ratchet failed to do its job.
KNOWN_OVERAGE: dict[str, int] = {
    "vultron/core/AGENTS.md": 251,
    "vultron/core/behaviors/AGENTS.md": 209,
}

# Directories whose AGENTS.md files are agent-tooling copies, not repo guidance.
_EXCLUDED_DIRS = (".git", ".agents", ".claude", "node_modules", ".venv")


def _agents_md_files() -> list[Path]:
    return sorted(
        p
        for p in _REPO_ROOT.rglob("AGENTS.md")
        if not any(
            part in _EXCLUDED_DIRS for part in p.relative_to(_REPO_ROOT).parts
        )
    )


def _line_count(path: Path) -> int:
    return len(path.read_text(encoding="utf-8").splitlines())


def test_root_agents_md_within_target() -> None:
    """Root AGENTS.md MUST stay at or below its documented 400-line target."""
    count = _line_count(_REPO_ROOT / "AGENTS.md")
    assert count <= ROOT_TARGET, (
        f"Root AGENTS.md is {count} lines, over the {ROOT_TARGET}-line target "
        f"documented in notes/agents-md-structure.md. Run the "
        f"condense-agents-md skill; do not raise the target here."
    )


@pytest.mark.parametrize(
    "rel_path",
    [
        pytest.param(
            str(p.relative_to(_REPO_ROOT)), id=str(p.relative_to(_REPO_ROOT))
        )
        for p in _agents_md_files()
        if p != _REPO_ROOT / "AGENTS.md"
    ],
)
def test_per_directory_agents_md_within_target(rel_path: str) -> None:
    """Each per-directory AGENTS.md stays within 200 lines, or its recorded ceiling."""
    count = _line_count(_REPO_ROOT / rel_path)
    ceiling = KNOWN_OVERAGE.get(rel_path, PER_DIRECTORY_TARGET)
    assert count <= ceiling, (
        f"{rel_path} is {count} lines, over its {ceiling}-line ceiling. "
        f"Run condense-agents-md on it — migrate content to notes/ or a "
        f"deeper per-directory AGENTS.md. Do not raise the ceiling."
    )


def test_known_overage_entries_are_still_needed() -> None:
    """A KNOWN_OVERAGE entry that no longer exceeds the target MUST be removed.

    Keeps the ratchet honest: once a file is condensed under 200 lines its
    exemption is stale and would silently permit regrowth back to the old
    ceiling.
    """
    stale = {
        rel: (_line_count(_REPO_ROOT / rel), ceiling)
        for rel, ceiling in KNOWN_OVERAGE.items()
        if (_REPO_ROOT / rel).exists()
        and _line_count(_REPO_ROOT / rel) <= PER_DIRECTORY_TARGET
    }
    assert not stale, (
        f"These files no longer exceed the {PER_DIRECTORY_TARGET}-line target; "
        f"remove their KNOWN_OVERAGE entries: {stale}"
    )


def test_known_overage_entries_exist() -> None:
    """A KNOWN_OVERAGE entry for a deleted or moved file MUST be removed."""
    missing = [rel for rel in KNOWN_OVERAGE if not (_REPO_ROOT / rel).exists()]
    assert (
        not missing
    ), f"KNOWN_OVERAGE names files that do not exist: {missing}"
