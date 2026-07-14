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
from vultron.core.behaviors.case.update_tree import (
    create_update_case_received_tree,
)
from vultron.core.models.case_actor import VultronCaseActor
from vultron.core.use_cases.received.case.update import (
    UpdateCaseReceivedUseCase,
)
from vultron.wire.as2.factories import update_case_activity
from vultron.wire.as2.vocab.objects.vulnerability_case import VulnerabilityCase


class TestUpdateCaseBTStructure:
    """BT tree-structure and no-post-BT-broadcast assertions for UpdateCaseBT."""

    def test_update_case_bt_structure_includes_broadcast_node(
        self, make_payload
    ):
        """UpdateCaseBT keeps ownership, embargo, update, and broadcast in-tree."""
        owner_id = "https://example.org/users/owner"
        case_id = "https://example.org/cases/bt1"
        updated_case = VulnerabilityCase(
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
        assert [child.__class__ for child in tree.children] == [
            CheckCaseUpdateOwnerNode,
            CaptureCaseUpdateBroadcastExclusionsNode,
            ApplyCaseUpdateNode,
            BroadcastCaseUpdateNode,
        ]

    def test_update_case_bt_executes_without_post_bt_broadcast(
        self, make_payload, monkeypatch
    ):
        """UpdateCaseBT handles the broadcast internally instead of after execute()."""
        dl = SqliteDataLayer("sqlite:///:memory:")
        owner_id = "https://example.org/users/owner"
        participant_id = "https://example.org/users/alice"
        case_id = "https://example.org/cases/bt2"

        case_actor = VultronCaseActor(
            id_=f"{case_id}/actor",
            name=f"CaseActor for {case_id}",
            attributed_to=owner_id,
            context=case_id,
        )
        dl.create(case_actor)

        case = VulnerabilityCase(
            id_=case_id,
            name="Original",
            attributed_to=owner_id,
        )
        case.actor_participant_index[participant_id] = (
            "https://example.org/participants/p-bt2"
        )
        dl.create(case)

        updated_case = VulnerabilityCase(
            id_=case_id,
            name="Updated",
            attributed_to=owner_id,
        )
        activity = update_case_activity(updated_case, actor=owner_id)
        event = make_payload(activity)

        def _should_not_be_called(*args, **kwargs):
            raise AssertionError("post-BT broadcast helper should not run")

        monkeypatch.setattr(
            UpdateCaseReceivedUseCase,
            "_broadcast_case_update",
            _should_not_be_called,
        )

        UpdateCaseReceivedUseCase(dl, event).execute()

        outbox_items = dl.outbox_list_for_actor(case_actor.id_)
        assert len(outbox_items) == 1


class TestCollectionDefaultsCS21:
    """CS-21-001: omitting excluded_actor_ids yields set() not None."""

    def test_broadcast_case_update_default_excluded_actor_ids_is_empty_set(
        self,
    ):
        """broadcast_case_update: omitting excluded_actor_ids gives set()."""
        dl = MagicMock()
        dl.read.return_value = None  # no case actor found — early return
        case = MagicMock()
        case.actor_participant_index = {}
        # Call without excluded_actor_ids; should not raise and should not
        # see None internally — verified by the no-CaseActor early-return path.
        broadcast_case_update(dl, "urn:uuid:case-1", case)

    def test_broadcast_case_update_uses_empty_set_when_not_provided(self):
        """broadcast_case_update: excluded_actor_ids defaults to set(), not None."""
        import inspect

        sig = inspect.signature(broadcast_case_update)
        default = sig.parameters["excluded_actor_ids"].default
        assert default == set()
        assert default is not None

    def test_broadcast_case_update_private_default_excluded_actor_ids_is_empty_set(
        self,
    ):
        """_broadcast_case_update: excluded_actor_ids defaults to set()."""
        import inspect

        sig = inspect.signature(
            UpdateCaseReceivedUseCase._broadcast_case_update
        )
        default = sig.parameters["excluded_actor_ids"].default
        assert default == set()
        assert default is not None
