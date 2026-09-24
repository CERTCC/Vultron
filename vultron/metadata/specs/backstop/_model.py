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
"""Constants and data types shared by the ``spec-backstop`` modules."""

from __future__ import annotations

from collections.abc import Callable, Sequence
from dataclasses import dataclass, field

SOURCE_PREFIX = "vultron/"
TEST_PREFIX = "test/"
MAX_EVIDENCE = 3
#: A changed symbol imported by more test files than this is a hub: its
#: import hits go to INFO, because nearly every test would otherwise be MUST.
HUB_THRESHOLD = 10
#: A test file carrying markers for more groups than this is a whole-subsystem
#: suite, not a test of one contract; its markers go to INFO. The median test
#: file here spans 2 groups and the 90th percentile spans 6.
MONOLITH_GROUP_SPAN = 8

GitRunner = Callable[[Sequence[str]], str]


class BackstopError(Exception):
    """Setup failure: not a repository, bad ref, unreadable manifest."""


# ---------------------------------------------------------------------------
# Data
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class FileChange:
    """A changed ``.py`` file; ``lines=None`` means the whole file changed."""

    path: str
    source: str | None
    lines: frozenset[int] | set[int] | None = None


@dataclass(frozen=True)
class TestFile:
    """What one ``test_*.py`` file imports from ``vultron`` and marks."""

    __test__ = False  # not a pytest class

    path: str
    modules: frozenset[str]
    names: frozenset[tuple[str, str]]
    spec_ids: frozenset[str]


@dataclass(frozen=True)
class Requirement:
    """One requirement, flattened for matching."""

    id: str
    group: str
    topic: str
    statement: str
    priority: str = "MUST"

    @property
    def mandatory(self) -> bool:
        """``MUST``/``MUST_NOT``; a SHOULD or MAY cannot block a build."""
        return self.priority in ("MUST", "MUST_NOT")


@dataclass
class GroupHit:
    """The requirement IDs and evidence that put a group in a tier."""

    group: str
    topic: str
    reqs: set[str] = field(default_factory=set)
    evidence: set[str] = field(default_factory=set)


@dataclass
class BackstopReport:
    """Result of :func:`analyze`."""

    symbols: dict[str, set[str]]
    must: dict[str, GroupHit]
    info: dict[str, GroupHit]
    no_signal: list[str]
    hubs: dict[str, int] = field(default_factory=dict)
    hub_threshold: int = HUB_THRESHOLD
    #: Catch-all test files whose markers were demoted, and their group span.
    monoliths: dict[str, int] = field(default_factory=dict)
    #: Changed paths outside ``vultron/`` and ``test/``, which this tool reads
    #: nothing from. Reported so a caller cannot mistake "ignored" for "clean".
    ignored: list[str] = field(default_factory=list)


#: Stand-in for an ID absent from the registry, so an unknown ID is treated as
#: mandatory rather than silently dropped from the MUST tier.
_ADVISORY = Requirement("", "", "", "", "MUST")


@dataclass
class Manifest:
    """IDs a Spec manifest lists as loaded or as considered and skipped."""

    loaded: set[str] = field(default_factory=set)
    dismissed: set[str] = field(default_factory=set)
