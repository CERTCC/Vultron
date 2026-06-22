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

"""Tests for AcceptCaseOwnershipTransferNode and SeedAnnouncedCaseNode."""

from typing import Any, cast

import pytest
from py_trees.common import Status

from vultron.adapters.driven.datalayer_sqlite import SqliteDataLayer
from vultron.core.behaviors.bridge import BTBridge
from vultron.core.behaviors.case.nodes.actor import (
    AcceptCaseOwnershipTransferNode,
)
from vultron.core.behaviors.case.nodes.announce import SeedAnnouncedCaseNode
from vultron.core.models.events import MessageSemantics
from vultron.core.models.events.actor import (
    AnnounceVulnerabilityCaseReceivedEvent,
)
from vultron.semantic_registry import extract_event
from vultron.wire.as2.factories import announce_vulnerability_case_activity
from vultron.wire.as2.vocab.objects.vulnerability_case import VulnerabilityCase

ACTOR_ID = "https://example.org/actors/owner"
NEW_OWNER_ID = "https://example.org/actors/coordinator"
CASE_ID = "https://example.org/cases/case-actor-node-01"
CASE_ID2 = "https://example.org/cases/case-announce-01"


@pytest.fixture
def dl():
    return SqliteDataLayer("sqlite:///:memory:")


@pytest.fixture
def bridge(dl):
    return BTBridge(datalayer=dl)


# ---------------------------------------------------------------------------
# AcceptCaseOwnershipTransferNode
# ---------------------------------------------------------------------------


class TestAcceptCaseOwnershipTransferNode:
    """Unit tests for AcceptCaseOwnershipTransferNode."""

    def test_transfers_ownership(self, bridge, dl) -> None:
        """Happy path: case.attributed_to updated to new_owner_id."""
        case = VulnerabilityCase(
            id_=CASE_ID,
            name="OT Node Test",
            attributed_to=ACTOR_ID,
        )
        dl.create(case)
        tree = AcceptCaseOwnershipTransferNode(
            case_id=CASE_ID, new_owner_id=NEW_OWNER_ID
        )
        result = bridge.execute_with_setup(tree=tree, actor_id=NEW_OWNER_ID)
        assert result.status == Status.SUCCESS
        refreshed = cast(Any, dl.read(CASE_ID))
        assert refreshed is not None
        owner = refreshed.attributed_to
        owner_id = (
            owner
            if isinstance(owner, str)
            else getattr(owner, "id_", str(owner))
        )
        assert owner_id == NEW_OWNER_ID

    def test_idempotent_when_already_owned(self, bridge, dl) -> None:
        """SUCCESS without mutation when case already has the new owner."""
        case = VulnerabilityCase(
            id_=CASE_ID,
            name="OT Node Idempotent",
            attributed_to=NEW_OWNER_ID,
        )
        dl.create(case)
        tree = AcceptCaseOwnershipTransferNode(
            case_id=CASE_ID, new_owner_id=NEW_OWNER_ID
        )
        result = bridge.execute_with_setup(tree=tree, actor_id=NEW_OWNER_ID)
        assert result.status == Status.SUCCESS

    def test_fails_when_case_not_found(self, bridge, dl) -> None:
        """FAILURE when case is absent from DataLayer."""
        tree = AcceptCaseOwnershipTransferNode(
            case_id="https://example.org/cases/missing",
            new_owner_id=NEW_OWNER_ID,
        )
        result = bridge.execute_with_setup(tree=tree, actor_id=NEW_OWNER_ID)
        assert result.status == Status.FAILURE


# ---------------------------------------------------------------------------
# SeedAnnouncedCaseNode
# ---------------------------------------------------------------------------


@pytest.fixture
def case():
    return VulnerabilityCase(id_=CASE_ID2, name="Seed Announce Test")


@pytest.fixture
def announce_event(case) -> AnnounceVulnerabilityCaseReceivedEvent:
    activity = announce_vulnerability_case_activity(
        case, actor=ACTOR_ID, context=case.id_
    )
    event = extract_event(activity)
    assert event.semantic_type == MessageSemantics.ANNOUNCE_VULNERABILITY_CASE
    return cast(AnnounceVulnerabilityCaseReceivedEvent, event)


class TestSeedAnnouncedCaseNode:
    """Unit tests for SeedAnnouncedCaseNode."""

    def test_saves_case_when_absent(
        self, bridge, dl, case, announce_event
    ) -> None:
        """MV-10-003: case is persisted when not yet in DataLayer."""
        assert dl.read(CASE_ID2) is None
        tree = SeedAnnouncedCaseNode(
            case_id=CASE_ID2, case_obj=case, request=announce_event
        )
        result = bridge.execute_with_setup(
            tree=tree, actor_id=ACTOR_ID, activity=announce_event
        )
        assert result.status == Status.SUCCESS
        assert dl.read(CASE_ID2) is not None

    def test_idempotent_when_case_exists(
        self, bridge, dl, case, announce_event
    ) -> None:
        """MV-10-004: SUCCESS without overwrite when case already present."""
        dl.create(case)
        tree = SeedAnnouncedCaseNode(
            case_id=CASE_ID2, case_obj=case, request=announce_event
        )
        result = bridge.execute_with_setup(
            tree=tree, actor_id=ACTOR_ID, activity=announce_event
        )
        assert result.status == Status.SUCCESS
        assert dl.read(CASE_ID2) is not None
