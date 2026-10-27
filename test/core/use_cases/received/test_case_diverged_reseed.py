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
"""The CASE_MANAGER re-seeds a replica that reports its case diverged.

A replica that refuses a copied entry extending its chain sends the
CASE_MANAGER a ``LedgerEntryRefused/CaseDiverged`` fault (SYNC-16-001).  From
an active participant, the CASE_MANAGER answers with
``Announce(VulnerabilityCase)`` of its current case, which names its ledger
position, rate-bounded per peer and never ledgered (SYNC-16-002 through
SYNC-16-004); a divergence the last re-seed already covered is logged at
ERROR (SYNC-16-008).  Every activity moves between the stores only as the
sealed body the sender's outbox delivers.
"""

import logging
from datetime import timedelta
from typing import Any, cast

import pytest

from test.support.inbox_replay import held_depth
from test.support.ledger import chain_tail, ledger_entries
from test.support.received import delivered_body
from vultron.core.models.fault_classes import (
    VULTRON_FAILURE_LEDGER_ENTRY_REFUSED_CASE_DIVERGED,
)
from vultron.core.models.replication_state import VultronReplicationState
from vultron.core.models.use_case_result import (
    HandlerDisposition,
    HandlerResult,
)
from vultron.core.states.participant_embargo_consent import (
    EmbargoConsentState,
)
from vultron.wire.as2.factories import create_processing_fault_activity
from vultron.wire.as2.vocab.objects.processing_fault import as_ProcessingFault

from ._ledger_network import (
    BYSTANDER,
    MANAGER,
    OWNER,
    PROPOSER,
    LedgerNetwork,
)

_CAUSE = "https://example.org/activities/the-act"
_STRANGER = "https://example.org/users/stranger"
_RESEED_LOGGER = "vultron.core.behaviors.sync.nodes.reseed"


def _diverged(name: str, member: str = OWNER) -> tuple[LedgerNetwork, str]:
    """A network whose bystander has refused, and reported, a diverged entry.

    The bystander's copy of *member*'s record lost its consent row, so the
    entry recording *member*'s decline does not apply to it.  Returns the
    network and the refused ``Announce``'s id.
    """
    net = LedgerNetwork(f"https://example.org/cases/{name}")
    body = net.diverged_announcement(BYSTANDER, member, _CAUSE)
    verdict = net.receive(BYSTANDER, body)
    assert verdict.disposition is HandlerDisposition.DEFERRED, verdict.reason
    return net, body["id"]


def _report(net: LedgerNetwork) -> HandlerResult:
    """Deliver the bystander's queued fault to the CASE_MANAGER."""
    ((_, verdict),) = net.deliver(BYSTANDER, to=MANAGER, type_="Create")
    return cast(HandlerResult, verdict)


def _fault_from(
    net: LedgerNetwork, sender: str, announce_id: str
) -> HandlerResult:
    """A new case-diverged fault from *sender* naming *announce_id*."""
    activity = create_processing_fault_activity(
        actor=sender,
        fault=as_ProcessingFault(
            failure_class=VULTRON_FAILURE_LEDGER_ENTRY_REFUSED_CASE_DIVERGED,
            in_reply_to=announce_id,
        ),
        to=[MANAGER],
    )
    return cast(HandlerResult, net.receive(MANAGER, delivered_body(activity)))


def _seeds(net: LedgerNetwork, to: str = BYSTANDER) -> list[dict[str, Any]]:
    """The ``Announce(VulnerabilityCase)`` bodies queued for *to*."""
    return net.sealed_bodies(
        MANAGER, to=to, type_="Announce", object_type="VulnerabilityCase"
    )


def _state(net: LedgerNetwork, peer: str) -> VultronReplicationState | None:
    key = VultronReplicationState(case_id=net.case_id, peer_id=peer).id_
    return cast(VultronReplicationState | None, net.stores[MANAGER].read(key))


