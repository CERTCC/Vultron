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

"""Tests for ``SvcSyncLogEntryUseCase`` (the demo ``sync-log-entry`` verb).

Covers, against a real in-memory store (``notes/triggers-test-coverage.md``):

- the state mutation: a canonical ``CaseLedgerEntry`` is minted at index 0
  with the caller's ``event_type`` verbatim, and the typed result carries its
  id, hash and index;
- the outbox effect: the entry is fanned out to the case's other participant
  through the injected ``sync_port`` (SYNC-02-002);
- the failure modes: an unknown requester is ``VultronNotFoundError``, and a
  store that does not hold the canonical log declines the mint and reports
  ``VultronCanonicalEntryError`` instead of pretending it committed.
"""

import pytest

from test.support.trigger_results import recipient_ids
from vultron.adapters.driven.datalayer_sqlite import (
    SqliteDataLayer,
    reset_datalayer,
)
from vultron.adapters.driven.sync_activity_adapter import SyncActivityAdapter
from vultron.adapters.driven.wire_render.as2 import As2WireRenderAdapter
from vultron.core.models.case_ledger_entry import CaseLedgerEntry
from vultron.core.models.use_case_result import SyncLogEntryResult
from vultron.core.use_cases.triggers.requests import (
    SyncLogEntryTriggerRequest,
)
from vultron.core.use_cases.triggers.sync_log_entry import (
    SvcSyncLogEntryUseCase,
)
from vultron.enums.roles import CVDRole
from vultron.errors import VultronCanonicalEntryError, VultronNotFoundError
from vultron.wire.as2.vocab.base.objects.actors import as_Service
from vultron.wire.as2.vocab.objects.case_participant import as_CaseParticipant
from vultron.wire.as2.vocab.objects.vulnerability_case import (
    as_VulnerabilityCase,
)

_PEER_ID = "https://example.org/actors/reporter"
_FOREIGN_CM_ID = "https://elsewhere.example/actors/other-cm"


@pytest.fixture
def actor_and_dl():
    actor = as_Service(name="Case Manager Co")
    reset_datalayer(actor.id_)
    dl = SqliteDataLayer("sqlite:///:memory:", actor_id=actor.id_)
    dl.clear_all()
    dl.create(actor)
    yield actor, dl
    dl.clear_all()
    reset_datalayer(actor.id_)


def _seed_case(
    dl: SqliteDataLayer, case_manager_id: str
) -> as_VulnerabilityCase:
    """A case whose CASE_MANAGER is *case_manager_id*, with one peer.

    ``attributed_to`` names the authority so the case mints its per-case
    genesis hash at construction; the first commit anchors on it (CLP-08-005).
    """
    case = as_VulnerabilityCase(
        name="Sync Case", attributed_to=case_manager_id
    )
    cm = as_CaseParticipant(
        attributed_to=case_manager_id,
        context=case.id_,
        case_roles=[CVDRole.CASE_MANAGER],
    )
    peer = as_CaseParticipant(
        attributed_to=_PEER_ID,
        context=case.id_,
        case_roles=[CVDRole.REPORTER],
    )
    for participant_actor_id, participant in (
        (case_manager_id, cm),
        (_PEER_ID, peer),
    ):
        case.actor_participant_index[participant_actor_id] = participant.id_
        case.case_participants.append(participant.id_)
        dl.create(participant)
    dl.create(case)
    return case


def _run(dl: SqliteDataLayer, request: SyncLogEntryTriggerRequest):
    return SvcSyncLogEntryUseCase(
        dl,
        request,
        sync_port=SyncActivityAdapter(dl),
        wire_render_port=As2WireRenderAdapter(),
    ).execute()


@pytest.mark.spec("SYNC-02-002")
@pytest.mark.spec("TRIG-10-004")
def test_commits_a_canonical_entry_and_returns_its_identity(actor_and_dl):
    actor, dl = actor_and_dl
    case = _seed_case(dl, actor.id_)

    result = _run(
        dl,
        SyncLogEntryTriggerRequest(
            actor_id=actor.id_,
            case_id=case.id_,
            object_id=case.id_,
            event_type="sync_test_event",
        ),
    )

    assert isinstance(result, SyncLogEntryResult)
    assert result.log_index == 0
    assert result.emitting_actor_id == actor.id_
    entry = dl.read(result.log_entry_id)
    assert isinstance(entry, CaseLedgerEntry)
    assert entry.case_id == case.id_
    assert entry.event_type == "sync_test_event"
    assert entry.entry_hash == result.entry_hash
    assert entry.log_object_id == case.id_


