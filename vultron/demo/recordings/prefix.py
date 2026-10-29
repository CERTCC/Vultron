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
branch point where the paths part, so their recorded ledgers must agree up to
that point.  The agreement is checked the way position-independent code is
compared: same logic, different addresses.

- **Isomorphism** (DEMOCI-11-017).  Each ledger prefix has its ids relabeled
  in order of first appearance and its timestamps removed; the two results
  must then be equal.  One relabeling covers the whole prefix, so a reference
  between objects must map the same way everywhere it occurs.
- **Byte identity** (DEMOCI-11-018).  A family written as composition (#4733)
  shares one copy of the prefix code, so its recordings must agree byte for
  byte up to the branch point.  :data:`COMPOSED_FAMILIES` names those
  families.

Where a branch point falls in a ledger is recorded by the run: each scenario
reports reaching each declared step to its harness, which records the ledger
tail there (:mod:`vultron.demo.helpers.harness`).  The recorder commits those
marks beside each recording (:mod:`.layout`).

Design: ``notes/demo-scenario-tree.md`` § "Shared-prefix check".
"""

import json
import re
from collections.abc import Iterable, Mapping, Sequence
from dataclasses import dataclass
from itertools import combinations

from vultron.demo.scenario.tree import PathStep, TreeNode

#: A string that names an object, wherever it occurs in an entry: an actor or
#: other URL, a ``urn:uuid:`` id, a bare UUID, the actor part of a
#: participant id (``<case>/participants/<uuid or actor slug>``: ``rcvcv``
#: seeds named actor ids where its siblings seed UUIDs), or a SHA-256 hex
#: digest (``entryHash``, ``prevLogHash``).  Each one is relabeled by first
#: appearance, including inside a longer string such as an activity ``name``
#: and in a mapping key such as an ``actorParticipantIndex`` entry.
_ID_RE = re.compile(
    r"https?://[^\s\"']+"
    r"|urn:uuid:[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}"
    r"|[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}"
    r"|(?<=/participants/)[A-Za-z0-9._~-]+"
    r"|\b[0-9a-f]{64}\b"
)

#: An ISO 8601 timestamp.  Timestamps are excluded from the comparison
#: (DEMOCI-11-017): the recording clock steps on every read, so two scenarios
#: that do the same thing after different amounts of setup stamp it differently.
_TIMESTAMP_RE = re.compile(
    r"\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(?:\.\d+)?(?:Z|[+-]\d{2}:\d{2})?"
)

_TIMESTAMP = "<timestamp>"

#: Scenario families written as composition (#4733), each the names of its
#: scenarios.  Every two scenarios in one family must be byte-identical up to
#: the branch point where their paths part (DEMOCI-11-018).  Empty because no
#: family is composed yet: until one is, every sibling pair seeds its own
#: actor names, container slots and ports, so only isomorphism can hold.
COMPOSED_FAMILIES: tuple[frozenset[str], ...] = ()


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


def _common_depth(
    first: Sequence[PathStep], second: Sequence[PathStep]
) -> int:
    depth = 0
    while (
        depth < min(len(first), len(second)) and first[depth] == second[depth]
    ):
        depth += 1
    return depth


def relabeled(entries: Iterable[Mapping[str, object]]) -> list[object]:
    """Return *entries* with ids relabeled by first appearance, sans timestamps.

    One relabeling spans every entry, so two ledgers relabel to equal values
    exactly when one consistent renaming of ids turns one into the other.
    Mapping keys are relabeled too, and are visited in document order, the
    order the recorder wrote them, so first appearance does not depend on how
    the original ids sort.
    """
    labels: dict[str, str] = {}

    def label(match: re.Match[str]) -> str:
        return labels.setdefault(match.group(0), f"<id {len(labels)}>")

    def text(value: str) -> str:
        return _ID_RE.sub(label, _TIMESTAMP_RE.sub(_TIMESTAMP, value))

    def walk(value: object) -> object:
        if isinstance(value, Mapping):
            return {text(str(key)): walk(item) for key, item in value.items()}
        if isinstance(value, list):
            return [walk(item) for item in value]
        if isinstance(value, str):
            return text(value)
        return value

    return [walk(entry) for entry in entries]


def isomorphism_mismatch(
    first: Sequence[Mapping[str, object]],
    second: Sequence[Mapping[str, object]],
) -> str | None:
    """Describe where two ledger prefixes stop being isomorphic, if they do.

    Returns:
        ``None`` when the prefixes are isomorphic (DEMOCI-11-017); otherwise
        a description naming the first entry that differs.
    """
    first_form, second_form = relabeled(first), relabeled(second)
    for index, (a, b) in enumerate(zip(first_form, second_form, strict=False)):
        if a != b:
            return (
                f"entry {index} differs after relabeling ids by first "
                f"appearance: {_differing_keys(a, b)}"
            )
    if len(first) != len(second):
        return (
            f"the prefixes hold {len(first)} and {len(second)} entries; "
            "one scenario commits more before the branch point."
        )
    return None


def _differing_keys(first: object, second: object) -> str:
    """Name the top-level fields of two entries that differ, with both values."""
    if not (isinstance(first, Mapping) and isinstance(second, Mapping)):
        return f"{_short(first)} vs {_short(second)}"
    keys = [
        key
        for key in dict.fromkeys([*first, *second])
        if first.get(key) != second.get(key)
    ]
    return "; ".join(
        f"{key}: {_short(first.get(key))} vs {_short(second.get(key))}"
        for key in keys
    )


def _short(value: object, limit: int = 160) -> str:
    rendered = json.dumps(value, sort_keys=True)
    return rendered if len(rendered) <= limit else rendered[:limit] + "…"


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
    "COMPOSED_FAMILIES",
    "SharedPrefix",
    "byte_mismatch",
    "isomorphism_mismatch",
    "relabeled",
    "shared_prefixes",
]
