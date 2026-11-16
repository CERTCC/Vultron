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
"""The synthetic marker, the fixture directory, and the tools that may mark.

A committed VINCE-shaped file is synthetic only when one of two tools wrote
it and it carries the marker (VSD-02-005, ADR-0189). The marker names
which tool wrote the file, at the top level of the file's one document::

    {"synthetic": {"producer": "generator"}, "reads": {...}}

A marker alone proves nothing, since anyone can type it. So the check asks
the named producer to vouch for the file (:data:`ProducerVerifier`): the
generator vouches for a file only when a fresh generation writes the same
bytes to the same path. The sanitizer (#6348) registers its own verifier
under :data:`SANITIZER`; until it does, a file marked with that producer is
refused.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass

#: The one directory a VINCE-shaped file may be committed in, relative to
#: the repository root (VSD-02-001).
FIXTURE_DIR = "test/fixtures/vince"

#: The committed cleared-case list (VSD-02-002), inside the fixture
#: directory.
CLEARED_CASES_PATH = f"{FIXTURE_DIR}/cleared-cases.yaml"

#: The top-level key of the synthetic marker.
MARKER_KEY = "synthetic"

#: The marker's field that names the tool that wrote the file.
PRODUCER_KEY = "producer"

#: The committed fixture generator, :mod:`.generator` (#5961).
GENERATOR = "generator"

#: The sanitizer of test-instance responses (#6348), reserved here.
SANITIZER = "sanitizer"

#: Vouches for a marked file: given its repository-relative path and exact
#: text, returns ``None`` when its producer wrote it, or why not.
ProducerVerifier = Callable[[str, str], str | None]


@dataclass(frozen=True)
class Marker:
    """A well-formed synthetic marker."""

    producer: str


class MarkerError(ValueError):
    """A ``synthetic`` key that is not a well-formed marker."""


def read_marker(document: object) -> Marker | None:
    """The marker of *document*, or ``None`` when it carries none.

    Raises:
        MarkerError: When the ``synthetic`` key is present but is not an
            object holding exactly one non-empty string ``producer``, such as
            a bare ``"synthetic": true``, which names no tool.
    """
    if not isinstance(document, dict) or MARKER_KEY not in document:
        return None
    value = document[MARKER_KEY]
    if (
        not isinstance(value, dict)
        or set(value) != {PRODUCER_KEY}
        or not isinstance(value[PRODUCER_KEY], str)
        or not value[PRODUCER_KEY].strip()
    ):
        raise MarkerError(
            f'the marker must be {{"{PRODUCER_KEY}": "<tool>"}}, naming the '
            f"tool that wrote the file, not {value!r}"
        )
    return Marker(value[PRODUCER_KEY])


def marker_for(producer: str) -> dict[str, dict[str, str]]:
    """The marker *producer* writes at the top of each file it produces."""
    return {MARKER_KEY: {PRODUCER_KEY: producer}}


__all__ = [
    "CLEARED_CASES_PATH",
    "FIXTURE_DIR",
    "GENERATOR",
    "MARKER_KEY",
    "Marker",
    "MarkerError",
    "PRODUCER_KEY",
    "ProducerVerifier",
    "SANITIZER",
    "marker_for",
    "read_marker",
]
