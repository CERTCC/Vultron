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
"""A peer that spells its own id with a trailing slash keeps its case (#4775).

The proposal tree stores the proposer canonically (#4772).  The peer's later
messages arrive in the slash spelling; the extractor normalises the sender id
(OID-01-007), so the CASE_MANAGER's exact lookups find the CASE_OWNER records
the proposal wrote, while the ledger keeps what the sender wrote (OID-01-006).
"""

from typing import Any, cast

import pytest

from test.support.embargo_register import propose
from test.support.received import received_event
from vultron.adapters.driven.datalayer_sqlite import SqliteDataLayer
from vultron.adapters.driven.sync_activity_adapter import SyncActivityAdapter
from vultron.adapters.driven.trigger_activity_adapter import (
    TriggerActivityAdapter,
)
from vultron.adapters.driven.wire_render.as2 import As2WireRenderAdapter
from vultron.core.models._helpers import days_from_now_utc
from vultron.core.models.actor import VultronOrganization
from vultron.core.models.case import VulnerabilityCase
from vultron.core.models.case_ledger_entry import CaseLedgerEntry
from vultron.core.models.case_participant import CaseParticipant
from vultron.core.models.use_case_result import HandlerDisposition
from vultron.core.use_cases.received.case_proposal import (
    CreateCaseProposalReceivedUseCase,
)
from vultron.core.use_cases.received.embargo import (
    RejectEmbargoProposalOnCaseReceivedUseCase,
    WithdrawFromEmbargoOnCaseReceivedUseCase,
)
from vultron.enums.roles import CVDRole
from vultron.wire.as2.factories import (
    reject_embargo_proposal_activity,
    withdraw_from_embargo_activity,
)
from vultron.wire.as2.vocab.base.objects.activities.transitive import (
    as_Create,
)
from vultron.wire.as2.vocab.examples._base import gen_report
from vultron.wire.as2.vocab.objects.case_proposal import as_CaseProposal
from vultron.wire.as2.vocab.objects.embargo_event import as_EmbargoEvent

_CASE_ACTOR = "https://example.org/case-actors/svc-1"
_VENDOR = "https://example.org/vendors/acme"
_VENDOR_AS_WRITTEN = _VENDOR + "/"


def _ports(dl: SqliteDataLayer) -> dict:
    return {
        "sync_port": SyncActivityAdapter(dl),
        "trigger_activity": TriggerActivityAdapter(dl),
        "wire_render_port": As2WireRenderAdapter(),
    }


def _event(activity: Any) -> Any:
    """The received event, as the inbox hands it to the use case."""
    return received_event(activity).model_copy(
        update={"receiving_actor_id": _CASE_ACTOR}
    )


def _case(dl: SqliteDataLayer) -> VulnerabilityCase:
    (case,) = [
        c
        for c in dl.list_objects("VulnerabilityCase")
        if isinstance(c, VulnerabilityCase)
    ]
    return case


def _propose_case(dl: SqliteDataLayer) -> VulnerabilityCase:
    proposal = as_CaseProposal(
        attributed_to=_VENDOR_AS_WRITTEN,
        object_=gen_report(),
        target=_CASE_ACTOR,
    )
    activity = as_Create(
        actor=VultronOrganization(id_=_VENDOR_AS_WRITTEN),
        object_=proposal,
        to=[_CASE_ACTOR],
    )
    result = CreateCaseProposalReceivedUseCase(
        dl, _event(activity), **_ports(dl)
    ).execute()
    assert result.disposition is HandlerDisposition.APPLIED, result.reason
    return _case(dl)


def _seed_revision(dl: SqliteDataLayer, case: VulnerabilityCase) -> str:
    """A second embargo proposal on the case, for the owner to reject."""
    revision = as_EmbargoEvent(
        id_=f"{case.id_}/embargo_events/revision",
        context=case.id_,
        end_time=days_from_now_utc(30),
    )
    dl.create(revision)
    propose(case, revision.id_)
    dl.save(case)
    return revision.id_


def _ledger(dl: SqliteDataLayer) -> list[CaseLedgerEntry]:
    return [
        e
        for e in dl.list_objects("CaseLedgerEntry")
        if isinstance(e, CaseLedgerEntry)
    ]


@pytest.mark.spec("OID-01-006")
@pytest.mark.spec("OID-01-007")
@pytest.mark.spec("CLP-07-003")
def test_a_slash_spelled_owner_reaches_its_case_owner_records():
    dl = SqliteDataLayer("sqlite:///:memory:", actor_id=_CASE_ACTOR)

    case = _propose_case(dl)

    # The proposal stored the owner canonically (#4772).
    assert str(case.attributed_to) == _VENDOR
    assert _VENDOR_AS_WRITTEN not in case.actor_participant_index
    owner = dl.read(case.actor_participant_index[_VENDOR])
    assert isinstance(owner, CaseParticipant)
    assert CVDRole.CASE_OWNER in owner.case_roles
    active_id = case.active_embargo_id
    assert active_id is not None

    # The owner rejects a revision, writing its id with the slash.
    revision_id = _seed_revision(dl, case)
    reject = reject_embargo_proposal_activity(
        cast(as_EmbargoEvent, dl.read(revision_id)),
        target=case.id_,
        actor=_VENDOR_AS_WRITTEN,
        to=[_CASE_ACTOR],
    )
    result = RejectEmbargoProposalOnCaseReceivedUseCase(
        dl, _event(reject), **_ports(dl)
    ).execute()

    assert result.disposition is HandlerDisposition.APPLIED, result.reason
    assert _case(dl).proposed_embargo_ids == []
    (entry,) = [
        e
        for e in _ledger(dl)
        if e.semantic_type == "reject_embargo_proposal_on_case"
    ]
    # The ledger keeps what the sender wrote (OID-01-006).
    assert entry.payload_snapshot.get("actor") == _VENDOR_AS_WRITTEN

    # The owner's withdrawal reaches the CASE_OWNER record: it is refused
    # because the owner ends an embargo by terminating it (MSM-07-010), not
    # because the sender has no participant record.
    leave = withdraw_from_embargo_activity(
        cast(as_EmbargoEvent, dl.read(active_id)),
        context=case.id_,
        actor=_VENDOR_AS_WRITTEN,
        to=[_CASE_ACTOR],
    )
    result = WithdrawFromEmbargoOnCaseReceivedUseCase(
        dl, _event(leave), **_ports(dl)
    ).execute()

    assert result.disposition is HandlerDisposition.REFUSED
    assert "is the case owner" in (result.reason or ""), result.reason
    assert "no participant record" not in (result.reason or "")