def _age_last_reseed(net: LedgerNetwork, peer: str, seconds: float) -> None:
    """Move the peer's last re-seed *seconds* into the past."""
    state = _state(net, peer)
    assert state is not None and state.last_reseeded_at is not None
    state.last_reseeded_at -= timedelta(seconds=seconds)
    net.stores[MANAGER].save(state)


@pytest.mark.spec("SYNC-16-003")
@pytest.mark.spec("SYNC-16-002")
@pytest.mark.spec("PCR-02-001")
def test_an_active_participants_fault_is_answered_with_the_case() -> None:
    """One case copy, to the reporter alone, naming the ledger position.

    Nothing is committed, and the re-seed is recorded in the peer's
    replication state (SYNC-16-004).
    """
    net, _ = _diverged("reseed-answered")
    ledger_before = ledger_entries(net.stores[MANAGER], net.case_id)

    verdict = _report(net)

    assert verdict.disposition is HandlerDisposition.APPLIED, verdict.reason
    (seed,) = _seeds(net)
    assert seed["to"] == [BYSTANDER]
    assert not any(seed.get(k) for k in ("cc", "bto", "bcc"))
    assert seed["actor"] == MANAGER
    position = net.case(MANAGER).ledger_position
    assert seed["object"]["ledgerPosition"] == position.model_dump(
        mode="json", by_alias=True
    )
    assert _seeds(net, OWNER) == []
    assert ledger_entries(net.stores[MANAGER], net.case_id) == ledger_before
    state = _state(net, BYSTANDER)
    assert state is not None
    assert state.last_reseeded_at is not None
    assert state.last_reseed_position == position


@pytest.mark.spec("SYNC-16-003")
@pytest.mark.spec("SYNC-16-006")
@pytest.mark.spec("SYNC-16-007")
def test_a_reseeded_replica_converges_to_the_case_managers_case() -> None:
    """The copy replaces the diverged case and drains the held entry.

    The replica ends with the CASE_MANAGER's rows and chain tail, holds
    nothing, and reports no further divergence.
    """
    net, _ = _diverged("reseed-converges")
    _report(net)
    (seed,) = _seeds(net)

    verdict = net.receive(BYSTANDER, seed)

    assert verdict.disposition is HandlerDisposition.APPLIED, verdict.reason
    assert held_depth(net.stores[BYSTANDER], net.case_id) == 0
    replica_rows = net.record(BYSTANDER, OWNER).embargo_consents
    manager_rows = net.record(MANAGER, OWNER).embargo_consents
    assert replica_rows == manager_rows
    assert chain_tail(
        net.stores[BYSTANDER], net.case(BYSTANDER)
    ) == chain_tail(net.stores[MANAGER], net.case(MANAGER))
    assert net.deliver(BYSTANDER, to=MANAGER, type_="Create") == []


@pytest.mark.spec("SYNC-16-003")
@pytest.mark.spec("HP-01-006")
@pytest.mark.parametrize(
    "who",
    ["a stranger", "a participant that declined the embargo"],
)
def test_a_fault_from_a_sender_not_active_is_refused(who: str) -> None:
    """Refused before anything is recorded or sent (CM-10-004).

    A participant whose own decline is the entry it refused is no longer an
    active participant while the embargo is in force, so its fault earns no
    case content either.
    """
    if who == "a stranger":
        net, announce_id = _diverged("reseed-stranger")
        verdict = _fault_from(net, _STRANGER, announce_id)
        sender = _STRANGER
    else:
        net, _ = _diverged("reseed-inert", member=BYSTANDER)
        assert (
            net.record(MANAGER, BYSTANDER).embargo_consents[0].state
            is EmbargoConsentState.DECLINED
        )
        verdict = _report(net)
        sender = BYSTANDER

    assert verdict.disposition is HandlerDisposition.REFUSED
    assert "not an active participant" in (verdict.reason or "")
    assert _seeds(net, sender) == []
    state = _state(net, sender)
    assert state is None or state.last_reseeded_at is None


