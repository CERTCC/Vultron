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
from vultron.wire.as2.vocab.objects.case_participant import as_CaseParticipant
from vultron.wire.as2.vocab.objects.vulnerability_case import (
    as_VulnerabilityCase,
)

ACTOR_ID = "https://example.org/actors/owner"
NEW_OWNER_ID = "https://example.org/actors/coordinator"
CASE_ID = "https://example.org/cases/case-actor-node-01"
CASE_ID2 = "https://example.org/cases/case-announce-01"


@pytest.fixture
def store_for():
    """Factory: the store belonging to a given actor.

    Each test class here executes as a different actor, and a BT's store follows
    its executing actor (ADR-0070), so the store cannot be a single module-wide
    fixture. Classes override ``dl`` with the actor they run as.

    Explicitly closed: an unclosed sqlite3 connection is collected at an
    unpredictable moment and pytest promotes the resulting ResourceWarning to a
    failure via PytestUnraisableExceptionWarning.
    """
    created: list[SqliteDataLayer] = []

    def _make(actor_id: str) -> SqliteDataLayer:
        dl = SqliteDataLayer("sqlite:///:memory:", actor_id=actor_id)
        created.append(dl)
        return dl

    yield _make
    for dl in created:
        dl.close()


@pytest.fixture
def dl(store_for):
    """Default store: the new owner, whom most trees in this file execute as."""
    return store_for(NEW_OWNER_ID)


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

    @pytest.fixture
    def dl(self, store_for):
        """This class executes as ACTOR_ID, so that is its store."""
        return store_for(ACTOR_ID)

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

    def test_idempotent_skip_line_is_debug(
        self, bridge, dl, case, announce_event, caplog
    ) -> None:
        """The routine idempotency skip is DEBUG, not INFO (SL-04-007)."""
        import logging

        dl.create(case)
        tree = SeedAnnouncedCaseNode(
            case_id=CASE_ID2, case_obj=case, request=announce_event
        )

        with caplog.at_level(logging.DEBUG):
            bridge.execute_with_setup(
                tree=tree, actor_id=ACTOR_ID, activity=announce_event
            )

        skip_records = [
            r
            for r in caplog.records
            if "already exists locally" in r.getMessage()
        ]
        assert skip_records, "Expected the idempotent-skip log entry"
        assert all(r.levelno == logging.DEBUG for r in skip_records)

    def test_persisted_case_has_no_inline_participants(
        self, bridge, dl, announce_event
    ) -> None:
        """Persisted VulnerabilityCase must not carry inline CaseParticipant objects.

        Regression for #2233 write path: _build_case_object materialises inline
        participants for delivery so that _store_embedded_participants on the
        receiver side can project and persist them.  SeedAnnouncedCaseNode must
        normalise case_participants to string IDs *before* saving the case, so
        the stored row never carries stale inline snapshots that would freeze
        the RM state visible to update_participant_rm_state.
        """
        participant_id = f"{CASE_ID2}/participants/vendor-inline-001"
        actor_id = "https://example.org/actors/vendor-inline-001"

        # Simulate what _build_case_object produces: a case carrying a fully
        # materialised inline wire CaseParticipant rather than a bare string ID.
        inline_participant = as_CaseParticipant(
            id_=participant_id,
            attributed_to=actor_id,
            context=CASE_ID2,
        )
        case_with_inline = as_VulnerabilityCase(
            id_=CASE_ID2, name="Inline Participant Write-Path Test"
        )
        case_with_inline.actor_participant_index[actor_id] = participant_id
        case_with_inline.case_participants.append(inline_participant)

        tree = SeedAnnouncedCaseNode(
            case_id=CASE_ID2,
            case_obj=case_with_inline,
            request=announce_event,
        )
        result = bridge.execute_with_setup(
            tree=tree, actor_id=ACTOR_ID, activity=announce_event
        )
        assert result.status == Status.SUCCESS

        stored = dl.read(CASE_ID2)
        assert stored is not None
        for ref in stored.case_participants:
            assert isinstance(ref, str), (
                "Persisted case_participants must contain only string IDs; "
                f"found inline {type(ref).__name__!r} — write-path bug (#2233)"
            )
        # Standalone participant record must also exist
        assert (
            dl.read(participant_id) is not None
        ), "Standalone CaseParticipant record must be stored alongside the case"


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

    @pytest.fixture
    def dl(self, store_for):
        """This class executes as ACTOR_ID, so that is its store."""
        return store_for(ACTOR_ID)

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
            {
                "id_": "urn:uuid:ac2-invite-001",
                "type": "Invite",
                "actor": ACTOR_ID,
                "object_": {"type": "CoreActor", "id_": INVITEE_ID},
                "target": {"type": "VulnerabilityCase", "id_": AC3_CASE_ID},
                "context": AC3_CASE_ID,
            },
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


