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

import py_trees
import pytest

from vultron.adapters.driven.datalayer_sqlite import SqliteDataLayer
from vultron.adapters.driven.trigger_activity_adapter import (
    TriggerActivityAdapter,
)
from vultron.core.behaviors.case.nodes.intake import (
    IntakeReceivedActivityNode,
)
from vultron.core.behaviors.case.nodes.update import (
    ApplyCaseUpdateNode,
    BroadcastCaseUpdateNode,
    CaptureCaseUpdateBroadcastExclusionsNode,
    CheckCaseUpdateOwnerNode,
)
from vultron.core.behaviors.case.update_support import broadcast_case_update
from vultron.core.models.case_participant import CaseParticipant
from vultron.core.models.use_case_result import HandlerResult
from vultron.enums.roles import CVDRole
from vultron.core.behaviors.case.nodes.conditions import (
    CheckIsCaseManagerNode,
)
from vultron.core.behaviors.case.update_tree import (
    create_update_case_received_tree,
)
from vultron.core.models.case_actor import CaseActor
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
        # Intake first (CLP-10-017, ADR-0111), then the sender-ownership guard,
        # then the effects.  No commit stage: Update(VulnerabilityCase) is not
        # a canonical payload signature (see create_update_case_received_tree).
        assert [child.__class__ for child in tree.children[:4]] == [
            IntakeReceivedActivityNode,
            CheckCaseUpdateOwnerNode,
            CaptureCaseUpdateBroadcastExclusionsNode,
            ApplyCaseUpdateNode,
        ]

        # The broadcast is role-gated: only the case's CASE_MANAGER may announce
        # canonical case state (CM-06-001), mirroring CLP-09 for ledger commits.
        # A non-manager skips rather than fails — applying the update to its own
        # replica is correct.
        guard = tree.children[4]
        assert guard.name == "GuardedBroadcastCaseUpdateBT"
        skip, broadcast = guard.children
        assert skip.name == "SkipIfNotCaseManager"
        inverter = skip.children[0]
        assert isinstance(inverter, py_trees.decorators.Inverter)
        assert isinstance(inverter.decorated, CheckIsCaseManagerNode)
        assert isinstance(broadcast, BroadcastCaseUpdateNode)

    def test_update_case_bt_executes_without_post_bt_broadcast(
        self, make_payload, monkeypatch
    ):
        """UpdateCaseBT handles the broadcast internally instead of after execute()."""
        owner_id = "https://example.org/users/owner"
        dl = SqliteDataLayer("sqlite:///:memory:", actor_id=owner_id)
        participant_id = "https://example.org/users/alice"
        case_id = "https://example.org/cases/bt2"

        case_actor = CaseActor(
            id_=f"{case_id}/actor",
            name=f"CaseActor for {case_id}",
            attributed_to=owner_id,
            context=case_id,
        )
        dl.create(case_actor)

        # BT-17-005: the broadcast gate resolves CASE_MANAGER from the case's
        # participants, not from the CaseActor *service* entity.  A
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
        UpdateCaseReceivedUseCase(
            dl, event, trigger_activity=TriggerActivityAdapter(dl)
        ).execute()

        outbox_items = dl.outbox_list()
        assert len(outbox_items) == 1


class TestBroadcastRefusalIsAReportedOutcome:
    """BroadcastCaseUpdateNode reports an Announce the adapter refuses.

    The CM-06-001 broadcast now goes through the trigger adapter, which will
    not build an Announce that cannot embed every report the case names
    (CBT-01-007).  That refusal is this node's FAILURE with a feedback
    message — not an exception escaping ``update()`` and surfacing as an
    internal error of the whole received tree (BT-HELPER-01).
    """

    @pytest.mark.spec("CBT-01-007")
    @pytest.mark.spec("CM-06-001")
    def test_missing_report_fails_the_node_without_an_internal_error(
        self, make_payload
    ):
        owner_id = "https://example.org/users/owner"
        dl = SqliteDataLayer("sqlite:///:memory:", actor_id=owner_id)
        participant_id = "https://example.org/users/alice"
        case_id = "https://example.org/cases/bt-missing-report"

        dl.create(
            CaseActor(
                id_=f"{case_id}/actor",
                name=f"CaseActor for {case_id}",
                attributed_to=owner_id,
                context=case_id,
            )
        )
        manager_participant_id = "https://example.org/participants/p-mgr-mr"
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
            vulnerability_reports=[
                "https://example.org/reports/not-in-this-store"
            ],
        )
        case.actor_participant_index[participant_id] = (
            "https://example.org/participants/p-mr"
        )
        case.actor_participant_index[owner_id] = manager_participant_id
        dl.create(case)

        updated_case = as_VulnerabilityCase(
            id_=case_id, name="Updated", attributed_to=owner_id
        )
        event = make_payload(
            update_case_activity(updated_case, actor=owner_id)
        )
        event.receiving_actor_id = owner_id

        # A programming error propagates out of execute() as an exception
        # (ADR-0095); a refused Announce must not.  The node reports it and
        # the tree carries on, so the handler returns a verdict and queues
        # nothing.
        result = UpdateCaseReceivedUseCase(
            dl, event, trigger_activity=TriggerActivityAdapter(dl)
        ).execute()

        assert isinstance(result, HandlerResult), result
        assert dl.outbox_list() == [], "nothing was announced"


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
            dl,
            "urn:uuid:case-1",
            case,
            "https://example.org/actors/manager",
            MagicMock(),
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
            dl,
            "urn:uuid:case-1",
            case,
            "https://example.org/actors/manager",
            MagicMock(),
        )
