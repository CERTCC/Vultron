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

"""Check that no status entry repeats the one before it, and that labels fit.

A ``CaseStatus`` entry records a change of the case's EM or PXA.  One whose
object equals the previous status, apart from its id, label and times,
changes nothing, and is not committed (CLP-07-013, ADR-0152; #5123).  A
participant may confirm a state it already holds (BTND-10-001), but no demo
scenario has a reason to, so an unchanged ``ParticipantStatus`` entry there
is a scenario that sends a step it does not need (#5125).  A ``CaseStatus``
label is derived from its states, so a label that names other states
contradicts the record (#5124).

Both checks read ``(log_index, semantic_type, payload_snapshot)`` triples in
chain order, so the in-process demo checks (``CaseLedgerEntry`` objects) and
the CI invariant harness (dumped JSON entries) share them.
"""

from collections.abc import Iterable, Mapping
from typing import Any

#: The entry types that record a status, keyed on their target.
STATUS_SEMANTIC_TYPES = frozenset(
    {"add_case_status_to_case", "add_participant_status_to_participant"}
)

#: The keys two otherwise equal statuses differ in: identity, label and time.
_VOLATILE_KEYS = frozenset({"id", "id_", "name", "published", "updated"})

StatusEntry = tuple[int, str, Mapping[str, Any]]


def _content(value: Any) -> Any:
    """*value* without the keys that differ between equal statuses."""
    if isinstance(value, Mapping):
        return {
            key: _content(item)
            for key, item in value.items()
            if key not in _VOLATILE_KEYS
        }
    if isinstance(value, list):
        return [_content(item) for item in value]
    return value


def _ref_id(value: Any) -> str | None:
    """The id *value* names, inline or by reference."""
    if isinstance(value, Mapping):
        value = value.get("id", value.get("id_"))
    return value if isinstance(value, str) and value else None


def unchanged_status_entries(entries: Iterable[StatusEntry]) -> list[str]:
    """One message per status entry equal to the previous one for its target."""
    previous: dict[tuple[str, str], tuple[int, Any]] = {}
    found: list[str] = []
    for index, semantic_type, snapshot in entries:
        if semantic_type not in STATUS_SEMANTIC_TYPES:
            continue
        status = snapshot.get("object")
        target = _ref_id(snapshot.get("target"))
        if not isinstance(status, Mapping) or target is None:
            continue
        key = (semantic_type, target)
        content = _content(status)
        if key in previous and previous[key][1] == content:
            found.append(
                f"entry {index} ({semantic_type}, {status.get('name')!r})"
                f" repeats entry {previous[key][0]} for '{target}' unchanged"
            )
        previous[key] = (index, content)
    return found


def mislabelled_case_statuses(entries: Iterable[StatusEntry]) -> list[str]:
    """One message per ``CaseStatus`` entry whose label names other states."""
    found: list[str] = []
    for index, semantic_type, snapshot in entries:
        if semantic_type != "add_case_status_to_case":
            continue
        status = snapshot.get("object")
        if not isinstance(status, Mapping) or status.get("name") is None:
            continue
        derived = f"{status.get('emState')} {status.get('pxaState')}"
        if status["name"] != derived:
            found.append(
                f"entry {index}: CaseStatus named {status['name']!r}, but its"
                f" states are {derived!r} (#5124)"
            )
    return found
