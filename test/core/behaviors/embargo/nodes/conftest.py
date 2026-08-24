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

"""Shared fixtures for test/core/behaviors/embargo/nodes tests.

Imports as_VulnerabilityCase as a side effect to populate the global vocabulary
registry before any test in this package runs.
"""

import py_trees
import pytest

from vultron.adapters.driven.datalayer_sqlite import SqliteDataLayer
from vultron.core.states.em import EM
from vultron.enums.roles import CVDRole
from vultron.wire.as2.vocab.objects.case_participant import as_CaseParticipant
from vultron.wire.as2.vocab.objects.embargo_event import as_EmbargoEvent
from vultron.wire.as2.vocab.objects.vulnerability_case import (  # noqa: F401
    as_VulnerabilityCase,
)

CASE_MANAGER_ACTOR = "https://example.org/actors/case-manager"
#: A non-manager participant. The teardown announce is addressed to the case's
#: other participants, so a case needs one for the emission to be observable.
OTHER_PARTICIPANT_ACTOR = "https://example.org/actors/vendor"


def make_case_and_embargo(
    case_suffix: str,
    em_state: EM = EM.ACTIVE,
    attributed_to: str = CASE_MANAGER_ACTOR,
) -> tuple[as_VulnerabilityCase, as_EmbargoEvent]:
    """Create an in-memory as_VulnerabilityCase + as_EmbargoEvent pair.

    ``attributed_to`` is required for any tree that commits to the canonical
    ledger: the per-case genesis hash is derived from it (CLP-08-001/002), and
    without one ``ReconstructChainTailNode`` cannot anchor an empty chain and the
    commit fails with "per-case genesis hash is unavailable".
    """
    case = as_VulnerabilityCase(
        id_=f"https://example.org/cases/case_{case_suffix}",
        name=f"Test Case {case_suffix}",
        attributed_to=attributed_to,
    )
    embargo = as_EmbargoEvent(
        id_=f"https://example.org/cases/case_{case_suffix}/embargo_events/e1",
        context=case.id_,
    )
    case.active_embargo = embargo.id_
    case.current_status.em_state = em_state
    return case, embargo


def make_case_with_manager(
    suffix: str,
    em_state: EM = EM.ACTIVE,
    case_manager_actor: str = CASE_MANAGER_ACTOR,
    other_participants: tuple[str, ...] = (OTHER_PARTICIPANT_ACTOR,),
) -> tuple[as_VulnerabilityCase, as_CaseParticipant, SqliteDataLayer]:
    """Return a DataLayer with a case, a CASE_MANAGER, and other participants.

    The case gets at least one participant besides the manager by default,
    because the teardown announce is addressed to the case's *other*
    participants.  A case whose only participant is the manager has nobody to
    announce to, so the announce is skipped — correct behaviour, but it makes a
    fixture built that way unable to observe the emission at all.
    """
    # The store belongs to the CASE_MANAGER named here: the teardown trees commit
    # to the canonical ledger, which that role holder owns (CLP-09, ADR-0072).
    dl = SqliteDataLayer("sqlite:///:memory:", actor_id=case_manager_actor)
    case, _ = make_case_and_embargo(suffix, em_state=em_state)
    cm_participant = as_CaseParticipant(
        id_=f"{case.id_}/participants/cm",
        attributed_to=case_manager_actor,
        case_roles=[CVDRole.CASE_MANAGER],
    )
    case.case_participants.append(cm_participant.id_)
    case.actor_participant_index[case_manager_actor] = cm_participant.id_
    dl.create(cm_participant)

    for i, actor in enumerate(other_participants):
        participant = as_CaseParticipant(
            id_=f"{case.id_}/participants/p{i}",
            attributed_to=actor,
            context=case.id_,
        )
        case.case_participants.append(participant.id_)
        case.actor_participant_index[actor] = participant.id_
        dl.create(participant)

    dl.create(case)
    return case, cm_participant, dl


def setup_blackboard(
    dl: SqliteDataLayer,
    actor_id: str = "https://example.org/users/vendor",
) -> None:
    """Populate the py_trees blackboard with the DataLayer and actor_id."""
    py_trees.blackboard.Blackboard.enable_activity_stream()
    blackboard = py_trees.blackboard.Client(name="test-setup")
    blackboard.register_key(
        key="datalayer", access=py_trees.common.Access.WRITE
    )
    blackboard.register_key(
        key="actor_id", access=py_trees.common.Access.WRITE
    )
    blackboard.datalayer = dl
    blackboard.actor_id = actor_id


@pytest.fixture
def dl() -> SqliteDataLayer:
    """Return a fresh in-memory SQLite DataLayer."""
    return SqliteDataLayer(
        "sqlite:///:memory:",
        actor_id="https://test.example/api/v2/actors/test-actor",
    )
