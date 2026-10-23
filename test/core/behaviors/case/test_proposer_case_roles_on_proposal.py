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

"""The report receiver states its own case roles on the proposal (ADR-0133).

The chain this pins:

1. the receiver copies its ``ActorConfig.default_case_roles`` onto the
   ``as_CaseProposal`` it sends, as ``proposerCaseRoles`` (CP-01-011);
2. the field survives the wire, and a claim to ``CASE_MANAGER`` is refused
   when the proposal is parsed (CP-01-012);
3. the extractor hands the roles to the CaseActor's use case on the event.

The CaseActor then seats the receiver with them (CP-09-007); that end is
covered in ``test_case_proposal_received_tree.py``.  Before ADR-0133 the
CaseActor read its *own* configuration, which was the receiver's only while
both ran in one container (#1876).
"""

import pytest
from py_trees.common import Status
from pydantic import ValidationError

from vultron.core.behaviors.case.nodes import ProposeReportCaseToActorNode
from vultron.core.models.actor import VultronOrganization
from vultron.core.models.events.case_proposal import (
    CreateCaseProposalReceivedEvent,
)
from vultron.enums.roles import CVDRole
from vultron.semantic_registry import extract_event
from vultron.wire.as2.vocab.base.objects.activities.transitive import (
    as_Create,
)
from vultron.wire.as2.vocab.objects.case_proposal import as_CaseProposal

_CASE_ACTOR_SERVICE_URL = "http://case-actor:7999/api/v2"
_CASE_ACTOR_URI = f"{_CASE_ACTOR_SERVICE_URL}/actors/case-actor"
_VENDOR_URI = "https://example.org/actors/vendor"
_REPORT_URI = "https://example.org/reports/r-001"
_PROPOSAL_URI = "https://example.org/proposals/p-roles"


@pytest.fixture
def configured_roles(monkeypatch):
    """Configure the receiver's CaseActor URL and its own default roles."""
    from vultron.config.app import reload_config

    def _configure(roles: str) -> None:
        monkeypatch.setenv(
            "VULTRON_ACTOR__CASE_ACTOR_SERVICE_URL", _CASE_ACTOR_SERVICE_URL
        )
        monkeypatch.setenv("VULTRON_ACTOR__DEFAULT_CASE_ROLES", roles)
        reload_config()

    yield _configure
    # Undo the env patch BEFORE reloading, or the values are re-cached into the
    # module-level config for the rest of the session (#2086).
    monkeypatch.undo()
    reload_config()


def _proposal(**kwargs) -> as_CaseProposal:
    return as_CaseProposal(
        id_=_PROPOSAL_URI,
        attributed_to=_VENDOR_URI,
        object_=_REPORT_URI,
        target=_CASE_ACTOR_URI,
        **kwargs,
    )


@pytest.mark.spec("CP-01-011")
@pytest.mark.spec("CP-01-013")
class TestReceiverStatesItsRoles:
    """Sender side: the proposal carries the sender's own default roles."""

    def _propose(self, bridge, datalayer, actor_id, report_id):
        node = ProposeReportCaseToActorNode(report_id=report_id)
        result = bridge.execute_with_setup(tree=node, actor_id=actor_id)
        assert result.status == Status.SUCCESS, node.feedback_message
        (proposal,) = [
            p
            for p in datalayer.list_objects("CaseProposal")
            if isinstance(p, as_CaseProposal)
        ]
        return proposal

    def test_a_vendor_states_vendor(
        self, configured_roles, datalayer, actor, report, bridge
    ):
        configured_roles('["vendor"]')
        proposal = self._propose(bridge, datalayer, actor.id_, report.id_)
        assert proposal.proposer_case_roles == [CVDRole.VENDOR]

    def test_a_receiver_with_no_default_roles_states_none(
        self, configured_roles, datalayer, actor, report, bridge
    ):
        configured_roles("[]")
        proposal = self._propose(bridge, datalayer, actor.id_, report.id_)
        assert proposal.proposer_case_roles == []


@pytest.mark.spec("CP-01-011")
class TestTheRolesSurviveTheWire:
    def test_serialised_under_the_wire_name(self):
        dumped = _proposal(
            proposer_case_roles=[CVDRole.VENDOR, CVDRole.DEPLOYER]
        ).model_dump(by_alias=True, mode="json")
        assert dumped["proposerCaseRoles"] == ["vendor", "deployer"]

    def test_round_trip(self):
        original = _proposal(proposer_case_roles=[CVDRole.COORDINATOR])
        restored = as_CaseProposal.model_validate(
            original.model_dump(by_alias=True, mode="json")
        )
        assert restored.proposer_case_roles == [CVDRole.COORDINATOR]

    def test_absent_means_no_role_beyond_case_owner(self):
        restored = as_CaseProposal.model_validate(
            {
                "id": _PROPOSAL_URI,
                "type": "CaseProposal",
                "attributedTo": _VENDOR_URI,
                "object": _REPORT_URI,
                "target": _CASE_ACTOR_URI,
            }
        )
        assert restored.proposer_case_roles == []


