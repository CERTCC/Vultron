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

"""Divergence recovery: a diverged replica reports, the CASE_MANAGER re-seeds.

Every SYNC-16 test here is a strict ``xfail`` for unbuilt behaviour (ADR-0142).
Each implementation issue removes the ``xfail`` from the tests it makes pass,
and replaces a probe with a full behaviour test where the probe only pins a
name.
"""

from typing import Any, cast

import pytest

from vultron.adapters.driven.datalayer_sqlite import SqliteDataLayer
from vultron.core.models import fault_classes
from vultron.core.models.events.actor import (
    AnnounceVulnerabilityCaseReceivedEvent,
)
from vultron.core.models.events.fault import CreateProcessingFaultReceivedEvent
from vultron.core.models.pending_case_inbox import VultronPendingCaseInbox
from vultron.core.models.replication_state import VultronReplicationState
from vultron.core.models.use_case_result import HandlerDisposition
from vultron.core.use_cases.received.actor.announce import (
    AnnounceVulnerabilityCaseReceivedUseCase,
)
from vultron.core.use_cases.received.fault import (
    CreateProcessingFaultReceivedUseCase,
)
from vultron.semantic_registry import extract_event
from vultron.wire.as2.factories import (
    announce_vulnerability_case_activity,
    create_processing_fault_activity,
)
from vultron.wire.as2.vocab.objects.processing_fault import as_ProcessingFault
from vultron.wire.as2.vocab.objects.vulnerability_case import (
    as_VulnerabilityCase,
)

_CASE_ID = "https://example.org/cases/case-diverged-001"
_CASE_ACTOR_ID = "https://example.org/actors/case-actor"
_REPLICA_ID = "https://example.org/actors/replica"
_STRANGER_ID = "https://example.org/actors/stranger"
_CASE_DIVERGED = "https://certcc.github.io/Vultron/ns/errors/LedgerEntryRefused/CaseDiverged"


@pytest.mark.xfail(
    strict=True,
    reason="SYNC-16-001: no case-diverged failure class yet. Tracked by #4798.",
)
@pytest.mark.spec("SYNC-16-001")
@pytest.mark.spec("SYNC-16-002")
def test_case_diverged_failure_class_is_defined() -> None:
    """The replica's fault names the divergence by its own failure class."""
    # getattr until #4798 defines the name, so the type checkers pass now.
    constant = getattr(  # noqa: B009
        fault_classes,
        "VULTRON_FAILURE_LEDGER_ENTRY_REFUSED_CASE_DIVERGED",
    )
    assert constant == _CASE_DIVERGED


@pytest.mark.xfail(
    strict=True,
    reason="SYNC-16-003: the fault use case only logs. Tracked by #4799.",
)
@pytest.mark.spec("SYNC-16-003")
def test_case_diverged_fault_from_a_non_participant_is_refused() -> None:
    """Only an active participant's divergence fault earns a re-seed."""
    dl = SqliteDataLayer("sqlite:///:memory:", actor_id=_CASE_ACTOR_ID)
    activity = create_processing_fault_activity(
        actor=_STRANGER_ID,
        fault=as_ProcessingFault(
            failure_class=_CASE_DIVERGED,
            in_reply_to=f"{_CASE_ID}/ledger/entries/7/announce",
        ),
        to=[_CASE_ACTOR_ID],
    )

    result = CreateProcessingFaultReceivedUseCase(
        dl, cast(CreateProcessingFaultReceivedEvent, extract_event(activity))
    ).execute()

    assert result.disposition == HandlerDisposition.REFUSED


@pytest.mark.xfail(
    strict=True,
    reason="SYNC-16-004: no per-peer re-seed record yet. Tracked by #4799.",
)
@pytest.mark.spec("SYNC-16-004")
@pytest.mark.spec("SYNC-16-008")
def test_replication_state_records_the_last_reseed() -> None:
    """The re-seed rate bound and the repeat check read per-peer state."""
    assert any(
        "reseed" in field for field in VultronReplicationState.model_fields
    )


@pytest.mark.xfail(
    strict=True,
    reason="SYNC-16-005: the case wire form has no ledger tail. Tracked by #4797.",
)
@pytest.mark.spec("SYNC-16-005")
@pytest.mark.spec("SYNC-16-006")
@pytest.mark.spec("SYNC-16-007")
def test_case_wire_form_declares_a_ledger_tail() -> None:
    """A case copy names the ledger position it reflects.

    The replica's stale, conflicting and short-chain checks all read it, so
    #4797 replaces this probe with one behaviour test for each.
    """
    assert "ledger_tail" in as_VulnerabilityCase.model_fields


@pytest.mark.spec("PCR-02-004")
def test_case_copy_replaces_an_existing_replica() -> None:
    """A copy from the CASE_MANAGER replaces the replica's case file.

    Built already: it replaces on every copy, which is why the stale-copy
    check of SYNC-16-006 is needed.
    """
    dl = SqliteDataLayer("sqlite:///:memory:", actor_id=_REPLICA_ID)
    dl.save(
        VultronPendingCaseInbox(case_id=_CASE_ID, case_actor_id=_CASE_ACTOR_ID)
    )
    dl.create(as_VulnerabilityCase(id_=_CASE_ID, name="diverged copy"))
    activity = announce_vulnerability_case_activity(
        as_VulnerabilityCase(id_=_CASE_ID, name="current copy"),
        actor=_CASE_ACTOR_ID,
        context=_CASE_ID,
    )

    AnnounceVulnerabilityCaseReceivedUseCase(
        dl,
        cast(AnnounceVulnerabilityCaseReceivedEvent, extract_event(activity)),
    ).execute()

    assert cast(Any, dl.read(_CASE_ID)).name == "current copy"
