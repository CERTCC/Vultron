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

"""Shared fixtures and cases for the received-side RM acceptance rule.

The CASE_MANAGER applies one RM acceptance rule to every received declaration,
whichever wire activity carried it (RSH-06-006).  The ``Add(ParticipantStatus)``
tests (``test/core/behaviors/status/test_participant_status_acceptance.py``),
the activity-typed handler tests
(``test/core/behaviors/report/test_rm_declaration_adjudication.py``) and the
full-case Invite reply tests
(``test/core/behaviors/case/test_full_case_invite_rm_declaration.py``) all build
their case from this module and run against :data:`RM_DECLARATION_CASES`, so
every path is asserted against the same table.
"""

from __future__ import annotations

import logging
from collections.abc import Iterator
from dataclasses import dataclass
from typing import Any, cast

import py_trees
import pytest
from py_trees.common import Status

from vultron.adapters.driven.datalayer_sqlite import SqliteDataLayer
from vultron.core.behaviors.status.nodes.rm_rule import BB_RM_ANOMALY
from vultron.core.models._helpers import _as_id
from vultron.core.models.case import VulnerabilityCase
from vultron.core.models.case_ledger_entry import CaseLedgerEntry
from vultron.core.models.case_participant import CaseParticipant
from vultron.core.models.dimensions import (
    EmDimension,
    PxaDimension,
    RmDimension,
    VfDimension,
)
from vultron.core.states.cs import CS_pxa, CS_vf
from vultron.core.states.em import EM
from vultron.core.states.rm import RM, RMDeclaration
from vultron.enums.roles import CVDRole
from vultron.wire.as2.vocab.objects.case_participant import as_CaseParticipant
from vultron.wire.as2.vocab.objects.case_status import (
    as_CaseStatus,
    as_ParticipantStatus,
)

ACTOR_ID = "https://example.org/actors/vendor"
CASE_MANAGER_ID = "https://example.org/actors/case-actor"
CASE_ID = "https://example.org/cases/case-2235"
REPORT_ID = "https://example.org/reports/report-2235"
PARTICIPANT_ID = f"{CASE_ID}/participants/vendor"
CM_PARTICIPANT_ID = f"{CASE_ID}/participants/case-actor"
CURRENT_STATUS_ID = f"{PARTICIPANT_ID}/statuses/current"
STRANGER_ID = "https://example.org/actors/stranger"


@pytest.fixture
def store_for() -> Iterator[Any]:
    """Factory: the store belonging to a given actor.

    A BT's store follows its executing actor (ADR-0073), so each test opens the
    store of the actor it runs as.
    """
    created: list[SqliteDataLayer] = []

    def _make(actor_id: str) -> SqliteDataLayer:
        dl = SqliteDataLayer("sqlite:///:memory:", actor_id=actor_id)
        created.append(dl)
        return dl

    yield _make
    for dl in created:
        dl.close()


def current_status(
    rm_state: RM,
    vf_state: CS_vf | None,
    pxa_state: CS_pxa,
) -> as_ParticipantStatus:
    """The sender's recorded status *before* the declaration arrives."""
    return as_ParticipantStatus(
        id_=CURRENT_STATUS_ID,
        context=CASE_ID,
        rm=RmDimension(state=rm_state),
        vf=(VfDimension(state=vf_state) if vf_state is not None else None),
        case_status=as_CaseStatus(
            id_=f"{CURRENT_STATUS_ID}/cs",
            context=CASE_ID,
            em=EmDimension(state=EM.NONE),
            pxa=PxaDimension(state=pxa_state),
        ),
    )


def seed_case(
    dl: SqliteDataLayer,
    current: as_ParticipantStatus,
    asserted: as_ParticipantStatus | None,
) -> None:
    """Seed a two-participant case with *current* as the sender's latest status.

    The case is linked to :data:`REPORT_ID`, so the report-verdict handlers
    find it the same way the status path does.
    """
    vendor = as_CaseParticipant(
        id_=PARTICIPANT_ID,
        context=CASE_ID,
        attributed_to=ACTOR_ID,
        case_roles=[CVDRole.CASE_OWNER, CVDRole.VENDOR],
    )
    vendor.participant_statuses.append(current)
    manager = as_CaseParticipant(
        id_=CM_PARTICIPANT_ID,
        context=CASE_ID,
        attributed_to=CASE_MANAGER_ID,
        case_roles=[CVDRole.CASE_MANAGER],
    )
    # attributed_to is what seeds the per-case genesis hash (CLP-08-003);
    # without it the ledger sits in the pre-genesis bootstrap window and the
    # guarded commit cannot anchor a chain.
    case = VulnerabilityCase(
        id_=CASE_ID,
        name="Issue 2235 Case",
        attributed_to=CASE_MANAGER_ID,
        vulnerability_reports=[REPORT_ID],
    )
    case.add_participant(cast(CaseParticipant, vendor))
    case.add_participant(cast(CaseParticipant, manager))

    dl.create(case)
    dl.create(vendor)
    dl.create(manager)
    dl.create(current)
    if asserted is not None:
        dl.create(asserted)


