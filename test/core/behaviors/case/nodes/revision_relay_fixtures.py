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
"""Shared setup for the creation-time revision relay tests (EP-04-011).

A REVISE case whose open proposal is the revision a contested creation
registered, and the readers the node tests assert through.
"""

from typing import Any, cast

from test.core.behaviors.bt_harness import BTTestScenario
from test.support.embargo_register import register, reject
from vultron.adapters.driven.sync_activity_adapter import SyncActivityAdapter
from vultron.adapters.driven.wire_render.as2 import As2WireRenderAdapter
from vultron.core.behaviors.act_transaction import ActTransaction
from vultron.core.behaviors.bridge import BTBridge, BTExecutionResult
from vultron.core.behaviors.case.nodes.embargo_revision import (
    CANDIDATE_KEY,
    CreationTimeRevisionCandidate,
)
from vultron.core.behaviors.case.nodes.embargo_revision_relay import (
    RelayCreationTimeRevisionNode,
)
from vultron.core.behaviors.case.nodes.proposal_ledger import (
    CREATE_CASE_SEMANTIC_TYPE,
)
from vultron.core.behaviors.embargo.nodes.relay import (
    EMBARGO_INVITE_SEMANTIC_TYPE,
)
from vultron.core.behaviors.sync.nodes.chain import _to_persistable_entry
from vultron.core.models._helpers import days_from_now_utc
from vultron.core.models.activity import VultronActivity
from vultron.core.models.activity_ids import derived_activity_id
from vultron.core.models.case import VulnerabilityCase
from vultron.core.models.case_ledger import HashChainLedgerRecord
from vultron.core.models.case_participant import CaseParticipant
from vultron.core.models.report import VulnerabilityReport
from vultron.core.services.embargo_duration import EmbargoDurationSource
from vultron.enums.roles import CVDRole
from vultron.wire.as2.vocab.objects.embargo_event import as_EmbargoEvent
from vultron.wire.as2.vocab.objects.vulnerability_case import (  # noqa: F401
    as_VulnerabilityCase,
)
from vultron.wire.as2.vocab.objects.vulnerability_report import (  # noqa: F401
    as_VulnerabilityReport,
)

CASE_ID = "https://example.org/cases/creation-revision"
EMBARGO_ID = f"{CASE_ID}/embargo_events/revision"
ACCEPTED_EMBARGO_ID = f"{CASE_ID}/embargo_events/accepted"
CASE_PROPOSAL_ID = "https://example.org/proposals/creation-revision"
REPORT_ID = "https://example.org/reports/creation-revision"
MANAGER = "https://example.org/actors/case-actor"
OWNER = "https://example.org/actors/owner"
REPORTER = "https://example.org/actors/reporter"


def participant(actor_id: str, *roles: CVDRole) -> CaseParticipant:
    return CaseParticipant(
        id_=f"{CASE_ID}/participants/{actor_id.rsplit('/', 1)[-1]}",
        attributed_to=actor_id,
        context=CASE_ID,
        case_roles=list(roles),
    )


def seed(
    scenario: BTTestScenario,
    *,
    open_proposal: bool = True,
    report_author: str | None = REPORTER,
) -> None:
    """A REVISE case owned by OWNER, managed by MANAGER, reported by REPORTER.

    The revision is an open proposal beside the embargo in force; with
    *open_proposal* false the owner has rejected it, leaving the case ACTIVE.
    The case's genesis ledger entry is committed, as the case tree's ledger
    commit does before the relay runs (CM-14-007, CM-14-011).
    """
    records = [
        participant(MANAGER, CVDRole.CASE_MANAGER),
        participant(OWNER, CVDRole.VENDOR),
        participant(REPORTER, CVDRole.REPORTER),
    ]
    case = VulnerabilityCase(
        id_=CASE_ID,
        name="Creation-time revision",
        attributed_to=OWNER,
        case_participants=[p.id_ for p in records],
        actor_participant_index={
            cast(str, p.attributed_to): p.id_ for p in records
        },
        embargo_register=register(
            active=ACCEPTED_EMBARGO_ID, proposed=[EMBARGO_ID]
        ),
    )
    if not open_proposal:
        reject(case, EMBARGO_ID)
    embargo = as_EmbargoEvent(
        id_=EMBARGO_ID, context=CASE_ID, end_time=days_from_now_utc(60)
    )
    report = VulnerabilityReport(id_=REPORT_ID, attributed_to=report_author)
    for record in records:
        # The rows the register's entries gave each participant (ADR-0122).
        record.write_uninvited_rows(
            e.embargo_id for e in case.embargo_register
        )
    scenario.seed(*records, case, embargo, report)
    scenario.dl.save(
        _to_persistable_entry(
            HashChainLedgerRecord(
                case_id=CASE_ID,
                log_index=0,
                object_id=CASE_ID,
                semantic_type=CREATE_CASE_SEMANTIC_TYPE,
                payload_snapshot={},
                prev_log_hash=case.genesis_hash,
            )
        )
    )


def candidate(
    losing_source: EmbargoDurationSource = EmbargoDurationSource.ACTOR_DEFAULT,
) -> CreationTimeRevisionCandidate:
    """The revision ``ResolveCreationTimeRevisionNode`` publishes."""
    return CreationTimeRevisionCandidate(
        embargo=as_EmbargoEvent(
            id_=EMBARGO_ID, context=CASE_ID, end_time=days_from_now_utc(60)
        ),
        losing_source=losing_source,
    )


def relay_node(
    report_id: str | None = REPORT_ID,
) -> RelayCreationTimeRevisionNode:
    return RelayCreationTimeRevisionNode(
        proposal_id=CASE_PROPOSAL_ID, report_id=report_id
    )


def relay(
    scenario: BTTestScenario,
    losing_source: EmbargoDurationSource
    | None = EmbargoDurationSource.ACTOR_DEFAULT,
    *,
    in_act: bool = False,
) -> BTExecutionResult:
    """Run the relay as the case tree does, after a registration.

    *losing_source* ``None`` runs it as a redelivery whose initialization
    was skipped: no candidate is published.  *in_act* runs it inside an
    ``ActTransaction``, as the creation act does.
    """
    node = relay_node()
    tree = (
        ActTransaction(name="CreationAct", children=[node]) if in_act else node
    )
    context: dict[str, Any] = {"case_id": CASE_ID}
    if losing_source is not None:
        context[CANDIDATE_KEY] = candidate(losing_source)
    return scenario.run(tree, **context)


def relayed_invite_id(winner: str) -> str:
    """The id the relay derives for the Invite to *winner* (OX-06-002)."""
    return derived_activity_id(
        EMBARGO_INVITE_SEMANTIC_TYPE,
        MANAGER,
        CASE_ID,
        CASE_PROPOSAL_ID,
        EMBARGO_ID,
        winner,
    )


def invites(scenario: BTTestScenario) -> list[VultronActivity]:
    return [
        a
        for a in (
            cast(VultronActivity, scenario.dl.read(i))
            for i in scenario.dl.outbox_list()
        )
        if a.type_ == "Invite"
    ]


def index(scenario: BTTestScenario) -> dict[str, str]:
    case = scenario.dl.read(CASE_ID)
    assert isinstance(case, VulnerabilityCase)
    return dict(case.pending_embargo_proposal_index)


def no_factory(scenario: BTTestScenario) -> None:
    """Rewire the scenario's bridge without a trigger-activity factory."""
    scenario.bridge = BTBridge(
        datalayer=scenario.dl,
        wire_render_port=As2WireRenderAdapter(),
        sync_port=SyncActivityAdapter(scenario.dl),
    )