@pytest.mark.spec("SYNC-16-003")
def test_a_fault_naming_no_announce_this_actor_sent_is_refused() -> None:
    """The fault carries no case, so one naming no ledger announce has none."""
    net, _ = _diverged("reseed-unknown-announce")

    verdict = _fault_from(net, BYSTANDER, "https://example.org/activities/x")

    assert verdict.disposition is HandlerDisposition.REFUSED
    assert "names no case" in (verdict.reason or "")
    assert _seeds(net) == []


@pytest.mark.spec("SYNC-16-004")
def test_reseeds_are_rate_bounded_per_peer_not_suppressed() -> None:
    """A fault inside the cooldown re-seeds nothing; one after it does."""
    from vultron.core.behaviors.sync.nodes.reseed import (
        RESEED_COOLDOWN_SECONDS,
    )

    net, announce_id = _diverged("reseed-cooldown")
    assert _report(net).disposition is HandlerDisposition.APPLIED
    first = _state(net, BYSTANDER)
    assert first is not None

    within = _fault_from(net, BYSTANDER, announce_id)

    assert within.disposition is HandlerDisposition.SKIPPED
    assert "cooldown" in (within.reason or "")
    assert len(_seeds(net)) == 1
    assert _state(net, BYSTANDER) == first

    _age_last_reseed(net, BYSTANDER, RESEED_COOLDOWN_SECONDS)
    after = _fault_from(net, BYSTANDER, announce_id)

    assert after.disposition is HandlerDisposition.APPLIED, after.reason
    assert len(_seeds(net)) == 2


@pytest.mark.spec("SYNC-16-008")
def test_a_divergence_after_an_acknowledged_reseed_is_logged_at_error(
    caplog: pytest.LogCaptureFixture,
) -> None:
    """The peer applied a copy that reflected the entry: a CASE_MANAGER defect.

    The first fault, with no re-seed before it, is routine.  Once the peer's
    acknowledged position reaches the re-seed's, a fault for the same entry
    is an ERROR naming the entry and the position.
    """
    net, announce_id = _diverged("reseed-repeat-acked")
    with caplog.at_level(logging.WARNING, logger=_RESEED_LOGGER):
        _report(net)
    assert not _reseed_records(caplog, logging.WARNING)
    (entry,) = ledger_entries(net.stores[MANAGER], net.case_id)
    _acknowledge(net, BYSTANDER, entry.entry_hash)

    caplog.clear()
    with caplog.at_level(logging.WARNING, logger=_RESEED_LOGGER):
        _fault_from(net, BYSTANDER, announce_id)

    (error,) = _reseed_records(caplog, logging.ERROR)
    message = error.getMessage()
    assert "SYNC-16-008" in message
    assert BYSTANDER in message
    assert entry.id_ in message


@pytest.mark.spec("SYNC-16-008")
@pytest.mark.spec("SYNC-16-004")
def test_a_divergence_after_an_unacknowledged_reseed_is_a_warning(
    caplog: pytest.LogCaptureFixture,
) -> None:
    """A lost or in-flight copy is recovery, not a defect.

    The peer never acknowledged the re-seed's position, so the repeat is a
    WARNING, never an ERROR, and the rate-bounded re-seed answers it once
    the cooldown has passed.
    """
    from vultron.core.behaviors.sync.nodes.reseed import (
        RESEED_COOLDOWN_SECONDS,
    )

    net, announce_id = _diverged("reseed-repeat-lost")
    _report(net)
    _age_last_reseed(net, BYSTANDER, RESEED_COOLDOWN_SECONDS)

    with caplog.at_level(logging.WARNING, logger=_RESEED_LOGGER):
        verdict = _fault_from(net, BYSTANDER, announce_id)

    assert not _reseed_records(caplog, logging.ERROR)
    (warning,) = _reseed_records(caplog, logging.WARNING)
    assert "has not acknowledged" in warning.getMessage()
    assert verdict.disposition is HandlerDisposition.APPLIED, verdict.reason
    assert len(_seeds(net)) == 2