@pytest.mark.spec("SYNC-02-002")
@pytest.mark.spec("PCR-08-001")
def test_fans_the_entry_out_to_the_peer_participant(actor_and_dl):
    actor, dl = actor_and_dl
    case = _seed_case(dl, actor.id_)
    before = set(dl.outbox_list())

    _run(
        dl,
        SyncLogEntryTriggerRequest(
            actor_id=actor.id_,
            case_id=case.id_,
            object_id=case.id_,
            event_type="sync_fanout",
        ),
    )

    new_ids = set(dl.outbox_list()) - before
    assert new_ids, "the commit must queue an Announce(CaseLedgerEntry)"
    recipients = {
        recipient
        for activity_id in new_ids
        for recipient in recipient_ids(dl.read(activity_id))
    }
    assert _PEER_ID in recipients


def test_does_not_require_a_trigger_activity_port():
    """The commit tree emits through ``sync_port``, not the activity factory."""
    assert SvcSyncLogEntryUseCase._requires_trigger_activity is False


def test_unknown_requester_is_not_found(actor_and_dl):
    actor, dl = actor_and_dl
    case = _seed_case(dl, actor.id_)
    with pytest.raises(VultronNotFoundError):
        _run(
            dl,
            SyncLogEntryTriggerRequest(
                actor_id="https://example.org/actors/nobody",
                case_id=case.id_,
                object_id=case.id_,
                event_type="x",
            ),
        )


@pytest.mark.spec("CM-24-001")
@pytest.mark.spec("CLP-10-014")
@pytest.mark.spec("DL-07-009")
def test_single_container_commit_lands_in_the_case_managers_store(
    actor_and_dl,
):
    """Requester ≠ CASE_MANAGER, both hosted here (the single-server demo).

    The tree runs as the CASE_MANAGER: the entry is minted in *its* store, the
    fan-out is queued in *its* outbox (the store-scoped ``sync_port``,
    DL-07-009), and the result names it so the router drains that queue.
    Nothing is written to the requester's own store.
    """
    requester, dl = actor_and_dl
    cm_actor = as_Service(name="Hosted Case Manager")
    reset_datalayer(cm_actor.id_)
    cm_dl = dl.clone_for_actor(cm_actor.id_)
    cm_dl.clear_all()
    try:
        cm_dl.create(cm_actor)
        case = _seed_case(dl, cm_actor.id_)
        # The requester's replica and the CASE_MANAGER's canonical copy hold
        # the same case (same id, same genesis hash); only the latter mints.
        cm_dl.create(case)
        for pid in case.case_participants:
            participant = dl.read(pid)
            assert participant is not None
            cm_dl.create(participant)
        cm_before = set(cm_dl.outbox_list())

        result = _run(
            dl,
            SyncLogEntryTriggerRequest(
                actor_id=requester.id_,
                case_id=case.id_,
                object_id=case.id_,
                event_type="single_container",
            ),
        )

        assert result.emitting_actor_id == cm_actor.id_
        assert isinstance(cm_dl.read(result.log_entry_id), CaseLedgerEntry)
        assert dl.read(result.log_entry_id) is None
        assert set(cm_dl.outbox_list()) - cm_before, (
            "fan-out must be queued in the CASE_MANAGER's outbox"
        )
        assert not dl.outbox_list()
    finally:
        cm_dl.clear_all()
        reset_datalayer(cm_actor.id_)


@pytest.mark.spec("CLP-10-014")
def test_store_without_the_canonical_log_declines_and_reports_it(
    actor_and_dl,
):
    """The case's CASE_MANAGER is elsewhere: the ledger-authority guard
    declines the mint (ADR-0073) and the use case says so rather than
    returning an entry it did not record."""
    actor, dl = actor_and_dl
    case = _seed_case(dl, _FOREIGN_CM_ID)

    with pytest.raises(VultronCanonicalEntryError, match="no canonical entry"):
        _run(
            dl,
            SyncLogEntryTriggerRequest(
                actor_id=actor.id_,
                case_id=case.id_,
                object_id=case.id_,
                event_type="foreign",
            ),
        )
    assert not any(
        isinstance(obj, CaseLedgerEntry)
        for obj in dl.list_objects("CaseLedgerEntry")
    )
