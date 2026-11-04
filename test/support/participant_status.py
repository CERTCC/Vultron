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

"""Test-side participant status arrange helpers and the fixture-state guard.

Two unrelated-looking duties live here because both are about a participant
status a *test* writes rather than a tree.

**Arranging an RM state** (ADR-0089 AC-2, issue #3207).  Production code
advances a participant's RM state only through the sole writer,
:class:`~vultron.core.behaviors.case.nodes.participant.status.CreateParticipantStatusNode`.
The model no longer carries an ``append_rm_state`` mutator.  Tests that just
need to *arrange* a participant at a given RM state use ``advance_participant_rm``
below, which goes through the public, validated
:meth:`~vultron.core.models.case_participant.CaseParticipant.add_participant_status`
door (PRM-03-003) rather than mutating ``participant_statuses`` directly.

It reproduces the vendor/deployer carry-forward the old mutator performed
(#2264, #3134): an RM-only append must not silently rewind ``vf``/``d`` that the
role-dimension seeding validator would re-seed at their initial state.

**Refusing an impossible arranged state** (CSB-18-001, issue #3046).  A fixture
chosen for convenience can pair an RM state with a VF or D state the protocol
makes impossible — ``rm=VALID`` with ``vf=VF``, say, which CSB-18-001 forbids
because a fix cannot be ready before the report is accepted.  A test built on
such a state passes for the wrong reason, and *fails* when the matching
invariant is finally enforced, so a real enforcement improvement reads as a
regression (#2906).  ``install_impossible_state_guard`` closes that door at the
only place every fixture must pass through: the DataLayer write.  It is keyed on
the entailment evaluator rather than on any fixture builder's name, so a test
that hand-rolls its own participant is caught too.
"""

from __future__ import annotations

import logging
from collections.abc import Callable, Iterator
from typing import Any

from vultron.core.models.case_participant import CaseParticipant
from vultron.core.models.dimensions import (
    DDimension,
    RmDimension,
    VfDimension,
)
from vultron.core.models.participant_status import (
    ParticipantStatus,
    coerce_cvd_roles,
    participant_status_d_state,
    participant_status_rm_state,
    participant_status_vf_state,
)
from vultron.core.predicates.roles import has_deployer_role, has_vendor_role
from vultron.core.states.composite_state_invariants import (
    composite_state_violations,
)
from vultron.core.states.rm import RM, is_valid_rm_transition

logger = logging.getLogger(__name__)


def advance_participant_rm(
    participant: CaseParticipant, rm_state: RM, actor: str, context: str
) -> bool:
    """Append a ParticipantStatus at *rm_state*, carrying vf/d forward.

    Test-only stand-in for the retired ``CaseParticipant.append_rm_state``.
    Validates the RM transition against the state machine; on an invalid
    transition it logs a warning and returns ``False`` without appending
    (matching the old mutator's contract so arrange sites that asserted the
    boolean still hold).

    Args:
        participant: The participant to advance.
        rm_state: Target RM state.
        actor: URI of the actor asserting the transition.
        context: URI of the case context.

    Returns:
        ``True`` when a status was appended, ``False`` when the transition was
        blocked.
    """
    latest = participant.participant_status
    current = latest.rm.state if latest is not None else RM.START
    if not is_valid_rm_transition(current, rm_state):
        logger.warning(
            "Invalid RM transition %s → %s for participant %s; skipping",
            current,
            rm_state,
            participant.id_,
        )
        return False
    roles = coerce_cvd_roles(participant.case_roles)
    # Carry the vendor and deployer paths forward, but only while their role is
    # still held (ADR-0075) — omitting a dimension re-seeds it at its initial
    # state (#2264, #3134), which would silently rewind a vendor or deployer.
    current_vf = (
        participant_status_vf_state(latest)
        if latest is not None and has_vendor_role(roles)
        else None
    )
    current_d = (
        participant_status_d_state(latest)
        if latest is not None and has_deployer_role(roles)
        else None
    )
    participant.add_participant_status(
        ParticipantStatus(
            rm=RmDimension(state=rm_state),
            vf=(
                VfDimension(state=current_vf)
                if current_vf is not None
                else None
            ),
            d=DDimension(state=current_d) if current_d is not None else None,
            context=context,
            attributed_to=actor,
            cvd_role=roles,
        )
    )
    return True


# ---------------------------------------------------------------------------
# Impossible-fixture guard (CSB-18-001, CSB-17-001; issue #3046)
# ---------------------------------------------------------------------------

