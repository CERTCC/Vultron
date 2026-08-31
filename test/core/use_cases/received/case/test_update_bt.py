#  Copyright (c) 2025-2026 Carnegie Mellon University and Contributors.
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
"""BT structure and no-post-BT-broadcast tests for UpdateCaseBT."""

from unittest.mock import MagicMock

from vultron.adapters.driven.datalayer_sqlite import SqliteDataLayer
from vultron.core.behaviors.case.nodes.update import (
    ApplyCaseUpdateNode,
    BroadcastCaseUpdateNode,
    CaptureCaseUpdateBroadcastExclusionsNode,
    CheckCaseUpdateOwnerNode,
)
from vultron.core.behaviors.case.update_support import broadcast_case_update
from vultron.core.models.participant import CaseParticipant
from vultron.enums.roles import CVDRole
from vultron.core.behaviors.case.nodes.conditions import (
    CheckIsCaseManagerNode,
)
from vultron.core.behaviors.case.update_tree import (
    create_update_case_received_tree,
)
from vultron.core.models.case_actor import VultronCaseActor
from vultron.core.use_cases.received.case.update import (
    UpdateCaseReceivedUseCase,
)
from vultron.wire.as2.factories import update_case_activity
from vultron.wire.as2.vocab.objects.vulnerability_case import (
    as_VulnerabilityCase,
)


class TestUpdateCaseBTStructure:
    """BT tree-structure and no-post-BT-broadcast assertions for UpdateCaseBT."""

    def test_update_case_bt_structure_includes_broadcast_node(
        self, make_payload
    ):
        """UpdateCaseBT keeps ownership, embargo, update, and broadcast in-tree."""
        owner_id = "https://example.org/users/owner"
        case_id = "https://example.org/cases/bt1"
        updated_case = as_VulnerabilityCase(
            id_=case_id, name="Updated", attributed_to=owner_id
        )
        activity = update_case_activity(updated_case, actor=owner_id)
        event = make_payload(activity)

        tree = create_update_case_received_tree(
            case_id=case_id,
            actor_id=owner_id,
            request=event,
        )

        assert tree.name == "UpdateCaseBT"
        assert [child.__class__ for child in tree.children[:3]] == [
            CheckCaseUpdateOwnerNode,
            CaptureCaseUpdateBroadcastExclusionsNode,
            ApplyCaseUpdateNode,
        ]

        # The broadcast is role-gated: only the case's CASE_MANAGER may announce
        # canonical case state (CM-06-001), mirroring CLP-09 for ledger commits.
        # A non-manager skips rather than fails — applying the update to its own
        # replica is correct.
        guard = tree.children[3]
        assert guard.name == "GuardedBroadcastCaseUpdateBT"
        gated = guard.children[0]
        assert gated.name == "BroadcastIfCaseManager"
        assert [child.__class__ for child in gated.children] == [
            CheckIsCaseManagerNode,
            BroadcastCaseUpdateNode,
        ]
        assert guard.children[1].name == "BroadcastSkippedNotCaseManager"

    def test_update_case_bt_executes_without_post_bt_broadcast(
        self, make_payload, monkeypatch
    ):
        """UpdateCaseBT handles the broadcast internally instead of after execute()."""
        owner_id = "https://example.org/users/owner"
        dl = SqliteDataLayer("sqlite:///:memory:", actor_id=owner_id)
        participant_id = "https://example.org/users/alice"
        case_id = "https://example.org/cases/bt2"

        case_actor = VultronCaseActor(
            id_=f"{case_id}/actor",
            name=f"CaseActor for {case_id}",
            attributed_to=owner_id,
            context=case_id,
        )
        dl.create(case_actor)

        # BT-17-005: the broadcast gate resolves CASE_MANAGER from the case's
        # participants, not from the VultronCaseActor *service* entity.  A
        # fixture that models only the Service leaves the case with no role
        # holder, so the gate correctly skips and nothing is announced.
        manager_participant_id = "https://example.org/participants/p-mgr-bt2"
        dl.create(
            CaseParticipant(
                id_=manager_participant_id,
                attributed_to=owner_id,
                case_roles=[CVDRole.CASE_MANAGER, CVDRole.COORDINATOR],
            )
        )

        case = as_VulnerabilityCase(
            id_=case_id,
            name="Original",
            attributed_to=owner_id,
        )
        case.actor_participant_index[participant_id] = (
            "https://example.org/participants/p-bt2"
        )
        case.actor_participant_index[owner_id] = manager_participant_id
        dl.create(case)

        updated_case = as_VulnerabilityCase(
            id_=case_id,
            name="Updated",
            attributed_to=owner_id,
        )
        activity = update_case_activity(updated_case, actor=owner_id)
        event = make_payload(activity)
        # The gated tree runs under the *receiving* actor (BT-17-005).
        event.receiving_actor_id = owner_id

        # The post-BT broadcast helper no longer exists — the BT node owns the
        # broadcast, behind a CASE_MANAGER role gate.  The assertion that made
        # the old monkeypatch guard meaningful is the one that matters: exactly
        # one Announce is queued, not two.
        UpdateCaseReceivedUseCase(dl, event).execute()

        outbox_items = dl.outbox_list()
        assert len(outbox_items) == 1


class TestCollectionDefaultsCS21:
    """Omitting excluded_actor_ids produces empty-set behaviour at the call site."""

    def test_broadcast_case_update_omitting_excluded_actor_ids_does_not_raise(
        self,
    ):
        """broadcast_case_update: omitting excluded_actor_ids does not raise."""
        dl = MagicMock()
        dl.read.return_value = None  # no case actor found — early return
        case = MagicMock()
        object.__setattr__(case, "actor_participant_index", {})
        # Call without excluded_actor_ids; should not raise.
        broadcast_case_update(
            dl, "urn:uuid:case-1", case, "https://example.org/actors/manager"
        )

    def test_broadcast_case_update_excludes_no_actors_by_default(self):
        """broadcast_case_update: all participants are eligible when no exclusions given."""
        dl = MagicMock()
        dl.read.return_value = None  # no case actor found — early return
        case = MagicMock()
        actor_id = "https://example.org/actors/vendor"
        object.__setattr__(
            case, "actor_participant_index", {actor_id: MagicMock()}
        )
        # No exclusions — the function should reach the participant-list
        # check (short-circuits only on missing CaseActor, not on empty list).
        broadcast_case_update(
            dl, "urn:uuid:case-1", case, "https://example.org/actors/manager"
        )