class RMAnomalyProbe(py_trees.decorators.Decorator):
    """Probe: snapshot ``BB_RM_ANOMALY`` when the wrapped tree finishes.

    The anomaly is an execution-scoped hand-off that ``execute_with_setup``
    resets at teardown, so a test cannot read it after the run returns.
    Wrap the tree in this probe to observe what the run published; the
    probe returns the tree's own status, so a refusal still reads as one.
    """

    def __init__(
        self, child: py_trees.behaviour.Behaviour, sink: dict[str, Any]
    ) -> None:
        super().__init__(name="RMAnomalyProbe", child=child)
        self._sink = sink

    def update(self) -> Status:
        self._sink["anomaly"] = py_trees.blackboard.Blackboard.storage.get(
            f"/{BB_RM_ANOMALY}"
        )
        return self.decorated.status


def recorded_rm(dl: SqliteDataLayer) -> RM:
    """Return the sender's latest recorded RM state."""
    participant = cast(CaseParticipant, dl.read(PARTICIPANT_ID))
    return participant.participant_statuses[-1].rm.state


def status_count(
    dl: SqliteDataLayer, participant_id: str = PARTICIPANT_ID
) -> int:
    """Return how many statuses *participant_id* has recorded."""
    participant = cast(CaseParticipant, dl.read(participant_id))
    return len(participant.participant_statuses)


def recorded_notes(dl: SqliteDataLayer) -> list[dict[str, Any]]:
    """Return the notes *dl*'s CASE_MANAGER recorded on the case (RSH-06-004).

    Each is the note an ``add_note_to_case`` entry carries inline, oldest
    first: the CASE_MANAGER commits its own note and the ledger fan-out
    delivers it (#4829).
    """
    entries = sorted(
        (
            e
            for e in dl.list_objects("CaseLedgerEntry")
            if isinstance(e, CaseLedgerEntry)
            and e.semantic_type == "add_note_to_case"
        ),
        key=lambda e: e.log_index,
    )
    return [
        cast(dict[str, Any], e.payload_snapshot["object"]) for e in entries
    ]


@dataclass(frozen=True)
class RMDeclarationCase:
    """One row of the shared RM acceptance table (RSH-06-001 to RSH-06-003)."""

    current: RM
    declared: RM
    verdict: RMDeclaration

    @property
    def id(self) -> str:
        return f"{self.current.name}->{self.declared.name}:{self.verdict.name}"

    @property
    def accepted(self) -> bool:
        return self.verdict is not RMDeclaration.REGRESSION

    @property
    def anomaly(self) -> str | None:
        """The ``BB_RM_ANOMALY`` type the rule flags, or ``None``."""
        if self.verdict is RMDeclaration.GAP:
            return "gap"
        if self.verdict is RMDeclaration.REGRESSION:
            return "regression"
        return None

    @property
    def expected_rm(self) -> RM:
        """The RM state recorded for the sender afterwards."""
        return self.declared if self.accepted else self.current

    @property
    def sender_closed(self) -> bool:
        """The sender is at RM ``CLOSED`` before the declaration arrives.

        A received declaration from such a sender is refused before the
        rule is applied, with no note (CM-23-018): its row exercises the
        rule itself, not a received handler.
        """
        return self.current is RM.CLOSED


_C = RMDeclarationCase
_V = RMDeclaration

RM_DECLARATION_CASES: tuple[RMDeclarationCase, ...] = (
    # Confirmations: a restated move is not an anomaly (RSH-08-002).
    _C(RM.INVALID, RM.INVALID, _V.CONFIRMATION),
    _C(RM.VALID, RM.VALID, _V.CONFIRMATION),
    _C(RM.ACCEPTED, RM.ACCEPTED, _V.CONFIRMATION),
    _C(RM.DEFERRED, RM.DEFERRED, _V.CONFIRMATION),
    _C(RM.CLOSED, RM.CLOSED, _V.CONFIRMATION),
    # Adjacent forward moves.
    _C(RM.RECEIVED, RM.INVALID, _V.ADVANCE),
    _C(RM.RECEIVED, RM.VALID, _V.ADVANCE),
    _C(RM.INVALID, RM.CLOSED, _V.ADVANCE),
    _C(RM.VALID, RM.ACCEPTED, _V.ADVANCE),
    _C(RM.VALID, RM.DEFERRED, _V.ADVANCE),
    _C(RM.DEFERRED, RM.ACCEPTED, _V.ADVANCE),
    _C(RM.RECEIVED, RM.CLOSED, _V.ADVANCE),
    _C(RM.ACCEPTED, RM.CLOSED, _V.ADVANCE),
    _C(RM.DEFERRED, RM.CLOSED, _V.ADVANCE),
    # Non-adjacent forward moves: accepted, flagged (RSH-06-001).
    _C(RM.RECEIVED, RM.ACCEPTED, _V.GAP),
    _C(RM.RECEIVED, RM.DEFERRED, _V.GAP),
    _C(RM.INVALID, RM.ACCEPTED, _V.GAP),
    _C(RM.VALID, RM.CLOSED, _V.GAP),
    # Backward moves: refused, current carried forward (RSH-06-002).
    _C(RM.ACCEPTED, RM.INVALID, _V.REGRESSION),
    _C(RM.ACCEPTED, RM.VALID, _V.REGRESSION),
    _C(RM.DEFERRED, RM.VALID, _V.REGRESSION),
    _C(RM.VALID, RM.INVALID, _V.REGRESSION),
    _C(RM.CLOSED, RM.INVALID, _V.REGRESSION),
    _C(RM.CLOSED, RM.ACCEPTED, _V.REGRESSION),
)