@pytest.mark.spec("CP-01-012")
class TestNoProposerClaimsCaseManager:
    def test_a_case_manager_claim_is_refused_at_parse(self):
        with pytest.raises(ValidationError, match="CP-01-012"):
            as_CaseProposal.model_validate(
                {
                    "id": _PROPOSAL_URI,
                    "type": "CaseProposal",
                    "attributedTo": _VENDOR_URI,
                    "object": _REPORT_URI,
                    "target": _CASE_ACTOR_URI,
                    "proposerCaseRoles": ["vendor", "case_manager"],
                }
            )

    def test_a_create_carrying_the_claim_is_refused_by_the_inbox_parser(
        self,
    ):
        """The refusal holds at ``parse_activity``, the real parse edge.

        ``as_Create.model_validate`` alone would degrade the inline proposal to
        a generic object, so only the full parse proves the claim is refused.
        """
        from vultron.wire.as2.errors import VultronParseValidationError
        from vultron.wire.as2.parser import parse_activity

        body = as_Create(
            actor=VultronOrganization(id_=_VENDOR_URI),
            object_=_proposal(proposer_case_roles=[CVDRole.VENDOR]),
            to=[_CASE_ACTOR_URI],
        ).model_dump(by_alias=True, mode="json", exclude_none=True)
        body["object"]["proposerCaseRoles"] = ["vendor", "case_manager"]

        with pytest.raises(VultronParseValidationError, match="CP-01-012"):
            parse_activity(body)

    def test_a_malformed_role_is_refused_not_dropped(self):
        """A non-string role is never read as "no roles" (CP-01-011)."""
        with pytest.raises(ValidationError, match="proposerCaseRoles items"):
            as_CaseProposal.model_validate(
                {
                    "id": _PROPOSAL_URI,
                    "type": "CaseProposal",
                    "attributedTo": _VENDOR_URI,
                    "object": _REPORT_URI,
                    "target": _CASE_ACTOR_URI,
                    "proposerCaseRoles": [1, "vendor"],
                }
            )

    def test_the_core_event_refuses_a_case_manager_claim(self):
        """Core is fail-fast too: no caller can seat a second CASE_MANAGER."""
        with pytest.raises(ValidationError, match="CP-01-012"):
            CreateCaseProposalReceivedEvent(
                activity_id="https://example.org/activities/create-p",
                actor_id=_VENDOR_URI,
                proposer_profile=VultronOrganization(id_=_VENDOR_URI),
                proposer_case_roles=[CVDRole.CASE_MANAGER],
            )


@pytest.mark.spec("CP-01-011")
class TestTheCaseActorReceivesThem:
    """The extractor puts the stated roles on the received event."""

    def _event(self, roles: list[CVDRole]) -> CreateCaseProposalReceivedEvent:
        activity = as_Create(
            actor=VultronOrganization(id_=_VENDOR_URI),
            object_=_proposal(proposer_case_roles=roles),
            to=[_CASE_ACTOR_URI],
        )
        event = extract_event(activity)
        assert isinstance(event, CreateCaseProposalReceivedEvent)
        return event

    def test_stated_roles_reach_the_event(self):
        assert self._event([CVDRole.VENDOR]).proposer_case_roles == [
            CVDRole.VENDOR
        ]

    def test_no_stated_roles_reach_the_event_as_empty(self):
        assert self._event([]).proposer_case_roles == []

    def test_a_create_without_a_parsed_proposal_is_refused(self):
        """Never read as "no roles": that seats the owner as CASE_OWNER alone."""
        from vultron.core.models.events import MessageSemantics
        from vultron.wire.as2.errors import VultronParseValidationError
        from vultron.wire.as2.extractor._extract import extract_intent

        activity = as_Create(
            actor=VultronOrganization(id_=_VENDOR_URI),
            object_=_REPORT_URI,
            to=[_CASE_ACTOR_URI],
        )
        with pytest.raises(VultronParseValidationError, match="CP-01-011"):
            extract_intent(
                activity,
                MessageSemantics.CREATE_CASE_PROPOSAL,
                CreateCaseProposalReceivedEvent,
            )
