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
tests (``test/core/behaviors/status/test_partial_accept_participant_status.py``)
and the activity-typed handler tests
(``test/core/behaviors/report/test_rm_declaration_adjudication.py``) both build
their case from this module and run against :data:`RM_DECLARATION_CASES`, so
the two paths are asserted against the same table.
"""

from __future__ import annotations

from collections.abc import Iterator
from dataclasses import dataclass
from typing import Any, cast

import pytest

from vultron.adapters.driven.datalayer_sqlite import SqliteDataLayer
from vultron.core.models.case import VulnerabilityCase
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


def recorded_rm(dl: SqliteDataLayer) -> RM:
    """Return the sender's latest recorded RM state."""
    participant = cast(CaseParticipant, dl.read(PARTICIPANT_ID))
    return participant.participant_statuses[-1].rm.state


def queued_notes(dl: SqliteDataLayer) -> list[Any]:
    """Return the ``Add(Note)`` activities in *dl*'s outbox (RSH-06-004)."""
    notes = []
    for activity_id in dl.outbox_list():
        activity = dl.read(activity_id)
        obj = getattr(activity, "object_", None)
        obj = dl.read(obj) if isinstance(obj, str) else obj
        if (
            getattr(activity, "type_", None) == "Add"
            and getattr(obj, "type_", None) == "Note"
        ):
            notes.append(activity)
    return notes


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


def cases_declaring(*declared: RM) -> list[Any]:
    """Return :data:`RM_DECLARATION_CASES` declaring one of *declared*, as params."""
    return [
        pytest.param(case, id=case.id)
        for case in RM_DECLARATION_CASES
        if case.declared in declared
    ]


def all_cases() -> list[Any]:
    """Return every row of :data:`RM_DECLARATION_CASES` as pytest params."""
    return [pytest.param(case, id=case.id) for case in RM_DECLARATION_CASES]
