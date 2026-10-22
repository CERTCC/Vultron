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

Every SYNC-16 test here is a strict ``xfail`` for unbuilt behaviour (ADR-0142),
except the ones that pin a SYNC-16 property that already holds. Each
implementation issue removes the ``xfail`` from the tests it makes pass, and
replaces a probe with a full behaviour test where the probe only pins a name.
"""

import logging
from typing import Any, cast

import pytest

from test.support.received import received_event
from vultron.adapters.driven.datalayer_sqlite import SqliteDataLayer
from vultron.core.behaviors.sync.nodes.chain import _to_persistable_entry
from vultron.core.models import fault_classes
from vultron.core.models.case_ledger import HashChainLedgerRecord
from vultron.core.models.case_ledger_entry import CaseLedgerEntry
from vultron.core.models.events.actor import (
    AnnounceVulnerabilityCaseReceivedEvent,
)
from vultron.core.models.events.fault import CreateProcessingFaultReceivedEvent
from vultron.core.models.ledger_position import LedgerPosition
from vultron.core.models.pending_case_inbox import VultronPendingCaseInbox
from vultron.core.models.replication_state import VultronReplicationState
from vultron.core.models.use_case_result import HandlerDisposition
from vultron.core.sync_helpers import store_ledger_entry
from vultron.core.use_cases.received.actor.announce import (
    AnnounceVulnerabilityCaseReceivedUseCase,
)
from vultron.core.use_cases.received.fault import (
    CreateProcessingFaultReceivedUseCase,
)
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
def test_case_diverged_failure_class_is_defined() -> None:
    """The replica's fault names the divergence by its own failure class."""
    # getattr until #4798 defines the name, so the type checkers pass now.
    constant = getattr(  # noqa: B009
        fault_classes,
        "VULTRON_FAILURE_LEDGER_ENTRY_REFUSED_CASE_DIVERGED",
    )
    assert constant == _CASE_DIVERGED


@pytest.mark.spec("SYNC-16-002")
def test_case_manager_does_not_ledger_a_divergence_fault() -> None:
    """The CASE_MANAGER commits no ledger entry for a divergence fault.

    Holds already, because the fault use case only logs. #4798 adds the
    replica side when it builds the fault's emission.
    """
    dl = SqliteDataLayer("sqlite:///:memory:", actor_id=_CASE_ACTOR_ID)
    dl.create(as_VulnerabilityCase(id_=_CASE_ID, name="current copy"))
    activity = create_processing_fault_activity(
        actor=_REPLICA_ID,
        fault=as_ProcessingFault(
            failure_class=_CASE_DIVERGED,
            in_reply_to=f"{_CASE_ID}/ledger/entries/7/announce",
        ),
        to=[_CASE_ACTOR_ID],
    )

    CreateProcessingFaultReceivedUseCase(
        dl, cast(CreateProcessingFaultReceivedEvent, received_event(activity))
    ).execute()

    assert list(dl.list_objects("CaseLedgerEntry")) == []


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
        dl, cast(CreateProcessingFaultReceivedEvent, received_event(activity))
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


@pytest.mark.spec("SYNC-16-005")
def test_a_case_copy_names_the_position_of_the_last_commit() -> None:
    """A case read after a commit carries that commit's index and hash."""
    dl = SqliteDataLayer("sqlite:///:memory:", actor_id=_CASE_ACTOR_ID)
    case = _owned_case(dl, "current copy")
    entry = _commit(dl, case, 0, case.genesis_hash)
    stored = dl.read_case(_CASE_ID)
    assert stored is not None
    activity = announce_vulnerability_case_activity(
        stored, actor=_CASE_ACTOR_ID, context=_CASE_ID
    )

    sent = activity.model_dump(by_alias=True, exclude_none=True, mode="json")

    assert sent["object"]["ledgerPosition"] == {
        "logIndex": entry.log_index,
        "entryHash": entry.entry_hash,
    }


@pytest.mark.xfail(
    strict=True,
    reason=(
        "SYNC-16-006: a copy is not yet judged by its position, so a stale"
        " one replaces the case. Tracked by #4797."
    ),
)
@pytest.mark.spec("SYNC-16-006")
@pytest.mark.spec("SYNC-16-007")
def test_a_copy_behind_the_replica_chain_is_skipped() -> None:
    """A stale copy leaves the replica's case unchanged and reports SKIPPED.

    The replica's stale, conflicting and short-chain checks all read the
    copy's position, so #4797 replaces this probe with one behaviour test for
    each.
    """
    dl = _replica_store()
    case = _owned_case(dl, "replica at entry 0")
    stale = case.model_copy(update={"name": "stale copy"})
    _commit(dl, case, 0, case.genesis_hash)
    activity = announce_vulnerability_case_activity(
        stale, actor=_CASE_ACTOR_ID, to=[_REPLICA_ID], context=_CASE_ID
    )

    result = AnnounceVulnerabilityCaseReceivedUseCase(
        dl,
        cast(AnnounceVulnerabilityCaseReceivedEvent, received_event(activity)),
    ).execute()

    assert result.disposition == HandlerDisposition.SKIPPED
    assert cast(Any, dl.read(_CASE_ID)).name == "replica at entry 0"


