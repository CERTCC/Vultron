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

"""
Tests for case_setup behavior tree nodes.

Covers:
- UpdateActorOutbox re-export via case.nodes and report.nodes (P360-FIX-1)
- ActorConfig.case_actor_service_url field validation (CP-08-002)
- EnsureCaseActorHostedNode publishes no CaseActor on a delegating node (#1876)

Note: TestRecordCaseCreationEvents and TestProposeCaseToActorNode were removed
in issue #4353 — the nodes they covered (RecordCaseCreationEvents,
RecordCaseCreatedEventNode, RecordOfferReceivedEventNode, ProposeCaseToActorNode)
were orphaned by create_create_case_tree's removal and have been deleted.

Per specs/behavior-tree-node-design.yaml BTND-02-001, BTND-03-001, BTND-04-005
and GitHub issue #401.
"""

from vultron.core.behaviors.case.nodes import (
    UpdateActorOutbox,
)
from vultron.core.behaviors.helpers import (
    UpdateActorOutbox as UpdateActorOutboxHelper,
)
from vultron.core.behaviors.report.nodes import (
    UpdateActorOutbox as UpdateActorOutboxReport,
)
from vultron.core.models.actor import CoreActor, VultronService

# ---------------------------------------------------------------------------
# P360-FIX-1: UpdateActorOutbox re-export tests
# ---------------------------------------------------------------------------


class TestUpdateActorOutboxReExport:
    """UpdateActorOutbox is the same object in all three modules (BTND-04-005)."""

    def test_case_nodes_re_exports_from_helpers(self) -> None:
        assert UpdateActorOutbox is UpdateActorOutboxHelper

    def test_report_nodes_re_exports_from_helpers(self) -> None:
        assert UpdateActorOutboxReport is UpdateActorOutboxHelper

    def test_shared_class_is_not_duplicate(self) -> None:
        """There is exactly one UpdateActorOutbox class definition."""
        assert (
            UpdateActorOutbox
            is UpdateActorOutboxReport
            is UpdateActorOutboxHelper
        )


# ---------------------------------------------------------------------------
# ActorConfig.case_actor_service_url tests
# ---------------------------------------------------------------------------


class TestActorConfigCaseActorServiceUrl:
    """ActorConfig.case_actor_service_url field validation (CP-08-001)."""

    def test_defaults_to_none(self) -> None:
        """case_actor_service_url defaults to None when not configured."""
        from vultron.config.actor import ActorConfig

        cfg = ActorConfig()
        assert cfg.case_actor_service_url is None

    def test_accepts_valid_http_url(self) -> None:
        """case_actor_service_url accepts a valid HttpUrl string via model_validate."""
        from vultron.config.actor import ActorConfig

        cfg = ActorConfig.model_validate(
            {"case_actor_service_url": "http://case-actor:7999/api/v2"}
        )
        assert cfg.case_actor_service_url is not None
        assert "case-actor" in str(cfg.case_actor_service_url)

    def test_roundtrip_through_env_var(self, monkeypatch) -> None:
        """VULTRON_ACTOR__CASE_ACTOR_SERVICE_URL sets case_actor_service_url."""
        from vultron.config.app import reload_config

        monkeypatch.setenv(
            "VULTRON_ACTOR__CASE_ACTOR_SERVICE_URL",
            "http://case-actor:7999/api/v2",
        )
        reload_config()
        from vultron.config import get_config

        cfg = get_config().actor
        assert cfg.case_actor_service_url is not None
        assert "case-actor" in str(cfg.case_actor_service_url)
        reload_config()

    def test_construction_succeeds_without_field(self) -> None:
        """ActorConfig construction succeeds when case_actor_service_url absent."""
        from vultron.config.actor import ActorConfig

        cfg = ActorConfig(auto_create_case=True)
        assert cfg.case_actor_service_url is None


# ---------------------------------------------------------------------------
# #1876 AC-4: a container that delegates its CaseActor hosts none of its own
# ---------------------------------------------------------------------------


class TestEnsureCaseActorHostedNode:
    """Where ``EnsureCaseActorHostedNode`` writes the CaseActor record.

    In the Docker topology every actor container names the dedicated
    case-actor container (CP-08-008), so the receiver's node must not publish a
    CaseActor of its own — that is the co-located shortcut #1876 retires.  It
    keeps one address-book entry for the CaseActor it now knows
    (ADR-0073#peer-records-in-knowers-store); that entry is knowledge, not an
    inbox.
    """

    _VENDOR_ID = "http://vendor:7999/api/v2/actors/vendor"

    def _run(self, monkeypatch, case_actor_service_url: str):
        from py_trees.common import Status

        from vultron.adapters.driven.datalayer_sqlite import SqliteDataLayer
        from vultron.config.app import reload_config
        from vultron.core.behaviors.bridge import BTBridge
        from vultron.core.behaviors.case.case_actor_identity import (
            case_actor_identity,
        )
        from vultron.core.behaviors.case.nodes import (
            EnsureCaseActorHostedNode,
        )

        monkeypatch.setenv(
            "VULTRON_ACTOR__CASE_ACTOR_SERVICE_URL", case_actor_service_url
        )
        reload_config()
        try:
            dl = SqliteDataLayer(
                "sqlite:///:memory:", actor_id=self._VENDOR_ID
            )
            dl.create(VultronService(id_=self._VENDOR_ID, name="Vendor"))
            result = BTBridge(datalayer=dl).execute_with_setup(
                tree=EnsureCaseActorHostedNode(), actor_id=self._VENDOR_ID
            )
            case_actor_id = case_actor_identity()
        finally:
            monkeypatch.undo()
            reload_config()
        assert result.status == Status.SUCCESS
        assert case_actor_id is not None
        return dl, case_actor_id

    def test_delegating_container_publishes_no_case_actor(self, monkeypatch):
        dl, case_actor_id = self._run(
            monkeypatch, "http://case-actor:7999/api/v2"
        )

        # The local copy of the CaseActor's store stays empty: nothing on this
        # node answers for http://case-actor:7999/.../case-actor.
        assert dl.clone_for_actor(case_actor_id).read(case_actor_id) is None
        # The sending actor knows the CaseActor as a peer, by its id alone:
        # no name, time or endpoint this node would have to guess (AKM-02-006).
        peer = dl.read(case_actor_id)
        assert isinstance(peer, VultronService)
        assert (peer.name, peer.published, peer.updated) == (None, None, None)
        assert (peer.inbox, peer.outbox) == (None, None)

    def test_self_hosting_container_publishes_it(self, monkeypatch):
        """Guard the guard: the same node does publish a co-located one."""
        dl, case_actor_id = self._run(monkeypatch, "http://vendor:7999/api/v2")

        hosted = dl.clone_for_actor(case_actor_id).read(case_actor_id)
        assert isinstance(hosted, CoreActor)
        # The CaseActor this node hosts states the endpoints it routes for it.
        assert (hosted.inbox, hosted.outbox) == (
            f"{case_actor_id}/inbox",
            f"{case_actor_id}/outbox",
        )