def assert_anomaly_flagged_and_noted(
    case: RMDeclarationCase,
    dl: SqliteDataLayer,
    records: list[logging.LogRecord],
) -> None:
    """Assert the run logged *case*'s anomaly and posted the note it owes.

    An anomaly is logged at WARNING naming both states (RSH-06-003), and
    either anomaly records one RSH-06-004 clarification note for the sender
    carrying the RSH-06-005 fields: an accepted gap from the effect stage, a
    refused regression from the factory's refusal-effects stage (CLP-10-022).
    """
    anomaly_logs = [
        r.getMessage()
        for r in records
        if r.levelno == logging.WARNING
        and f"RM {case.anomaly} declared by '{ACTOR_ID}'" in r.getMessage()
    ]
    if case.anomaly is None:
        assert not [r for r in records if "declared by" in r.getMessage()]
    else:
        assert anomaly_logs, "RSH-06-003: the anomaly must not be silent"
        assert case.current in anomaly_logs[0]
        assert case.declared in anomaly_logs[0]
    assert_note_owed(case, dl)


def committed_since(dl: SqliteDataLayer, log_index: int) -> list[str]:
    """The ``semantic_type`` of each entry *dl* committed after *log_index*.

    A refused declaration commits nothing of its own; the only entry it may
    leave is the CASE_MANAGER's RSH-06-004 note (CLP-10-022).
    """
    return [
        e.semantic_type
        for e in sorted(
            (
                e
                for e in dl.list_objects("CaseLedgerEntry")
                if isinstance(e, CaseLedgerEntry) and e.log_index > log_index
            ),
            key=lambda e: e.log_index,
        )
    ]


def note_content(note: dict[str, Any]) -> str:
    """Return the content of a recorded note."""
    return str(note.get("content") or "")


def assert_note_owed(case: RMDeclarationCase, dl: SqliteDataLayer) -> None:
    """Assert *dl* recorded exactly the RSH-06-004 note *case* owes, if any.

    The note is attached to the case and names the sender, both RM states,
    and whether the anomaly was a forward gap or a refused regression
    (RSH-06-005).
    """
    notes = recorded_notes(dl)
    assert len(notes) == (0 if case.anomaly is None else 1)
    if not notes:
        return
    stored = cast(VulnerabilityCase, dl.read(CASE_ID))
    assert notes[0]["id"] in [_as_id(n) for n in stored.notes]
    content = note_content(notes[0])
    assert ACTOR_ID in content
    assert f"{case.current}" in content
    assert f"{case.declared}" in content
    kind = "non-adjacent forward" if case.anomaly == "gap" else "backward"
    assert kind in content


def cases_declaring(*declared: RM, sender_closed: bool = False) -> list[Any]:
    """Return :data:`RM_DECLARATION_CASES` declaring one of *declared*, as params.

    By default only the rows whose sender may still act on the case, which a
    received handler adjudicates.  With *sender_closed* the rows whose sender
    is at RM ``CLOSED``, which a received handler refuses before adjudicating
    (CM-23-018).
    """
    return [
        pytest.param(case, id=case.id)
        for case in RM_DECLARATION_CASES
        if case.declared in declared and case.sender_closed is sender_closed
    ]


def received_cases(*, sender_closed: bool = False) -> list[Any]:
    """Return every row a received handler adjudicates, as pytest params.

    :func:`all_cases` without the rows whose sender is at RM ``CLOSED``; with
    *sender_closed*, only those rows (CM-23-018).
    """
    return [
        pytest.param(case, id=case.id)
        for case in RM_DECLARATION_CASES
        if case.sender_closed is sender_closed
    ]


def all_cases() -> list[Any]:
    """Return every row of :data:`RM_DECLARATION_CASES` as pytest params."""
    return [pytest.param(case, id=case.id) for case in RM_DECLARATION_CASES]
