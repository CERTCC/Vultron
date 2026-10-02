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

A REVISE case owing one ``PendingCreationTimeRevisionRelay``, and the
readers the node, tree and startup-runner tests assert through.
"""

from typing import cast

from test.core.behaviors.bt_harness import BTTestScenario
from vultron.adapters.driven.sync_activity_adapter import SyncActivityAdapter
from vultron.adapters.driven.wire_render.as2 import As2WireRenderAdapter
from vultron.core.behaviors.bridge import BTBridge, BTExecutionResult
from vultron.core.behaviors.case.nodes.embargo_revision_relay import (
    RelayCreationTimeRevisionNode,
)
from vultron.core.behaviors.case.nodes.proposal_ledger import (
    CREATE_CASE_EVENT_TYPE,
)
from vultron.core.behaviors.sync.nodes.chain import _to_persistable_entry
from vultron.core.models._helpers import days_from_now_utc
from vultron.core.models.activity import VultronActivity
from vultron.core.models.case import VulnerabilityCase
from vultron.core.models.case_ledger import HashChainLedgerRecord
from vultron.core.models.case_participant import CaseParticipant
from vultron.core.models.pending_creation_time_revision_relay import (
    LosingSource,
    PendingCreationTimeRevisionRelay,
)
from vultron.core.models.report import VulnerabilityReport
from vultron.core.services.embargo_duration import EmbargoDurationSource
from vultron.core.states.em import EM
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
PROPOSAL_ID = "urn:uuid:creation-time-revision-invite"
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
    owner: str | None = OWNER,
    created: bool = True,
) -> None:
    """A REVISE case owned by OWNER, managed by MANAGER, reported by REPORTER.

    *created* commits the case's genesis ledger entry, as the case tree's
    ledger commit does before the relay runs; without it the case's creation
    entries are still owed (CM-14-007, CM-14-011).
    """
    records = [
        participant(MANAGER, CVDRole.CASE_MANAGER),
        participant(OWNER, CVDRole.VENDOR),
        participant(REPORTER, CVDRole.FINDER),
    ]
    case = VulnerabilityCase(
        id_=CASE_ID,
        name="Creation-time revision",
        attributed_to=OWNER,
        case_participants=[p.id_ for p in records],
        actor_participant_index={
            cast(str, p.attributed_to): p.id_ for p in records
        },
        proposed_embargoes=[EMBARGO_ID] if open_proposal else [],
    )
    case.append_case_status(em_state=EM.REVISE)
    # A case only materializes status with an owner, so an ownerless case is
    # one whose record lost it after construction (assignment skips checks).
    case.attributed_to = owner
    embargo = as_EmbargoEvent(
        id_=EMBARGO_ID, context=CASE_ID, end_time=days_from_now_utc(60)
    )
    report = VulnerabilityReport(id_=REPORT_ID, attributed_to=report_author)
    scenario.seed(*records, case, embargo, report)
    if created:
        scenario.dl.save(
            _to_persistable_entry(
                HashChainLedgerRecord(
                    case_id=CASE_ID,
                    log_index=0,
                    object_id=CASE_ID,
                    event_type=CREATE_CASE_EVENT_TYPE,
                    payload_snapshot={},
                    prev_log_hash=case.genesis_hash,
                )
            )
        )


def marker(
    losing_source: EmbargoDurationSource = EmbargoDurationSource.ACTOR_DEFAULT,
    report_id: str = REPORT_ID,
    *,
    invite_queued: bool = False,
) -> PendingCreationTimeRevisionRelay:
    return PendingCreationTimeRevisionRelay(
        case_id=CASE_ID,
        embargo_id=EMBARGO_ID,
        proposal_id=PROPOSAL_ID,
        losing_source=cast(LosingSource, losing_source.value),
        report_id=report_id,
        case_actor_id=MANAGER,
        invite_queued=invite_queued,
    )


def owe(
    scenario: BTTestScenario,
    losing_source: EmbargoDurationSource = EmbargoDurationSource.ACTOR_DEFAULT,
    report_id: str = REPORT_ID,
    *,
    invite_queued: bool = False,
) -> None:
    """Record the relay obligation the registration would write."""
    scenario.dl.save(
        marker(losing_source, report_id, invite_queued=invite_queued)
    )


def relay(
    scenario: BTTestScenario, *, case_id: str | None = None
) -> BTExecutionResult:
    """Run the relay as the case tree does (``case_id`` on the blackboard),
    or as the startup runner does (``case_id`` passed in)."""
    if case_id is not None:
        return scenario.run(RelayCreationTimeRevisionNode(case_id=case_id))
    return scenario.run(RelayCreationTimeRevisionNode(), case_id=CASE_ID)


def owed(scenario: BTTestScenario) -> PendingCreationTimeRevisionRelay | None:
    stored = scenario.dl.read(
        PendingCreationTimeRevisionRelay.build_id(CASE_ID)
    )
    assert stored is None or isinstance(
        stored, PendingCreationTimeRevisionRelay
    )
    return stored


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
