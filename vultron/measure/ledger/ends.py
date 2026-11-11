"""Whether a case ledger's last entry is known to be the case's last (CEH-02-006).

No copy of a ledger says whose copy it is, since a replica's entries are
byte-identical to the CASE_MANAGER's (CLP-07-013).  So a copy that holds every
index without a gap is complete only as far as the input shows: a participant's
replica cut off at the tail when its report closed (CM-23-004) looks the same
as the CASE_MANAGER's copy of a case that has not ended.  The end is confirmed
only by evidence in the entries:

* the last entry is the CASE_MANAGER's own ``RM.CLOSED`` status, the owner-close
  boundary after which the case records nothing more (CM-23-013), read with the
  core predicate every closure check shares (``closure_boundary_indices``); or
* another copy ends on the same entry.
"""

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

from __future__ import annotations

from collections.abc import Iterable, Mapping

from vultron.core.predicates.case_closure import closure_boundary_indices
from vultron.enums.roles import CVDRole
from vultron.measure.ledger.fields import (
    first_present,
    log_index_of,
    payload_of,
)


def _ref(value: object) -> str | None:
    """A reference as a string id, from a bare id or an inline object."""
    if isinstance(value, str) and value:
        return value
    if isinstance(value, Mapping):
        ref = value.get("id") or value.get("id_")
        return ref if isinstance(ref, str) and ref else None
    return None


def _collect_case_managers(node: object, out: set[str]) -> None:
    """Add every participant *node* holds that carries the CASE_MANAGER role."""
    if isinstance(node, list):
        for item in node:
            _collect_case_managers(item, out)
        return
    if not isinstance(node, Mapping):
        return
    roles = first_present(node, "caseRoles", "case_roles")
    if isinstance(roles, list) and CVDRole.CASE_MANAGER.value in roles:
        actor = _ref(first_present(node, "attributedTo", "attributed_to"))
        if actor is not None:
            out.add(actor)
    for child in node.values():
        if isinstance(child, (Mapping, list)):
            _collect_case_managers(child, out)


def case_manager_ids(entries: Iterable[Mapping[str, object]]) -> set[str]:
    """The actors the entries name as holding the CASE_MANAGER role.

    Read from every participant record in every payload snapshot, so a
    copy that holds the genesis entry, which seats the CASE_MANAGER, always
    yields it.
    """
    found: set[str] = set()
    for entry in entries:
        _collect_case_managers(payload_of(entry), found)
    return found


def ends_in_case_closure(entries: list[Mapping[str, object]]) -> bool:
    """Whether the entry with the highest log index closes the case.

    True when that entry is the CASE_MANAGER's own ``RM.CLOSED`` status for
    an actor the entries name as CASE_MANAGER.  Only the *last* entry counts:
    an earlier closure entry with entries missing after it would leave the
    tail unproved.
    """
    indexed = [(i, e) for e in entries if (i := log_index_of(e)) is not None]
    if not indexed:
        return False
    last_index, last = max(indexed, key=lambda pair: pair[0])
    shaped = {
        "log_index": last_index,
        "semantic_type": first_present(last, "semantic_type", "semanticType"),
        "payload_snapshot": payload_of(last),
    }
    return any(
        closure_boundary_indices([shaped], manager) == [last_index]
        for manager in sorted(case_manager_ids(entries))
    )
