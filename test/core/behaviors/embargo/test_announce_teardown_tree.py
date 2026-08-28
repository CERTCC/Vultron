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

"""Integration tests for remove_embargo_from_case_tree.

Verifies that SendAnnounceEmbargoEventNode fires (and does not fire) in the
correct branches of the TeardownIfActive Selector.
"""

from typing import cast
from unittest.mock import MagicMock

import py_trees
import pytest

from vultron.core.behaviors.bridge import BTBridge
from vultron.core.behaviors.embargo.announce_teardown_tree import (
    remove_embargo_from_case_tree,
)
from vultron.core.models.activity import VultronActivity
from vultron.core.models.base import VultronObject
from vultron.core.models.case import VulnerabilityCase
from vultron.core.models.events.embargo import (
    RemoveEmbargoEventFromCaseReceivedEvent,
)
from vultron.core.states.em import EM
from vultron.wire.as2.vocab.objects.vulnerability_case import (  # noqa: F401
    as_VulnerabilityCase,
)

from test.core.behaviors.embargo.nodes.conftest import (
    CASE_MANAGER_ACTOR,
    make_case_and_embargo,
    make_case_with_manager,
)

# Kept for objects that reference the vendor; the trees below execute as the
# CASE_MANAGER, which is who the ledger commit is gated on.
ACTOR_ID = "https://example.org/actors/vendor"


@pytest.fixture(autouse=True)
def clear_blackboard():
    py_trees.blackboard.Blackboard.storage.clear()


def _make_factory(
    announce_id: str = "https://example.org/activities/ann1",
) -> MagicMock:
    factory = MagicMock()
    factory.announce_embargo.return_value = (announce_id, {})
    return factory


def _make_remove_event(
    case, embargo, activity_id: str
) -> RemoveEmbargoEventFromCaseReceivedEvent:
    """A Remove(EmbargoEvent) received event that carries its own activity.

    The tree's ledger commit builds ``payloadSnapshot`` from
    ``event.activity`` when present, and CLP-07 requires that snapshot to have a
    non-empty ``actor``.  An event with no ``activity`` falls back to dumping the
    *event*, whose ``actor_id`` serializes as ``actorId`` — so
    ``payloadSnapshot.actor`` is absent and the commit fails validation.

    Before the commit was role-gated it never ran in these tests, so the missing
    activity did not matter.  Once the store, the receiving actor and the
    CASE_MANAGER role holder were aligned the commit began executing, and the gap
    surfaced as a bare ``Status.FAILURE``.
    """
    return RemoveEmbargoEventFromCaseReceivedEvent(
        activity_id=activity_id,
        actor_id=ACTOR_ID,
        object_=VultronObject(id_=embargo.id_),
        origin=VultronObject(id_=case.id_),
        receiving_actor_id=CASE_MANAGER_ACTOR,
        activity=VultronActivity(
            id_=activity_id,
            type_="Remove",
            actor=ACTOR_ID,
            object_=embargo.id_,
            origin=case.id_,
            context=case.id_,
        ),
    )


class TestRemoveEmbargoFromCaseTreeAnnounce:
    """Verify Announce(EmbargoEvent) emission wiring in remove_embargo_from_case_tree."""

    @pytest.mark.spec("EMB-07-001")
    @pytest.mark.spec("EMB-13-001")
    def test_emits_announce_when_active_embargo_removed(self):
        """ActiveTeardown path emits Announce(EmbargoEvent) to outbox."""
        case, _, dl = make_case_with_manager("atrt1", em_state=EM.ACTIVE)
        _, embargo = make_case_and_embargo("atrt1")
        dl.create(embargo)
        factory = _make_factory()

        tree = remove_embargo_from_case_tree(
            case_id=case.id_, embargo_id=embargo.id_
        )
        bridge = BTBridge(datalayer=dl, trigger_activity=factory)
        activity = _make_remove_event(
            case, embargo, "https://example.org/activities/remove1"
        )
        result = bridge.execute_with_setup(
            tree=tree, actor_id=CASE_MANAGER_ACTOR, activity=activity
        )

        assert result.status == py_trees.common.Status.SUCCESS
        # Authored by the executing actor — the CASE_MANAGER the commit is gated
        # on — and addressed to the case's *other* participants. It used to be
        # addressed to the manager, which once the tree became role-gated meant
        # the manager announcing the teardown to itself.
        factory.announce_embargo.assert_called_once_with(
            embargo_id=embargo.id_,
            case_id=case.id_,
            actor=CASE_MANAGER_ACTOR,
            to=[ACTOR_ID],
        )
        outbox = dl.outbox_list()
        assert "https://example.org/activities/ann1" in outbox
        updated = cast(VulnerabilityCase, dl.read(case.id_))
        assert updated.current_status.em.state == EM.EXITED

    def test_no_announce_when_embargo_not_active(self):
        """EmbargoWasNotActive path does NOT emit Announce(EmbargoEvent)."""
        # Build a case that starts in PROPOSED state (not ACTIVE), so the
        # IsActiveEmbargoNode guard fails and the ActiveTeardown Sequence is
        # skipped — the Selector falls through to EmbargoWasNotActive.
        case, _, dl = make_case_with_manager("atrt2", em_state=EM.PROPOSED)
        _, embargo = make_case_and_embargo("atrt2")
        dl.create(embargo)
        object.__setattr__(case, "active_embargo", None)
        case.proposed_embargoes.append(embargo.id_)
        dl.save(case)
        factory = _make_factory()

        tree = remove_embargo_from_case_tree(
            case_id=case.id_, embargo_id=embargo.id_
        )
        bridge = BTBridge(datalayer=dl, trigger_activity=factory)
        activity = _make_remove_event(
            case, embargo, "https://example.org/activities/remove2"
        )
        result = bridge.execute_with_setup(
            tree=tree, actor_id=CASE_MANAGER_ACTOR, activity=activity
        )

        assert result.status == py_trees.common.Status.SUCCESS
        factory.announce_embargo.assert_not_called()
        assert dl.outbox_list() == []

    def test_announce_skipped_gracefully_when_no_factory(self):
        """Tree succeeds when factory is absent (no announce emitted)."""
        case, _, dl = make_case_with_manager("atrt3", em_state=EM.ACTIVE)
        _, embargo = make_case_and_embargo("atrt3")
        dl.create(embargo)

        tree = remove_embargo_from_case_tree(
            case_id=case.id_, embargo_id=embargo.id_
        )
        bridge = BTBridge(datalayer=dl)  # no trigger_activity
        activity = _make_remove_event(
            case, embargo, "https://example.org/activities/remove3"
        )
        result = bridge.execute_with_setup(
            tree=tree, actor_id=CASE_MANAGER_ACTOR, activity=activity
        )

        assert result.status == py_trees.common.Status.SUCCESS
        updated = cast(VulnerabilityCase, dl.read(case.id_))
        assert updated.current_status.em.state == EM.EXITED