def _reseed_records(
    caplog: pytest.LogCaptureFixture, at_least: int
) -> list[logging.LogRecord]:
    """The re-seed module's records at *at_least* or above."""
    return [
        r
        for r in caplog.records
        if r.name.startswith(_RESEED_LOGGER) and r.levelno >= at_least
    ]


def _acknowledge(net: LedgerNetwork, peer: str, entry_hash: str) -> None:
    """Record *peer*'s acknowledgement of the entry *entry_hash* names, as its
    ``Reject`` or ``Read`` would (SYNC-04-001)."""
    state = _state(net, peer)
    assert state is not None
    state.last_acknowledged_hash = entry_hash
    net.stores[MANAGER].save(state)


@pytest.mark.spec("SYNC-16-008")
def test_a_divergence_past_the_last_reseed_is_routine(
    caplog: pytest.LogCaptureFixture,
) -> None:
    """A refused entry newer than the last copy is ordinary recovery."""
    from vultron.core.behaviors.embargo.copy_commit import (
        commit_and_apply_embargo_entries,
    )

    net, _ = _diverged("reseed-newer")
    _report(net)
    change = net.consent_row_change(PROPOSER, EmbargoConsentState.DECLINED)
    commit_and_apply_embargo_entries(
        net.stores[MANAGER],
        net.case_id,
        [net.planned_consent_entry(change, _CAUSE)],
    )
    newer = net.sealed_bodies(
        MANAGER, to=BYSTANDER, type_="Announce", object_type="CaseLedgerEntry"
    )[-1]
    assert newer["object"]["logIndex"] > (
        cast(
            VultronReplicationState, _state(net, BYSTANDER)
        ).last_reseed_position.log_index  # type: ignore[union-attr]
    )

    with caplog.at_level(logging.ERROR, logger=_RESEED_LOGGER):
        _fault_from(net, BYSTANDER, newer["id"])

    assert not [r for r in caplog.records if r.levelno >= logging.ERROR]


