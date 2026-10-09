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

Note: TestRecordCaseCreationEvents and TestProposeCaseToActorNode were removed
in issue #4353 — the nodes they covered (RecordCaseCreationEvents,
RecordCaseCreatedEventNode, RecordOfferReceivedEventNode, ProposeCaseToActorNode)
were orphaned by create_create_case_tree's removal and have been deleted.

Per specs/behavior-tree-node-design.yaml BTND-02-001, BTND-03-001, BTND-04-001
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

# ---------------------------------------------------------------------------
# P360-FIX-1: UpdateActorOutbox re-export tests
# ---------------------------------------------------------------------------


class TestUpdateActorOutboxReExport:
    """UpdateActorOutbox is the same object in all three modules (BTND-04-001)."""

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
# CreateCaseActorNode (blackboard variant) tests
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