#: Every ``SqliteDataLayer`` method that can put a participant record in a
#: store.  The guard wraps all of them, so no write path is a way around it.
_GUARDED_WRITE_METHODS = (
    "create",
    "save",
    "save_many",
    "save_if_unchanged",
    "update",
)


def impossible_state_reasons(status: object) -> list[str]:
    """Return every composite-state entailment *status* violates.

    Delegates to :func:`composite_state_violations`, the one place the RM↔VF,
    RM↔D and VF↔D rules are composed (CSB-18-001, CSB-17-001), so the guard and
    the protocol paths can never enforce different subsets of them
    (RSH-09-004, RSH-09-012).  An empty list means the combination is possible.

    The PXA↔EM entailments (CSB-18-002..004) are deliberately out of scope: the
    P, X and A events *cause* embargo termination, so a snapshot pairing them
    with an active embargo is a legitimate intermediate rather than an
    impossible state (``violation_pxa_em_entailment`` is not enforced on the
    emit path for the same reason).
    """
    rm = participant_status_rm_state(status)
    return [
        violation.message
        for violation in composite_state_violations(
            rm,
            participant_status_vf_state(status),
            participant_status_d_state(status),
        )
    ]


def assert_possible_participant_status(status: object, where: str) -> None:
    """Raise when *status* encodes a state the CS invariants forbid.

    *where* names the thing being checked — a participant id, a fixture helper
    — so the failure points at the fixture rather than at the guard.
    """
    reasons = impossible_state_reasons(status)
    if not reasons:
        return
    raise AssertionError(
        f"{where} encodes a participant state the protocol forbids."
        " A fixture in an impossible state makes the test pass for a reason"
        " other than the behaviour it names, and fail when the matching"
        f" invariant is enforced (#3046). Violations: {'; '.join(reasons)}"
    )


def assert_recorded_states_possible(
    participant: object, where: str = ""
) -> None:
    """Check every status recorded on *participant*.

    ``participant_statuses`` is the participant's append-only history
    (SM-05-002), and CSB-18-001 is a statement about a participant's composite
    state, so every entry is in scope, not only the current one.  Entries held
    by reference (a bare id rather than an inline snapshot) carry no dimensions
    and are skipped.
    """
    statuses = getattr(participant, "participant_statuses", None)
    if not statuses:
        return
    label = where or str(getattr(participant, "id_", participant))
    for index, status in enumerate(statuses):
        if getattr(status, "rm", None) is None:
            continue
        assert_possible_participant_status(
            status, f"{label} participant_statuses[{index}]"
        )


def _participant_records(value: object) -> Iterator[object]:
    """Yield every participant record reachable from a persisted *value*.

    A test may seed a participant on its own (``dl.create(vendor)``) or only
    inline on the case (``case.case_participants``), and
    ``_dehydrate_data`` keeps the inline snapshot, so both reach a store.  A
    standalone ``ParticipantStatus`` write is *not* a participant record and is
    deliberately not yielded: the received-side tests store the inbound status
    they expect to be refused, and that one is allowed to be impossible.
    """
    if getattr(value, "participant_statuses", None):
        yield value
    for participant in getattr(value, "case_participants", None) or ():
        if getattr(participant, "participant_statuses", None):
            yield participant


def _guarded_write(
    method: Callable[..., Any], name: str
) -> Callable[..., Any]:
    def _wrapper(self: Any, *args: Any, **kwargs: Any) -> Any:
        for value in (*args, *kwargs.values()):
            for candidate in _participant_records(value):
                record_id = getattr(candidate, "id_", candidate)
                assert_recorded_states_possible(
                    candidate, f"DataLayer.{name}({record_id})"
                )
        return method(self, *args, **kwargs)

    return _wrapper


def install_impossible_state_guard(monkeypatch: Any) -> None:
    """Refuse any DataLayer write of a participant in an impossible state.

    Wraps each of :data:`_GUARDED_WRITE_METHODS` on ``SqliteDataLayer`` so the
    check runs *during* the test, where the failure names the test that seeded
    the state.  A teardown scan could not do that: the store a test opens is
    closed by the fixture that opened it.

    The guard holds the whole protocol to the rule, not just the fixtures: a
    production path that commits an impossible participant state fails here
    too, which is the point — CSB-18-001's ``verification`` asks for exactly
    this call over each participant.

    ``monkeypatch`` undoes the wrapping at teardown, so the guard never leaks
    into a test that did not ask for it.
    """
    from vultron.adapters.driven.datalayer_sqlite import SqliteDataLayer

    for name in _GUARDED_WRITE_METHODS:
        monkeypatch.setattr(
            SqliteDataLayer,
            name,
            _guarded_write(getattr(SqliteDataLayer, name), name),
        )
