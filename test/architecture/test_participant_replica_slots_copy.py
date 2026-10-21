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

"""Replica participant slots copy what their entries carry (#4295, CM-23-016).

A replica changes RM state, participant records, participant statuses and
case statuses only by copying the objects the CASE_MANAGER's entries carry
(CLP-07-013, ADR-0124).  So every slot of ``AnnounceLogEntryReceivedBT`` that
writes one of them (:data:`_SLOTS`) must never mint an id, read a clock, walk
the RM table, re-run an acceptance rule, or read the replica's own status to
fill a field.  :data:`_FORBIDDEN` names those, and the check follows every
helper and core model method a slot reaches (``_replica_slots``), so a slot
cannot hand the work on.  A slot also never builds a record afresh: a call of
a record class itself (``ParticipantStatus(...)``) is a new id and new times.

The writes behind these slots are the model mutators
(``CaseParticipant.add_participant_status``, ``VulnerabilityCase.add_participant``,
``add_case_status``), the same ones the CASE_MANAGER's writers use; no code
outside ``vultron/core/models`` mutates those collections in place
(``test_validate_assignment_ratchet.py``, CM-27-003).
:func:`test_every_replica_participant_slot_is_checked` keeps :data:`_SLOTS`
whole.
"""

import ast
import inspect
import textwrap
from typing import Any, cast

import pytest

from test.architecture import _corpus
from test.architecture._replica_slots import (
    _functions_reached,
    _names_used,
    _own_classes,
    _reached_functions,
    _tree_slot_classes,
)
from vultron.core.behaviors.sync.nodes.case_status_effect import (
    ApplyCaseStatusFromLedgerNode,
)
from vultron.core.behaviors.sync.nodes.participant_record_effect import (
    ApplyCaseParticipantUpdateFromLedgerNode,
    ApplyCreateCaseParticipantFromLedgerNode,
)
from vultron.core.behaviors.sync.nodes.participant_removal_effect import (
    ApplyReinstateCaseParticipantFromLedgerNode,
    ApplyRemoveCaseParticipantFromLedgerNode,
)
from vultron.core.behaviors.sync.nodes.participant_status_effect import (
    ApplyParticipantStatusFromLedgerNode,
)
from vultron.core.behaviors.sync.nodes.role_grant_effect import (
    ApplyCaseParticipantRoleGrantFromLedgerNode,
)
from vultron.core.behaviors.sync.nodes.stub_reply_effect import (
    ApplyInviteAcceptFromLedgerNode,
    ApplyInviteRejectFromLedgerNode,
)

#: What a copying slot must never reach for (CM-23-016): an id or clock of
#: its own, the RM table or a lifecycle writer, an acceptance rule that
#: carries the replica's value forward, or the replica's current status.
_FORBIDDEN = frozenset(
    {
        # minting and clocks
        "uuid4",
        "now_utc",
        "now",
        # walking the RM table / running a lifecycle writer
        "rm_closure_path",
        "RMClosureWriter",
        "CreateParticipantStatusNode",
        "validate_participant_status_write",
        # acceptance rules that carry the replica's own value forward
        "is_em_assertion_acceptable",
        "is_pxa_assertion_acceptable",
        "is_rm_at_least",
        # reading the replica's own status to fill a field
        "read_rm_states",
        "resolve_participant_state_from_dl",
        "current_status",
        "participant_status",
    }
)

#: Record classes a slot copies and never builds.
_RECORD_CLASSES = frozenset(
    {"ParticipantStatus", "CaseParticipant", "CaseStatus"}
)

#: Every replica slot that writes RM state, a participant record, a
#: participant status or a case status.
_SLOTS = [
    ApplyParticipantStatusFromLedgerNode,
    ApplyCaseStatusFromLedgerNode,
    ApplyCreateCaseParticipantFromLedgerNode,
    ApplyCaseParticipantUpdateFromLedgerNode,
    ApplyCaseParticipantRoleGrantFromLedgerNode,
    ApplyRemoveCaseParticipantFromLedgerNode,
    ApplyReinstateCaseParticipantFromLedgerNode,
    # the stub Invite answers: joined, and the joiner's own consent row
    ApplyInviteAcceptFromLedgerNode,
    ApplyInviteRejectFromLedgerNode,
]

#: Names whose use marks a slot as writing participant or case-status state.
_WRITER_NAMES = frozenset(
    {
        "add_participant_status",
        "add_participant",
        "add_case_status",
        "add_role",
        "remove_role",
        "mark_removed",
        "mark_reinstated",
    }
)


