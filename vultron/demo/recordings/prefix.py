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

"""The shared-prefix check over the committed recordings (DEMOCI-11-017/018).

Two scenarios whose declared paths share a prefix run the same story up to the
branch point where the paths part, so their recorded ledgers must be
**byte-identical** up to that point (DEMOCI-11-017, DEMOCI-11-018).  Every
scenario is written as composition, so each shared stretch is one copy of the
code running on one fixed cast under one seed (DEMOCI-11-020, DEMOCI-11-025):
identical bytes hold by construction, and nothing about the comparison is
scoped to a declared subset of the tree — :func:`shared_prefixes` returns every
pair of registered scenarios and every one of them is compared.

A pair that parts at the root shares no ledger entries, because the root branch
point is decided before the case exists.  Its comparison is therefore true of
an empty prefix; what carries the check is the pairs that part later.

Where a branch point falls in a ledger is recorded by the run:
:func:`~vultron.demo.helpers.story.run_story` reports each choice of the story
to the harness, which records the ledger tail there
(:mod:`vultron.demo.helpers.harness`).  The recorder commits those marks beside
each recording (:mod:`.layout`).

Design: ``notes/demo-scenario-tree.md`` § "Shared-prefix check"; what a shared
stretch must satisfy for byte identity to hold is § "Composition" of the same
note.
"""

from collections.abc import Sequence
from dataclasses import dataclass
from itertools import combinations

from vultron.demo.recordings.layout import Recording
from vultron.demo.scenario.tree import PathStep, TreeNode
from vultron.errors import DemoRecordingError


@dataclass(frozen=True)
class SharedPrefix:
    """Two scenarios whose paths agree for :attr:`depth` steps, then part.

    Attributes:
        first: The scenario that comes first in name order.
        second: The other scenario.
        depth: The number of leading steps the two paths share.  The paths
            part at step ``depth``, which names the same branch point in both
            and a different choice in each.
    """

    first: str
    second: str
    depth: int

    @property
    def id(self) -> str:
        """A test id, e.g. ``rv~rvv@1``."""
        return f"{self.first}~{self.second}@{self.depth}"


def shared_prefixes(root: TreeNode) -> list[SharedPrefix]:
    """Return every pair of scenarios on *root*, with where their paths part.

    Every two scenarios share at least the root, so every pair is returned; a
    pair that parts at the root shares an empty prefix.
    """
    paths = {
        name: node.prefix for name, node in sorted(root.endings().items())
    }
    return [
        SharedPrefix(first, second, _common_depth(paths[first], paths[second]))
        for first, second in combinations(paths, 2)
    ]


def prefix_lines(recording: Recording, depth: int) -> list[str]:
    """Return the ledger lines of *recording* before its step at *depth*.

    The step at *depth* is where the pair's paths part, so its mark is the
    branch point's place in this ledger.

    ``depth`` indexes the marks, and it is in range because two rules in other
    modules hold: no registered path equals or is a strict prefix of another
    (DEMOCI-11-023, :func:`~vultron.demo.scenario.tree.build_scenario_tree`),
    so a shared depth is shorter than either path; and a recording is kept only
    with one mark per declared step
    (:func:`~vultron.demo.recordings.ledgers.parse_step_marks`), so the marks
    are as many as the path's steps.  Checked here rather than left to an
    ``IndexError``, because relaxing either rule should name the scenario that
    stopped satisfying it.

    Raises:
        DemoRecordingError: When *recording* holds no mark at *depth*.
    """
    if depth >= len(recording.steps):
        raise DemoRecordingError(
            f"scenario {recording.scenario!r} was asked for the ledger before "
            f"step {depth}, but it marked only {len(recording.steps)} step(s). "
            "A shared depth is shorter than either path (DEMOCI-11-023) and "
            "every declared step is marked, so one of those no longer holds."
        )
    return recording.entries[: recording.steps[depth].ledger_tail]


def pair_byte_mismatch(
    pair: SharedPrefix, first: Recording, second: Recording
) -> str | None:
    """Compare *pair*'s recordings byte for byte up to its branch point.

    The check every pair of registered scenarios gets (DEMOCI-11-017,
    DEMOCI-11-018).
    """
    return byte_mismatch(
        prefix_lines(first, pair.depth), prefix_lines(second, pair.depth)
    )


def _common_depth(
    first: Sequence[PathStep], second: Sequence[PathStep]
) -> int:
    depth = 0
    while (
        depth < min(len(first), len(second)) and first[depth] == second[depth]
    ):
        depth += 1
    return depth


def byte_mismatch(first: Sequence[str], second: Sequence[str]) -> str | None:
    """Describe where two ledger prefixes stop being byte-identical, if they do.

    Args:
        first: The JSONL lines of one prefix.
        second: The JSONL lines of the other.

    Returns:
        ``None`` when the prefixes are byte-identical (DEMOCI-11-018);
        otherwise a description naming the first line that differs.
    """
    for index, (a, b) in enumerate(zip(first, second, strict=False)):
        if a != b:
            column = next(
                (
                    i
                    for i, (x, y) in enumerate(zip(a, b, strict=False))
                    if x != y
                ),
                min(len(a), len(b)),
            )
            return f"entry {index} differs from byte {column} on."
    if len(first) != len(second):
        return f"the prefixes hold {len(first)} and {len(second)} entries."
    return None


__all__ = [
    "SharedPrefix",
    "byte_mismatch",
    "pair_byte_mismatch",
    "prefix_lines",
    "shared_prefixes",
]