# ---------------------------------------------------------------------------
# EmitAddCaseParticipantNode (Issue-1689)
# ---------------------------------------------------------------------------

EMIT_ADD_CASE_ID = "https://example.org/cases/add-participant-01"
EMIT_ADD_ACTOR_ID = "https://example.org/actors/case-actor-add"
EMIT_ADD_INVITEE_ID = "https://example.org/actors/new-participant-add"
EMIT_ADD_PARTICIPANT_ID = f"{EMIT_ADD_CASE_ID}/participants/p-new"
EMIT_ADD_ACTIVITY_ID = f"{EMIT_ADD_CASE_ID}/activities/add-p-001"


def _make_add_node_fixture(dl):
    """Create a minimal CaseParticipant on the blackboard for EmitAddCaseParticipantNode tests."""
    from vultron.core.models.case_participant import CaseParticipant

    participant = CaseParticipant(
        id_=EMIT_ADD_PARTICIPANT_ID,
        attributed_to=EMIT_ADD_INVITEE_ID,
        context=EMIT_ADD_CASE_ID,
    )
    dl.create(participant)
    return participant


class TestEmitAddCaseParticipantNode:
    """Unit tests for EmitAddCaseParticipantNode."""

    @pytest.fixture
    def dl(self, store_for):
        """This class executes as EMIT_ADD_ACTOR_ID, so that is its store."""
        return store_for(EMIT_ADD_ACTOR_ID)

    def test_emits_add_activity_and_commits_ledger_entry(self, dl):
        """Happy path: emits Add(CaseParticipant) and commits ledger entry."""
        from unittest.mock import MagicMock

        from vultron.adapters.driven.trigger_activity_adapter import (
            TriggerActivityAdapter,
        )
        from vultron.core.behaviors.case.accept_invite_tree import (
            EmitAddCaseParticipantNode,
        )
        from vultron.core.models.case_ledger_entry import CaseLedgerEntry
        from vultron.wire.as2.vocab.objects.vulnerability_case import (
            as_VulnerabilityCase,
        )

        case = as_VulnerabilityCase(
            id_=EMIT_ADD_CASE_ID,
            name="add-participant-test",
            attributed_to=EMIT_ADD_ACTOR_ID,
        )
        dl.create(case)
        participant = _make_add_node_fixture(dl)

        from vultron.wire.as2.factories import add_participant_to_case_activity
        from vultron.wire.as2.vocab.objects.case_participant import (
            as_CaseParticipant,
        )

        wire_participant = as_CaseParticipant(
            id_=EMIT_ADD_PARTICIPANT_ID,
            attributed_to=EMIT_ADD_INVITEE_ID,
            context=EMIT_ADD_CASE_ID,
        )
        add_activity = add_participant_to_case_activity(
            participant=wire_participant,
            target=EMIT_ADD_CASE_ID,
            actor=EMIT_ADD_ACTOR_ID,
            id_=EMIT_ADD_ACTIVITY_ID,
        )
        dl.create(add_activity)

        mock_factory = MagicMock(spec=TriggerActivityAdapter)
        mock_factory.add_participant_to_case.return_value = (
            EMIT_ADD_ACTIVITY_ID
        )

        bridge = BTBridge(datalayer=dl, trigger_activity=mock_factory)
        node = EmitAddCaseParticipantNode(
            case_id=EMIT_ADD_CASE_ID, invitee_id=EMIT_ADD_INVITEE_ID
        )
        result = bridge.execute_with_setup(
            tree=node,
            actor_id=EMIT_ADD_ACTOR_ID,
            new_invite_participant=participant,
            invitee_already_participant=False,
        )

        assert result.status == Status.SUCCESS
        mock_factory.add_participant_to_case.assert_called_once()
        entries = [
            e
            for e in dl.list_objects("CaseLedgerEntry")
            if isinstance(e, CaseLedgerEntry) and e.case_id == EMIT_ADD_CASE_ID
        ]
        assert any(
            e.event_type == "add_case_participant" for e in entries
        ), f"Expected add_case_participant ledger entry; got {[e.event_type for e in entries]}"

    def test_snapshot_strips_bare_target_from_stored_activity(self, dl):
        """_build_snapshot must strip bare target from stored as_Add (IMPROVE-2).

        The real TriggerActivityAdapter stores the as_Add in the datalayer and
        returns its id.  model_dump() of the stored object includes
        ``"target": "<case_uri>"`` as a bare string.  _validate_canonical_entry
        rejects bare inline-object values, so _build_snapshot MUST call
        _snapshot_with_context (which calls _drop_bare_inline_refs) rather than
        returning raw model_dump output.
        """
        from unittest.mock import MagicMock

        from vultron.adapters.driven.trigger_activity_adapter import (
            TriggerActivityAdapter,
        )
        from vultron.core.behaviors.case.accept_invite_tree import (
            EmitAddCaseParticipantNode,
        )
        from vultron.core.models.case_ledger_entry import CaseLedgerEntry
        from vultron.wire.as2.factories import add_participant_to_case_activity
        from vultron.wire.as2.vocab.objects.case_participant import (
            as_CaseParticipant,
        )
        from vultron.wire.as2.vocab.objects.vulnerability_case import (
            as_VulnerabilityCase,
        )

        case = as_VulnerabilityCase(
            id_=EMIT_ADD_CASE_ID,
            name="snapshot-bare-target-test",
            attributed_to=EMIT_ADD_ACTOR_ID,
        )
        dl.create(case)
        participant = _make_add_node_fixture(dl)

        # Build and store the real as_Add activity so datalayer.read() returns it.
        # Use target as a bare string URI — that is what the real adapter does
        # (TriggerActivityAdapterActorsMixin.add_participant_to_case passes case_id
        # as the target kwarg).  model_dump() serialises this as "target": "<uri>"
        # which _validate_canonical_entry would reject without _drop_bare_inline_refs.
        wire_participant = as_CaseParticipant(
            id_=EMIT_ADD_PARTICIPANT_ID,
            attributed_to=EMIT_ADD_INVITEE_ID,
            context=EMIT_ADD_CASE_ID,
        )
        add_activity = add_participant_to_case_activity(
            participant=wire_participant,
            target=EMIT_ADD_CASE_ID,
            actor=EMIT_ADD_ACTOR_ID,
            id_=EMIT_ADD_ACTIVITY_ID,
        )
        dl.create(add_activity)

        mock_factory = MagicMock(spec=TriggerActivityAdapter)
        mock_factory.add_participant_to_case.return_value = (
            EMIT_ADD_ACTIVITY_ID
        )

        bridge = BTBridge(datalayer=dl, trigger_activity=mock_factory)
        node = EmitAddCaseParticipantNode(
            case_id=EMIT_ADD_CASE_ID, invitee_id=EMIT_ADD_INVITEE_ID
        )
        result = bridge.execute_with_setup(
            tree=node,
            actor_id=EMIT_ADD_ACTOR_ID,
            new_invite_participant=participant,
            invitee_already_participant=False,
        )

        assert result.status == Status.SUCCESS, (
            "Snapshot with stored as_Add must not fail validation "
            "(bare target must be stripped by _snapshot_with_context)"
        )
        entries = [
            e
            for e in dl.list_objects("CaseLedgerEntry")
            if isinstance(e, CaseLedgerEntry) and e.case_id == EMIT_ADD_CASE_ID
        ]
        assert any(e.event_type == "add_case_participant" for e in entries)

    def test_skips_when_already_participant(self, dl):
        """SUCCESS without emitting when invitee_already_participant=True."""
        from unittest.mock import MagicMock

        from vultron.adapters.driven.trigger_activity_adapter import (
            TriggerActivityAdapter,
        )
        from vultron.core.behaviors.case.accept_invite_tree import (
            EmitAddCaseParticipantNode,
        )
        from vultron.wire.as2.vocab.objects.vulnerability_case import (
            as_VulnerabilityCase,
        )

        case = as_VulnerabilityCase(
            id_=EMIT_ADD_CASE_ID,
            name="add-participant-skip-test",
            attributed_to=EMIT_ADD_ACTOR_ID,
        )
        dl.create(case)
        participant = _make_add_node_fixture(dl)
        mock_factory = MagicMock(spec=TriggerActivityAdapter)

        bridge = BTBridge(datalayer=dl, trigger_activity=mock_factory)
        node = EmitAddCaseParticipantNode(
            case_id=EMIT_ADD_CASE_ID, invitee_id=EMIT_ADD_INVITEE_ID
        )
        result = bridge.execute_with_setup(
            tree=node,
            actor_id=EMIT_ADD_ACTOR_ID,
            new_invite_participant=participant,
            invitee_already_participant=True,
        )

        assert result.status == Status.SUCCESS
        mock_factory.add_participant_to_case.assert_not_called()

    def test_fails_when_participant_not_on_blackboard(self, dl):
        """FAILURE when new_invite_participant is not a valid participant object."""
        from unittest.mock import MagicMock

        from vultron.adapters.driven.trigger_activity_adapter import (
            TriggerActivityAdapter,
        )
        from vultron.core.behaviors.case.accept_invite_tree import (
            EmitAddCaseParticipantNode,
        )
        from vultron.wire.as2.vocab.objects.vulnerability_case import (
            as_VulnerabilityCase,
        )

        case = as_VulnerabilityCase(
            id_=EMIT_ADD_CASE_ID,
            name="add-participant-fail-test",
            attributed_to=EMIT_ADD_ACTOR_ID,
        )
        dl.create(case)
        mock_factory = MagicMock(spec=TriggerActivityAdapter)
        bridge = BTBridge(datalayer=dl, trigger_activity=mock_factory)
        node = EmitAddCaseParticipantNode(
            case_id=EMIT_ADD_CASE_ID, invitee_id=EMIT_ADD_INVITEE_ID
        )
        result = bridge.execute_with_setup(
            tree=node,
            actor_id=EMIT_ADD_ACTOR_ID,
            new_invite_participant="not-a-participant",
            invitee_already_participant=False,
        )

        assert result.status == Status.FAILURE
        mock_factory.add_participant_to_case.assert_not_called()

    def test_to_field_contains_http_actor_urls_not_bare_uuids(self, dl):
        """to= passed to add_participant_to_case must contain HTTP actor URLs.

        Production storage keeps case.case_participants as bare UUID strings
        (e.g. "urn:uuid:…").  _resolve_actor_recipients must use
        case.actor_participant_index keys (HTTP URIs) instead, or outbox
        delivery will fail with "Request URL is missing 'http://'".
        """
        from unittest.mock import MagicMock

        from vultron.adapters.driven.trigger_activity_adapter import (
            TriggerActivityAdapter,
        )
        from vultron.core.behaviors.case.accept_invite_tree import (
            EmitAddCaseParticipantNode,
        )
        from vultron.core.models.case import VulnerabilityCase
        from vultron.core.models.case_participant import CaseParticipant

        # Two existing participants stored as bare UUID strings in case_participants
        # (matching production DataLayer storage format).
        existing_actor_1 = "https://example.org/actors/existing-actor-1"
        existing_actor_2 = "https://example.org/actors/existing-actor-2"
        existing_p1_id = "urn:uuid:11111111-0000-0000-0000-000000000001"
        existing_p2_id = "urn:uuid:22222222-0000-0000-0000-000000000002"

        case = VulnerabilityCase(
            id_=EMIT_ADD_CASE_ID,
            name="to-field-http-url-test",
            attributed_to=EMIT_ADD_ACTOR_ID,
            # bare UUID strings, as stored in production
            case_participants=[existing_p1_id, existing_p2_id],
            actor_participant_index={
                existing_actor_1: existing_p1_id,
                existing_actor_2: existing_p2_id,
            },
        )
        dl.create(case)

        participant = CaseParticipant(
            id_=EMIT_ADD_PARTICIPANT_ID,
            attributed_to=EMIT_ADD_INVITEE_ID,
            context=EMIT_ADD_CASE_ID,
        )
        dl.create(participant)

        from vultron.wire.as2.factories import add_participant_to_case_activity
        from vultron.wire.as2.vocab.objects.case_participant import (
            as_CaseParticipant as as_CP,
        )

        wire_p_to = as_CP(
            id_=EMIT_ADD_PARTICIPANT_ID,
            attributed_to=EMIT_ADD_INVITEE_ID,
            context=EMIT_ADD_CASE_ID,
        )
        add_act_to = add_participant_to_case_activity(
            participant=wire_p_to,
            target=EMIT_ADD_CASE_ID,
            actor=EMIT_ADD_ACTOR_ID,
            id_=EMIT_ADD_ACTIVITY_ID,
        )
        dl.create(add_act_to)

        mock_factory = MagicMock(spec=TriggerActivityAdapter)
        mock_factory.add_participant_to_case.return_value = (
            EMIT_ADD_ACTIVITY_ID
        )

        bridge = BTBridge(datalayer=dl, trigger_activity=mock_factory)
        node = EmitAddCaseParticipantNode(
            case_id=EMIT_ADD_CASE_ID, invitee_id=EMIT_ADD_INVITEE_ID
        )
        result = bridge.execute_with_setup(
            tree=node,
            actor_id=EMIT_ADD_ACTOR_ID,
            new_invite_participant=participant,
            invitee_already_participant=False,
        )

        assert result.status == Status.SUCCESS
        mock_factory.add_participant_to_case.assert_called_once()
        call_kwargs = mock_factory.add_participant_to_case.call_args
        to_arg = call_kwargs.kwargs.get("to") or (
            call_kwargs.args[3] if len(call_kwargs.args) > 3 else None
        )
        assert (
            to_arg is not None
        ), "to= must be passed to add_participant_to_case"
        for recipient in to_arg:
            assert recipient.startswith("http"), (
                f"to= recipients must be HTTP actor URLs, not bare IDs: {recipient!r}. "
                f"Full to= list: {to_arg}"
            )
        assert existing_actor_1 in to_arg
        assert existing_actor_2 in to_arg
        # The new invitee must NOT be in the recipients (it's the one being added)
        assert EMIT_ADD_INVITEE_ID not in to_arg


