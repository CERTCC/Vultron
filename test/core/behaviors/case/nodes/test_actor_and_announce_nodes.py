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

"""Tests for AcceptCaseOwnershipTransferNode, SeedAnnouncedCaseNode,
and EmitInviteActorToCaseNode._read_suggested_roles."""

from typing import Any, cast

import py_trees
import pytest
from py_trees.common import Status

from vultron.adapters.driven.datalayer_sqlite import SqliteDataLayer
from vultron.core.behaviors.bridge import BTBridge
from vultron.core.behaviors.case.nodes.actor import (
    EmitInviteActorToCaseNode,
)
from vultron.core.behaviors.case.nodes.ownership_transfer import (
    AcceptCaseOwnershipTransferNode,
)
from vultron.core.behaviors.case.nodes.announce import SeedAnnouncedCaseNode
from vultron.core.models.case_participant import CaseParticipant
from vultron.core.models.events import MessageSemantics
from vultron.core.models.events.actor import (
    AnnounceVulnerabilityCaseReceivedEvent,
)
from vultron.enums.roles import CVDRole
from vultron.semantic_registry import extract_event
from vultron.wire.as2.factories import announce_vulnerability_case_activity
from vultron.wire.as2.vocab.objects.vulnerability_case import (
    as_VulnerabilityCase,
)

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
        case = as_VulnerabilityCase(
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
        case = as_VulnerabilityCase(
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

    def test_grants_case_owner_role_to_participant(self, bridge, dl) -> None:
        """New owner's participant record gains CVDRole.CASE_OWNER on transfer."""
        participant = CaseParticipant(
            id_="https://example.org/participants/p-new-owner",
            attributed_to=NEW_OWNER_ID,
            context=CASE_ID,
            case_roles=[CVDRole.COORDINATOR],
        )
        dl.create(participant)
        case = as_VulnerabilityCase(
            id_=CASE_ID,
            name="OT Role Grant Test",
            attributed_to=ACTOR_ID,
            actor_participant_index={
                NEW_OWNER_ID: participant.id_,
            },
        )
        dl.create(case)
        tree = AcceptCaseOwnershipTransferNode(
            case_id=CASE_ID, new_owner_id=NEW_OWNER_ID
        )
        result = bridge.execute_with_setup(tree=tree, actor_id=NEW_OWNER_ID)
        assert result.status == Status.SUCCESS
        refreshed_participant = cast(Any, dl.read(participant.id_))
        assert refreshed_participant is not None
        assert CVDRole.CASE_OWNER in refreshed_participant.case_roles

    def test_strips_case_owner_role_from_previous_owner(
        self, bridge, dl
    ) -> None:
        """Previous owner's participant loses CVDRole.CASE_OWNER on transfer (CM-21-003)."""
        old_owner_participant = CaseParticipant(
            id_="https://example.org/participants/p-old-owner",
            attributed_to=ACTOR_ID,
            context=CASE_ID,
            case_roles=[CVDRole.CASE_OWNER, CVDRole.COORDINATOR],
        )
        new_owner_participant = CaseParticipant(
            id_="https://example.org/participants/p-new-owner",
            attributed_to=NEW_OWNER_ID,
            context=CASE_ID,
            case_roles=[CVDRole.COORDINATOR],
        )
        dl.create(old_owner_participant)
        dl.create(new_owner_participant)
        case = as_VulnerabilityCase(
            id_=CASE_ID,
            name="OT Role Strip Test",
            attributed_to=ACTOR_ID,
            actor_participant_index={
                ACTOR_ID: old_owner_participant.id_,
                NEW_OWNER_ID: new_owner_participant.id_,
            },
        )
        dl.create(case)
        tree = AcceptCaseOwnershipTransferNode(
            case_id=CASE_ID, new_owner_id=NEW_OWNER_ID
        )
        result = bridge.execute_with_setup(tree=tree, actor_id=NEW_OWNER_ID)
        assert result.status == Status.SUCCESS
        refreshed_old = cast(Any, dl.read(old_owner_participant.id_))
        assert refreshed_old is not None
        assert CVDRole.CASE_OWNER not in refreshed_old.case_roles
        # Other roles are preserved — CM-21-003
        assert CVDRole.COORDINATOR in refreshed_old.case_roles

    def test_at_most_one_case_owner_after_transfer(self, bridge, dl) -> None:
        """Exactly one participant holds CVDRole.CASE_OWNER after transfer (CM-21-001)."""
        old_owner_participant = CaseParticipant(
            id_="https://example.org/participants/p-old-owner",
            attributed_to=ACTOR_ID,
            context=CASE_ID,
            case_roles=[CVDRole.CASE_OWNER],
        )
        new_owner_participant = CaseParticipant(
            id_="https://example.org/participants/p-new-owner",
            attributed_to=NEW_OWNER_ID,
            context=CASE_ID,
            case_roles=[CVDRole.COORDINATOR],
        )
        dl.create(old_owner_participant)
        dl.create(new_owner_participant)
        case = as_VulnerabilityCase(
            id_=CASE_ID,
            name="OT At-Most-One Test",
            attributed_to=ACTOR_ID,
            actor_participant_index={
                ACTOR_ID: old_owner_participant.id_,
                NEW_OWNER_ID: new_owner_participant.id_,
            },
        )
        dl.create(case)
        tree = AcceptCaseOwnershipTransferNode(
            case_id=CASE_ID, new_owner_id=NEW_OWNER_ID
        )
        result = bridge.execute_with_setup(tree=tree, actor_id=NEW_OWNER_ID)
        assert result.status == Status.SUCCESS
        all_participants = [
            cast(Any, dl.read(old_owner_participant.id_)),
            cast(Any, dl.read(new_owner_participant.id_)),
        ]
        owners = [
            p for p in all_participants if CVDRole.CASE_OWNER in p.case_roles
        ]
        assert len(owners) == 1
        assert owners[0].id_ == new_owner_participant.id_

    def test_atomic_rollback_on_save_failure(self, bridge, dl) -> None:
        """Failed save_many leaves both participants unchanged (CM-21-004)."""
        from unittest.mock import patch

        old_owner_participant = CaseParticipant(
            id_="https://example.org/participants/p-old-owner",
            attributed_to=ACTOR_ID,
            context=CASE_ID,
            case_roles=[CVDRole.CASE_OWNER],
        )
        new_owner_participant = CaseParticipant(
            id_="https://example.org/participants/p-new-owner",
            attributed_to=NEW_OWNER_ID,
            context=CASE_ID,
            case_roles=[CVDRole.COORDINATOR],
        )
        dl.create(old_owner_participant)
        dl.create(new_owner_participant)
        case = as_VulnerabilityCase(
            id_=CASE_ID,
            name="OT Atomic Test",
            attributed_to=ACTOR_ID,
            actor_participant_index={
                ACTOR_ID: old_owner_participant.id_,
                NEW_OWNER_ID: new_owner_participant.id_,
            },
        )
        dl.create(case)

        # Patch save_many to raise, simulating a storage failure mid-commit.
        # BTBridge catches and logs the exception rather than re-raising it, so
        # we assert on DataLayer state — not on the raised exception.
        with patch.object(
            dl, "save_many", side_effect=RuntimeError("db down")
        ):
            tree = AcceptCaseOwnershipTransferNode(
                case_id=CASE_ID, new_owner_id=NEW_OWNER_ID
            )
            bridge.execute_with_setup(tree=tree, actor_id=NEW_OWNER_ID)

        # Because save_many was never called, no write reached the DataLayer.
        # Both participants must be exactly as they were before the attempt.
        old_refreshed = cast(Any, dl.read(old_owner_participant.id_))
        new_refreshed = cast(Any, dl.read(new_owner_participant.id_))
        assert (
            CVDRole.CASE_OWNER in old_refreshed.case_roles
        ), "CM-21-004: old owner should still hold CASE_OWNER after failed transfer"
        assert (
            CVDRole.CASE_OWNER not in new_refreshed.case_roles
        ), "CM-21-004: new owner must not gain CASE_OWNER from a failed transfer"


# ---------------------------------------------------------------------------
# SeedAnnouncedCaseNode
# ---------------------------------------------------------------------------


@pytest.fixture
def case():
    return as_VulnerabilityCase(id_=CASE_ID2, name="Seed Announce Test")


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


# ---------------------------------------------------------------------------
# EmitInviteActorToCaseNode._read_suggested_roles (AC-3, Issue-1405)
# ---------------------------------------------------------------------------

INVITEE_ID = "https://example.org/actors/invitee-ac3"
AC3_CASE_ID = "https://example.org/cases/ac3-case"


class TestEmitInviteActorToCaseNodeReadSuggestedRoles:
    """AC-3: _read_suggested_roles() returns None when suggested_roles absent."""

    def setup_method(self):
        py_trees.blackboard.Blackboard.enable_activity_stream()
        self.node = EmitInviteActorToCaseNode(
            invitee_id=INVITEE_ID,
            case_id=AC3_CASE_ID,
        )
        self.node.setup()

    def teardown_method(self):
        py_trees.blackboard.Blackboard.disable_activity_stream()
        py_trees.blackboard.Blackboard.clear()

    def test_returns_none_when_key_absent(self):
        """AC-3: _read_suggested_roles() returns None on KeyError (key not set)."""
        result = self.node._read_suggested_roles()
        assert (
            result is None
        ), f"AC-3: expected None when suggested_roles absent, got {result!r}"


class TestEmitInviteActorToCaseNodePassesRolesNoneToFactory:
    """AC-2 (ISSUE-1406): factory.invite_actor_to_case() called with roles=None.

    When ``suggested_roles`` is absent from the blackboard (as in the
    ``create_accept_actor_recommendation_received_tree`` path), the node
    must pass ``roles=None`` to the factory — no silent default substitution
    (ADR-0032, BT-HELPER-01).
    """

    @pytest.fixture(autouse=True)
    def clear_blackboard(self):
        py_trees.blackboard.Blackboard.storage.clear()
        yield
        py_trees.blackboard.Blackboard.storage.clear()

    def test_invite_actor_to_case_called_with_roles_none(self, dl):
        """AC-2: roles=None passed to factory when suggested_roles absent."""
        from unittest.mock import MagicMock

        from vultron.adapters.driven.trigger_activity_adapter import (
            TriggerActivityAdapter,
        )
        from vultron.wire.as2.vocab.objects.vulnerability_case import (
            as_VulnerabilityCase,
        )

        # attributed_to triggers genesis_hash computation so the internal
        # commit_log_entry_tree inside EmitInviteActorToCaseNode can bootstrap.
        case = as_VulnerabilityCase(
            id_=AC3_CASE_ID,
            name="AC2 test case",
            attributed_to=ACTOR_ID,
        )
        dl.create(case)

        mock_factory = MagicMock(spec=TriggerActivityAdapter)
        mock_factory.invite_actor_to_case.return_value = (
            "urn:uuid:ac2-invite-001",
            {"id_": "urn:uuid:ac2-invite-001"},
        )

        bridge = BTBridge(datalayer=dl, trigger_activity=mock_factory)
        node = EmitInviteActorToCaseNode(
            invitee_id=INVITEE_ID,
            case_id=AC3_CASE_ID,
        )
        result = bridge.execute_with_setup(tree=node, actor_id=ACTOR_ID)

        assert result.status == Status.SUCCESS
        mock_factory.invite_actor_to_case.assert_called_once()
        call_kwargs = mock_factory.invite_actor_to_case.call_args
        actual_roles = call_kwargs.kwargs.get(
            "roles",
            call_kwargs.args[3] if len(call_kwargs.args) > 3 else "MISSING",
        )
        assert actual_roles is None, (
            f"AC-2: invite_actor_to_case must be called with roles=None "
            f"when suggested_roles is absent, got {actual_roles!r}"
        )