@pytest.mark.xfail(
    strict=True,
    reason=(
        "SYNC-16-006: a copy is not yet judged by its position, so a"
        " conflicting one replaces the case unlogged. Tracked by #4797."
    ),
)
@pytest.mark.spec("CLP-04-008")
def test_a_conflicting_copy_is_logged_at_error(caplog) -> None:
    """A copy naming a different entry at an index the replica holds is
    refused, and the conflict is logged at ERROR."""
    dl = _replica_store()
    case = _owned_case(dl, "replica at entry 0")
    _commit(dl, case, 0, case.genesis_hash)
    conflicting = case.model_copy(
        update={
            "name": "conflicting copy",
            "ledger_position": LedgerPosition(
                log_index=0, entry_hash="f" * 64
            ),
        }
    )
    activity = announce_vulnerability_case_activity(
        conflicting, actor=_CASE_ACTOR_ID, to=[_REPLICA_ID], context=_CASE_ID
    )

    with caplog.at_level(logging.ERROR, logger="vultron"):
        AnnounceVulnerabilityCaseReceivedUseCase(
            dl,
            cast(
                AnnounceVulnerabilityCaseReceivedEvent,
                received_event(activity),
            ),
        ).execute()

    assert cast(Any, dl.read(_CASE_ID)).name == "replica at entry 0"
    assert any(r.levelno == logging.ERROR for r in caplog.records), caplog.text


def _owned_case(dl: SqliteDataLayer, name: str) -> as_VulnerabilityCase:
    """An owned case stored in *dl*, at its empty ledger (SYNC-16-005)."""
    case = as_VulnerabilityCase(
        id_=_CASE_ID, name=name, attributed_to=_CASE_ACTOR_ID
    )
    dl.create(case)
    return case


def _commit(
    dl: SqliteDataLayer, case: as_VulnerabilityCase, index: int, prev: str
) -> CaseLedgerEntry:
    """Store one entry for *case* in *dl*, moving its position to it."""
    entry = _to_persistable_entry(
        HashChainLedgerRecord(
            case_id=case.id_,
            log_index=index,
            object_id=f"{case.id_}/activities/{index}",
            semantic_type="test_event",
            payload_snapshot={"log_index": index},
            prev_log_hash=prev,
        )
    )
    store_ledger_entry(entry, dl)
    return entry


def _replica_store() -> SqliteDataLayer:
    """The replica's store, expecting the case from the CASE_MANAGER."""
    dl = SqliteDataLayer("sqlite:///:memory:", actor_id=_REPLICA_ID)
    dl.save(
        VultronPendingCaseInbox(
            case_id=_CASE_ID,
            case_actor_id=_CASE_ACTOR_ID,
            invite_anchored=True,
        )
    )
    return dl


@pytest.mark.spec("PCR-02-004")
def test_case_copy_replaces_an_existing_replica() -> None:
    """A copy from the CASE_MANAGER replaces the replica's case file.

    Built already: it replaces on every copy, which is why the stale-copy
    check of SYNC-16-006 is needed.
    """
    dl = SqliteDataLayer("sqlite:///:memory:", actor_id=_REPLICA_ID)
    dl.save(
        VultronPendingCaseInbox(
            case_id=_CASE_ID,
            case_actor_id=_CASE_ACTOR_ID,
            invite_anchored=True,
        )
    )
    dl.create(as_VulnerabilityCase(id_=_CASE_ID, name="diverged copy"))
    activity = announce_vulnerability_case_activity(
        as_VulnerabilityCase(id_=_CASE_ID, name="current copy"),
        actor=_CASE_ACTOR_ID,
        to=[_REPLICA_ID],
        context=_CASE_ID,
    )

    AnnounceVulnerabilityCaseReceivedUseCase(
        dl,
        cast(AnnounceVulnerabilityCaseReceivedEvent, received_event(activity)),
    ).execute()

    assert cast(Any, dl.read(_CASE_ID)).name == "current copy"