# ---------------------------------------------------------------------------
# AC-5a / AC-5b: EmitOfferCaseOwnershipTransferNode and
#               EmitAcceptCaseOwnershipTransferNode BT-layer routing tests
# ---------------------------------------------------------------------------

_OT_OWNER_ID = "https://example.org/actors/ot-owner"
_OT_CASE_ACTOR_ID = "https://example.org/actors/ot-case-actor"
_OT_TRANSFEREE_ID = "https://example.org/actors/ot-transferee"
_OT_CASE_ID = "https://example.org/cases/ot-emit-test-01"


def _make_ot_case(dl: SqliteDataLayer) -> None:
    """Seed a case with a CASE_MANAGER participant so _resolve_case_manager_id
    returns _OT_CASE_ACTOR_ID from _OT_CASE_ID."""
    from vultron.core.models.case_participant import CaseParticipant
    from vultron.enums.roles import CVDRole as _CVDRole
    from vultron.wire.as2.vocab.objects.vulnerability_case import (
        as_VulnerabilityCase as _VC,
    )

    case = _VC(
        id_=_OT_CASE_ID,
        name="OT Emit Test",
        attributed_to=_OT_OWNER_ID,
    )
    owner_p = CaseParticipant(
        id_=f"{_OT_CASE_ID}/participants/owner",
        attributed_to=_OT_OWNER_ID,
        context=_OT_CASE_ID,
        case_roles=[_CVDRole.CASE_OWNER],
    )
    ca_p = CaseParticipant(
        id_=f"{_OT_CASE_ID}/participants/case-actor",
        attributed_to=_OT_CASE_ACTOR_ID,
        context=_OT_CASE_ID,
        case_roles=[_CVDRole.CASE_MANAGER],
    )
    case.actor_participant_index[_OT_OWNER_ID] = owner_p.id_
    case.actor_participant_index[_OT_CASE_ACTOR_ID] = ca_p.id_
    case.case_participants.append(owner_p.id_)
    case.case_participants.append(ca_p.id_)
    dl.create(case)
    dl.create(owner_p)
    dl.create(ca_p)