def _record_builds(obj: object) -> set[str]:
    """Record classes *obj*'s source builds afresh.

    A direct call (``ParticipantStatus(...)``) or a ``model_validate`` of a
    dict literal written in the slot: either gets the model's own id and
    times, not the carried ones.  Validating the carried snapshot
    (``model_validate(project_wire_snapshot_to_core(...))``) is a copy.
    """
    source = inspect.getsource(cast(Any, obj))
    tree = _corpus.parse_inline(textwrap.dedent(source))
    built: set[str] = set()
    for node in ast.walk(tree):
        if not isinstance(node, ast.Call):
            continue
        func = node.func
        if isinstance(func, ast.Name) and func.id in _RECORD_CLASSES:
            built.add(func.id)
        elif (
            isinstance(func, ast.Attribute)
            and func.attr == "model_validate"
            and isinstance(func.value, ast.Name)
            and func.value.id in _RECORD_CLASSES
            and node.args
            and isinstance(node.args[0], ast.Dict)
        ):
            built.add(func.value.id)
    return built


def _slot_names(slot: type) -> dict[str, set[str]]:
    """The names each of *slot*'s own classes and reached functions use."""
    found = {c.__qualname__: _names_used(c) for c in _own_classes(slot)}
    found.update(_functions_reached(slot))
    return found


@pytest.mark.spec("CM-23-016")
@pytest.mark.parametrize("slot", _SLOTS, ids=lambda c: c.__name__)
def test_a_participant_slot_derives_nothing(slot: type) -> None:
    offenders = {
        where: sorted(names & _FORBIDDEN)
        for where, names in _slot_names(slot).items()
        if names & _FORBIDDEN
    }
    assert not offenders, f"{slot.__name__} reaches {offenders}"


@pytest.mark.spec("CM-23-016")
@pytest.mark.parametrize("slot", _SLOTS, ids=lambda c: c.__name__)
def test_a_participant_slot_builds_no_record(slot: type) -> None:
    """A copy keeps the carried record's id and times; a build mints its own.

    Checked in the slot's own classes and every helper and core model method
    it reaches, so a slot cannot hand the build to a helper.
    """
    roots: list[Any] = [*_own_classes(slot), *_reached_functions(slot)]
    builds = {
        r.__qualname__: sorted(_record_builds(r))
        for r in roots
        if _record_builds(r)
    }
    assert not builds, f"{slot.__name__} builds {builds}"


def _writes_participant_state(cls: type) -> bool:
    names = set().union(*(_names_used(c) for c in _own_classes(cls)))
    for reached in _functions_reached(cls, follow_methods=False).values():
        names |= reached
    return bool(names & _WRITER_NAMES)


@pytest.mark.spec("CM-23-016")
def test_every_replica_participant_slot_is_checked() -> None:
    """A new participant-writing slot in the announce tree joins the ratchet."""
    slots = {c for c in _tree_slot_classes() if _writes_participant_state(c)}

    assert slots, "the announce tree runs no participant slot"
    missing = sorted(c.__name__ for c in slots - set(_SLOTS))
    assert not missing, f"add {missing} to _SLOTS"
    absent = sorted(c.__name__ for c in set(_SLOTS) - _tree_slot_classes())
    assert not absent, f"{absent} no longer run in the announce tree"


def test_the_check_sees_a_minted_status() -> None:
    """Not vacuous: the RM-verdict replay #4295 removed would fail it.

    It built the status from a dict literal, with the replica's own VF and
    roles and no id, so the model minted one.
    """

    class _BuildsAStatus:
        def update(self, entry: Any, current: Any) -> Any:
            ParticipantStatus.model_validate(  # type: ignore[name-defined]  # noqa: F821
                {"rm": entry.rm, "vf": current.vf}
            )
            return CaseStatus(published=now_utc())  # type: ignore[name-defined]  # noqa: F821

    assert _record_builds(_BuildsAStatus) == {
        "ParticipantStatus",
        "CaseStatus",
    }
    assert "now_utc" in _names_used(_BuildsAStatus)


def test_the_walk_follows_a_slots_helpers() -> None:
    """Not vacuous: the stub-reply slot reaches the helper that writes."""
    reached = _functions_reached(ApplyInviteAcceptFromLedgerNode)

    assert "vultron.core.participants.stub_reply.apply_stub_accept" in reached