@pytest.mark.spec("SYNC-16-004")
@pytest.mark.spec("BT-14-001")
def test_a_copy_the_port_cannot_build_is_an_internal_error(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The CASE_MANAGER's own failure is raised, never blamed on the sender.

    Nothing is queued or recorded, so the next fault re-seeds: a cooldown
    started by a copy that was never sent would strand the peer for its
    length (the reasoning SYNC-15-003 applies to replay).
    """
    from vultron.adapters.driven.trigger_activity_adapter import (
        TriggerActivityAdapter,
    )
    from vultron.errors import VultronBTInternalError, VultronValidationError

    def _fail(*args: Any, **kwargs: Any) -> str:
        raise VultronValidationError("the case cannot be rendered")

    net, announce_id = _diverged("reseed-port-fails")
    with monkeypatch.context() as patched:
        patched.setattr(
            TriggerActivityAdapter, "announce_vulnerability_case", _fail
        )
        with pytest.raises(VultronBTInternalError, match="could not re-seed"):
            _report(net)

    assert _seeds(net) == []
    state = _state(net, BYSTANDER)
    assert state is None or state.last_reseeded_at is None

    retried = _fault_from(net, BYSTANDER, announce_id)

    assert retried.disposition is HandlerDisposition.APPLIED, retried.reason
    assert len(_seeds(net)) == 1


@pytest.mark.spec("SYNC-16-004")
def test_a_record_that_fails_withdraws_the_queued_copy(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The copy, its outbox entry and its record land together or not at all,
    so no copy is ever queued without starting the cooldown."""
    from vultron.core.behaviors.sync.nodes import reseed
    from vultron.errors import VultronBTInternalError, VultronValidationError

    def _fail(*args: Any, **kwargs: Any) -> None:
        raise VultronValidationError("the replication state is unwritable")

    net, _ = _diverged("reseed-record-fails")
    outbox_before = list(net.stores[MANAGER].outbox_list())
    with monkeypatch.context() as patched:
        patched.setattr(reseed, "record_reseed", _fail)
        with pytest.raises(VultronBTInternalError):
            _report(net)

    assert list(net.stores[MANAGER].outbox_list()) == outbox_before
    assert _seeds(net) == []


@pytest.mark.spec("CM-23-013")
@pytest.mark.spec("SYNC-16-003")
def test_a_fault_on_a_fully_closed_case_is_dropped() -> None:
    """Past the post-close boundary nothing is sent or recorded."""
    from test.support.ledger import commit_case_manager_closure

    from ._ledger_network import NETWORKS

    net, _ = _diverged("reseed-closed")
    # The closure entry is a bare stand-in written outside any act, which
    # neither the label check nor a rebuild can read: leave it unchecked.
    NETWORKS.remove(net)
    commit_case_manager_closure(net.stores[MANAGER], net.case_id)

    verdict = _report(net)

    assert verdict.disposition is HandlerDisposition.REFUSED
    assert _seeds(net) == []
    state = _state(net, BYSTANDER)
    assert state is None or state.last_reseeded_at is None


@pytest.mark.spec("SYNC-16-003")
def test_a_fault_naming_an_announce_this_actor_did_not_send_is_refused() -> (
    None
):
    """An Announce held here but sent by another actor names no copy this
    actor sent the peer, so it names no case either."""
    from vultron.wire.as2.factories import announce_log_entry_activity
    from vultron.wire.as2.vocab.objects.case_ledger_entry import (
        as_CaseLedgerEntry,
    )

    net, _ = _diverged("reseed-foreign-announce")
    (entry,) = ledger_entries(net.stores[MANAGER], net.case_id)
    foreign = announce_log_entry_activity(
        entry=as_CaseLedgerEntry.model_validate(entry.model_dump(mode="json")),
        actor=OWNER,
        to=[MANAGER],
    )
    net.stores[MANAGER].save(foreign)

    verdict = _fault_from(net, BYSTANDER, foreign.id_)

    assert verdict.disposition is HandlerDisposition.REFUSED
    assert "names no case" in (verdict.reason or "")
    assert _seeds(net) == []


def _run_reseed(net: LedgerNetwork, node: Any) -> Any:
    from vultron.adapters.driven.trigger_activity_adapter import (
        TriggerActivityAdapter,
    )
    from vultron.core.behaviors.bridge import BTBridge

    dl = net.stores[MANAGER]
    return BTBridge(
        datalayer=dl, trigger_activity=TriggerActivityAdapter(dl)
    ).execute_with_setup(tree=node, actor_id=MANAGER)


@pytest.mark.spec("CM-10-004")
def test_the_reseed_node_sends_no_case_to_a_peer_not_active() -> None:
    """Its own content gate, for callers without the fault's sender guard."""
    from py_trees.common import Status

    from vultron.core.behaviors.sync.nodes.reseed import ReseedPeerNode

    net = LedgerNetwork("https://example.org/cases/reseed-node-withheld")
    node = ReseedPeerNode(case_id=net.case_id, peer_id=_STRANGER)

    result = _run_reseed(net, node)

    assert result.status is Status.SUCCESS
    assert node.withheld and not node.reseeded
    assert _seeds(net, _STRANGER) == []
    assert _state(net, _STRANGER) is None


@pytest.mark.spec("CM-10-004")
def test_the_reseed_node_fails_when_its_gate_is_undecidable() -> None:
    """A case this store does not hold cannot be judged, so nothing is sent."""
    from py_trees.common import Status

    from vultron.core.behaviors.sync.nodes.reseed import ReseedPeerNode

    net = LedgerNetwork("https://example.org/cases/reseed-node-no-case")
    node = ReseedPeerNode(
        case_id="https://example.org/cases/unknown", peer_id=BYSTANDER
    )

    result = _run_reseed(net, node)

    assert result.status is Status.FAILURE
    assert not node.reseeded