class TestEmitOwnershipTransferNodes:
    """AC-5a / AC-5b: Emit nodes address activities to the CaseActor (ADR-0053).

    The two tests execute as *different* actors — the offering owner and the
    accepting transferee — so each builds its own store rather than sharing one.
    Each seeds the case into its own replica, which is what actually holds in
    production: both parties have a replica naming the same CaseActor.
    """

    def test_emit_offer_to_is_case_actor_id(self, store_for):
        dl = store_for(_OT_OWNER_ID)
        # AC-5a: EmitOfferCaseOwnershipTransferNode sets to=[case_actor_id].
        from vultron.adapters.driven.trigger_activity_adapter import (
            TriggerActivityAdapter,
        )
        from vultron.core.behaviors.case.nodes.ownership_transfer import (
            EmitOfferCaseOwnershipTransferNode,
        )

        _make_ot_case(dl)

        captured: dict = {}
        node = EmitOfferCaseOwnershipTransferNode(
            case_id=_OT_CASE_ID,
            transferee_id=_OT_TRANSFEREE_ID,
            captured=captured,
        )
        bridge = BTBridge(
            datalayer=dl,
            trigger_activity=TriggerActivityAdapter(dl),
        )
        result = bridge.execute_with_setup(tree=node, actor_id=_OT_OWNER_ID)

        assert (
            result.status == Status.SUCCESS
        ), f"EmitOfferCaseOwnershipTransferNode must succeed; feedback: {node.feedback_message}"
        activity = captured.get("activity", {})
        # ADR-0053 / CM-21-005: Offer is routed to the CaseActor, not the transferee.
        assert _OT_CASE_ACTOR_ID in activity.get("to", []), (
            f"Offer must be addressed to the CaseActor ({_OT_CASE_ACTOR_ID}); "
            f"got to={activity.get('to')!r}"
        )
        # The transferee is named as the intended new owner in the target field.
        assert _OT_TRANSFEREE_ID == activity.get("target"), (
            f"Offer.target must name the transferee ({_OT_TRANSFEREE_ID}); "
            f"got target={activity.get('target')!r}"
        )

    def test_emit_accept_to_is_case_actor_id(self, store_for):
        """AC-5b: EmitAcceptCaseOwnershipTransferNode sets to=[case_actor_id].

        Uses a mock TriggerActivityAdapter to capture the ``to`` kwarg that
        the node passes to ``accept_case_ownership_transfer()``.  The node
        resolves the CaseActor via ``_resolve_case_manager_id`` *before*
        calling the factory, so the mock's call_args faithfully records the
        routing decision (ADR-0053 / CM-21-006).
        """
        dl = store_for(_OT_TRANSFEREE_ID)
        from unittest.mock import MagicMock

        from vultron.adapters.driven.trigger_activity_adapter import (
            TriggerActivityAdapter,
        )
        from vultron.core.behaviors.case.nodes.ownership_transfer import (
            EmitAcceptCaseOwnershipTransferNode,
        )

        _make_ot_case(dl)

        _accept_id = "https://example.org/activities/ot-accept-mock-01"
        mock_factory = MagicMock(spec=TriggerActivityAdapter)
        mock_factory.accept_case_ownership_transfer.return_value = (
            _accept_id,
            {"id": _accept_id, "type": "Accept", "to": [_OT_CASE_ACTOR_ID]},
        )

        node = EmitAcceptCaseOwnershipTransferNode(
            offer_id="https://example.org/activities/ot-offer-01",
            case_id=_OT_CASE_ID,
        )
        bridge = BTBridge(datalayer=dl, trigger_activity=mock_factory)
        result = bridge.execute_with_setup(
            tree=node, actor_id=_OT_TRANSFEREE_ID
        )

        assert (
            result.status == Status.SUCCESS
        ), f"EmitAcceptCaseOwnershipTransferNode must succeed; feedback: {node.feedback_message}"
        mock_factory.accept_case_ownership_transfer.assert_called_once()
        call_kwargs = mock_factory.accept_case_ownership_transfer.call_args
        to_arg = call_kwargs.kwargs.get("to") or (
            call_kwargs.args[2] if len(call_kwargs.args) > 2 else None
        )
        # ADR-0053 / CM-21-006: Accept is routed to the CaseActor.
        assert (
            to_arg is not None
        ), "to= must be passed to accept_case_ownership_transfer"
        assert _OT_CASE_ACTOR_ID in to_arg, (
            f"Accept must be addressed to the CaseActor ({_OT_CASE_ACTOR_ID}); "
            f"got to={to_arg!r}"
        )
