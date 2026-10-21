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
"""The termination cause a ``Remove(EmbargoEvent)`` carries (#4857).

ADR-0122 revision 7 (Idea #4609): a termination's why is one of four cause
kinds, discriminated on ``kind`` (EMB-13-004).  The ``Remove`` carries it
beside the what, as ``terminationCause``, checked at the parse edge.  The
CASE_MANAGER records a case owner's ``FIX_READY``, ``FIX_DEPLOYED`` or
``OTHER`` claim as given and refuses a ``THREAT_SIGNAL`` before it commits;
every ``Remove`` the CASE_MANAGER sends carries the cause it records
(EMB-13-005).  A replica copies the cause from the ledger entry, never from
its own case state (#4748).
"""

from typing import Any, cast

import py_trees
import pytest
from pydantic import ValidationError

from test.support.ledger import ledger_entries
from vultron.adapters.driven.sync_activity_adapter import SyncActivityAdapter
from vultron.adapters.driven.trigger_activity_adapter import (
    TriggerActivityAdapter,
)
from vultron.adapters.driven.wire_render.as2 import As2WireRenderAdapter
from vultron.adapters.outbox_sealed_body import read_sealed_body_dict
from vultron.core.behaviors.bridge import BTBridge
from vultron.core.behaviors.embargo.nodes import EMBARGO_TEARDOWN_SEMANTIC_TYPE
from vultron.core.behaviors.embargo.trigger_tree import terminate_embargo_bt
from vultron.core.models._helpers import now_utc
from vultron.core.models.activity import VultronActivity
from vultron.core.models.embargo_termination import (
    _CAUSE_KINDS_BY_REASON,
    EmbargoTermination,
    FixDeployedCause,
    FixReadyCause,
    OtherCause,
    TerminationCause,
    TerminationCauseKind,
    ThreatSignal,
    ThreatSignalCause,
    ThreatSignalTermination,
    threat_signals_of,
)
from vultron.core.models.events.embargo import (
    RemoveEmbargoEventFromCaseReceivedEvent,
)
from vultron.core.models.use_case_result import HandlerDisposition
from vultron.core.states.em import EM
from vultron.core.states.embargo_register import TerminationReason
from vultron.semantic_registry import extract_event
from vultron.wire.as2.errors import VultronParseValidationError
from vultron.wire.as2.factories import (
    remove_embargo_from_case_activity,
    remove_participant_from_case_activity,
)
from vultron.wire.as2.factories.errors import VultronActivityConstructionError
from vultron.wire.as2.parser import parse_activity
from vultron.wire.as2.vocab.objects.case_participant import as_CaseParticipant
from vultron.wire.as2.vocab.objects.embargo_event import as_EmbargoEvent

from ._ledger_network import (
    BYSTANDER,
    MANAGER,
    OWNER,
    REPLICAS,
    LedgerNetwork,
)

VENDOR = "https://example.org/users/vendor"
CASE = "https://example.org/cases/tc-wire"

_NEW_CAUSES = [
    {"kind": "FIX_READY", "vendors": [VENDOR]},
    {"kind": "FIX_DEPLOYED"},
    {"kind": "OTHER"},
]

#: One cause of each kind an owner may claim, as core models.
_OWNER_CAUSES: list[TerminationCause] = [
    FixReadyCause(vendors=[BYSTANDER]),
    FixDeployedCause(),
    OtherCause(),
]


# ---------------------------------------------------------------------------
# AC-1: the cause kinds (EMB-13-004)
# ---------------------------------------------------------------------------


@pytest.mark.spec("EMB-13-004")
@pytest.mark.parametrize("cause", _NEW_CAUSES, ids=lambda c: c["kind"])
def test_an_early_termination_records_each_new_cause_kind(
    cause: dict[str, object],
) -> None:
    recorded = EmbargoTermination.model_validate(
        {"reason": TerminationReason.EARLY, "cause": cause}
    )

    assert recorded.model_dump(mode="json")["cause"] == cause
    with pytest.raises(ValidationError):
        EmbargoTermination.model_validate(
            {"reason": TerminationReason.END_TIME_REACHED, "cause": cause}
        )


@pytest.mark.spec("EMB-13-004")
def test_every_cause_kind_is_early_and_end_time_has_none() -> None:
    assert _CAUSE_KINDS_BY_REASON[TerminationReason.EARLY] == set(
        TerminationCauseKind
    )
    assert _CAUSE_KINDS_BY_REASON[TerminationReason.END_TIME_REACHED] == set()
    assert {kind.value for kind in TerminationCauseKind} == {
        "THREAT_SIGNAL",
        "FIX_READY",
        "FIX_DEPLOYED",
        "OTHER",
    }


@pytest.mark.spec("EMB-13-004")
@pytest.mark.parametrize(
    "cause",
    [
        {"kind": "LEAK"},
        {"kind": "FIX_READY"},
        {"kind": "FIX_READY", "vendors": []},
        {"kind": "FIX_READY", "vendors": [VENDOR, VENDOR]},
        {"kind": "FIX_READY", "vendors": [""]},
        {"kind": "FIX_READY", "vendors": [VENDOR, f"{VENDOR}/"]},
        {"kind": "THREAT_SIGNAL", "signals": []},
        {"kind": "THREAT_SIGNAL", "signals": ["X", "P"]},
        {"kind": "OTHER", "account": "a leak"},
    ],
    ids=[
        "unknown-kind",
        "no-vendors",
        "empty-vendors",
        "repeated-vendor",
        "blank-vendor",
        "unnormalised-vendor",
        "no-signals",
        "unordered-signals",
        "detail-on-other",
    ],
)
def test_a_malformed_cause_is_refused(cause: dict[str, object]) -> None:
    with pytest.raises(ValidationError):
        EmbargoTermination.model_validate(
            {"reason": TerminationReason.EARLY, "cause": cause}
        )


@pytest.mark.spec("EMB-13-004")
def test_an_early_termination_with_no_cause_records_the_what_alone() -> None:
    assert EmbargoTermination.from_reason(TerminationReason.EARLY) == (
        EmbargoTermination.early()
    )


# ---------------------------------------------------------------------------
# AC-2: carriage and the parse edge (EMB-13-005)
# ---------------------------------------------------------------------------


def _extract(activity: Any) -> RemoveEmbargoEventFromCaseReceivedEvent:
    event = extract_event(activity)
    assert isinstance(event, RemoveEmbargoEventFromCaseReceivedEvent)
    return event


def _remove_body(
    reason: TerminationReason = TerminationReason.EARLY,
) -> dict[str, Any]:
    embargo = as_EmbargoEvent(context=CASE, end_time=now_utc())
    activity = remove_embargo_from_case_activity(
        embargo, origin=CASE, actor=OWNER, reason=reason
    )
    return activity.model_dump(mode="json", by_alias=True, exclude_none=True)


@pytest.mark.spec("EMB-13-005")
def test_parse_edge_promotes_a_carried_cause_onto_the_event() -> None:
    body = _remove_body()
    body["terminationCause"] = {"kind": "FIX_DEPLOYED"}

    event = _extract(parse_activity(body))

    cause = event.model_dump(mode="json").get("termination_cause")
    assert cause is not None and cause["kind"] == "FIX_DEPLOYED"
    # The activity the ledger entry records carries it too.
    assert event.activity is not None
    assert event.activity.termination_cause == FixDeployedCause()


@pytest.mark.spec("EMB-13-005")
def test_a_remove_with_no_cause_extracts_none() -> None:
    event = _extract(parse_activity(_remove_body()))

    assert event.model_dump(mode="json").get("termination_cause") is None


@pytest.mark.spec("EMB-13-005")
@pytest.mark.parametrize(
    "cause",
    [
        {"kind": "LEAK"},
        {"kind": "FIX_READY"},
        {"kind": "FIX_READY", "vendors": "not-a-list"},
        {"kind": "THREAT_SIGNAL"},
        {"kind": "THREAT_SIGNAL", "signals": ["Q"]},
        "FIX_DEPLOYED",
    ],
    ids=[
        "unknown-kind",
        "missing-vendors",
        "malformed-vendors",
        "missing-signals",
        "malformed-signals",
        "not-an-object",
    ],
)
def test_parse_edge_refuses_a_malformed_cause(cause: object) -> None:
    body = _remove_body()
    body["terminationCause"] = cause

    with pytest.raises(VultronParseValidationError, match="terminationCause"):
        parse_activity(body)


@pytest.mark.spec("EMB-13-005")
def test_parse_edge_refuses_a_cause_on_an_end_time_termination() -> None:
    body = _remove_body(TerminationReason.END_TIME_REACHED)
    body["terminationCause"] = {"kind": "OTHER"}

    with pytest.raises(VultronParseValidationError, match="END_TIME_REACHED"):
        _extract(parse_activity(body))


@pytest.mark.spec("EMB-13-005")
def test_the_event_refuses_a_cause_on_an_end_time_termination() -> None:
    """The event checks the fit itself, so one built past the parse edge
    cannot carry a cause its what cannot have."""
    with pytest.raises(ValidationError, match="END_TIME_REACHED"):
        RemoveEmbargoEventFromCaseReceivedEvent(
            activity_id="urn:uuid:tc-event-end-time",
            actor_id=OWNER,
            termination_reason=TerminationReason.END_TIME_REACHED,
            termination_cause=OtherCause(),
        )


@pytest.mark.spec("EMB-13-005")
def test_parse_edge_refuses_a_cause_on_a_remove_that_ends_no_embargo() -> None:
    """Only a termination ``Remove`` has a why: a ``Remove(CaseParticipant)``
    naming one is refused, so the cause never reaches its ledger snapshot."""
    participant = as_CaseParticipant(
        attributed_to=VENDOR, context=CASE, name="vendor"
    )
    activity = remove_participant_from_case_activity(
        participant, target=CASE, actor=OWNER
    )
    body = activity.model_dump(mode="json", by_alias=True, exclude_none=True)
    body["terminationCause"] = {"kind": "THREAT_SIGNAL", "signals": ["X"]}

    with pytest.raises(VultronParseValidationError, match="terminationCause"):
        extract_event(parse_activity(body))


@pytest.mark.spec("EMB-13-005")
@pytest.mark.parametrize("cause", _OWNER_CAUSES, ids=lambda c: c.kind)
def test_the_factory_carries_the_cause_as_termination_cause(
    cause: TerminationCause,
) -> None:
    embargo = as_EmbargoEvent(context=CASE, end_time=now_utc())
    activity = remove_embargo_from_case_activity(
        embargo,
        origin=CASE,
        actor=OWNER,
        reason=TerminationReason.EARLY,
        cause=cause,
    )

    body = activity.model_dump(mode="json", by_alias=True, exclude_none=True)

    assert body["terminationCause"] == cause.model_dump(
        mode="json", by_alias=True
    )
    assert _extract(parse_activity(body)).termination_cause == cause


@pytest.mark.spec("EMB-13-005")
def test_the_factory_refuses_a_cause_on_an_end_time_termination() -> None:
    embargo = as_EmbargoEvent(context=CASE, end_time=now_utc())

    with pytest.raises(VultronActivityConstructionError):
        remove_embargo_from_case_activity(
            embargo,
            origin=CASE,
            actor=OWNER,
            reason=TerminationReason.END_TIME_REACHED,
            cause=OtherCause(),
        )


# ---------------------------------------------------------------------------
# AC-3 and AC-4: the case owner's Remove at the CASE_MANAGER (EMB-13-005)
# ---------------------------------------------------------------------------


def _owner_remove(net: LedgerNetwork, cause: TerminationCause) -> Any:
    """Route the case owner's early ``Remove`` naming *cause* to the
    CASE_MANAGER."""
    embargo = net.stores[MANAGER].read(net.initial_embargo_id)
    assert isinstance(embargo, as_EmbargoEvent)
    activity = remove_embargo_from_case_activity(
        embargo,
        origin=net.case_id,
        context=net.case_id,
        actor=OWNER,
        to=[MANAGER],
        reason=TerminationReason.EARLY,
        cause=cause,
    )
    return net.receive(
        MANAGER,
        activity.model_dump(mode="json", by_alias=True, exclude_none=True),
    )


@pytest.mark.spec("EMB-13-005")
@pytest.mark.parametrize("cause", _OWNER_CAUSES, ids=lambda c: c.kind)
def test_case_manager_records_an_owner_cause_as_given(
    cause: TerminationCause,
) -> None:
    net = LedgerNetwork(f"https://example.org/cases/tc-owner-{cause.kind}")

    result = _owner_remove(net, cause)

    assert result.disposition is HandlerDisposition.APPLIED, result.reason
    ended = net.case(MANAGER)
    assert ended.em_state is EM.EXITED
    assert ended.embargo_termination == EmbargoTermination(
        reason=TerminationReason.EARLY, cause=cause
    )
    # The ledger entry that records the Remove carries the cause with it.
    (entry,) = [
        e
        for e in ledger_entries(net.stores[MANAGER], net.case_id)
        if e.semantic_type == EMBARGO_TEARDOWN_SEMANTIC_TYPE
    ]
    snapshot = entry.payload_snapshot or {}
    assert snapshot["terminationCause"] == cause.model_dump(
        mode="json", by_alias=True
    )


@pytest.mark.spec("EMB-13-005")
def test_an_owner_fix_ready_cause_is_not_checked_against_the_vendors() -> None:
    """Ending early on a quorum is the owner's judgment: the CASE_MANAGER
    records the vendors it names, though none of them is fix-ready."""
    net = LedgerNetwork("https://example.org/cases/tc-owner-unready")
    cause = FixReadyCause(vendors=[BYSTANDER, VENDOR])

    result = _owner_remove(net, cause)

    assert result.disposition is HandlerDisposition.APPLIED, result.reason
    recorded = net.case(MANAGER).embargo_termination
    assert recorded is not None and recorded.cause == cause


@pytest.mark.spec("EMB-13-005")
def test_an_owner_threat_signal_cause_is_refused_before_the_commit() -> None:
    net = LedgerNetwork("https://example.org/cases/tc-owner-threat")
    before = ledger_entries(net.stores[MANAGER], net.case_id)

    result = _owner_remove(net, ThreatSignalCause(signals=[ThreatSignal.X]))

    assert result.disposition is HandlerDisposition.REFUSED
    # The reason points the owner to the case status update route.
    assert "case status update" in result.reason
    assert "P, X or A" in result.reason
    assert net.case(MANAGER).em_state is EM.ACTIVE
    # Refused before the commit (CLP-10-006): nothing is ledgered.
    assert ledger_entries(net.stores[MANAGER], net.case_id) == before


# ---------------------------------------------------------------------------
# #4748 AC-3: a replica copies the cause the ledger entry carries
# ---------------------------------------------------------------------------


def _assert_replicas_copy_the_termination(
    net: LedgerNetwork, expected: EmbargoTermination
) -> None:
    """Replay the ledger to each replica; its register must equal the
    CASE_MANAGER's, the ``TERMINATED`` entry's termination included."""
    assert net.case(MANAGER).embargo_termination == expected
    for replica in REPLICAS:
        assert EMBARGO_TEARDOWN_SEMANTIC_TYPE in net.replay_ledger(replica)
        assert net.case(replica).em_state is EM.EXITED, replica
        assert net.case(replica).embargo_termination == expected, replica
        assert net.register(replica) == net.register(MANAGER), replica


@pytest.mark.spec("EMB-13-005")
@pytest.mark.spec("CM-23-016")
def test_a_replica_copies_an_owner_fix_ready_cause() -> None:
    """Nothing in a replica's case state names the vendors whose readiness
    made the owner's quorum, so it can only copy them from the entry."""
    net = LedgerNetwork("https://example.org/cases/tc-replica-fix-ready")
    cause = FixReadyCause(vendors=[BYSTANDER, VENDOR])

    result = _owner_remove(net, cause)

    assert result.disposition is HandlerDisposition.APPLIED, result.reason
    _assert_replicas_copy_the_termination(
        net, EmbargoTermination(reason=TerminationReason.EARLY, cause=cause)
    )


@pytest.mark.spec("EMB-13-005")
@pytest.mark.spec("CM-23-016")
def test_a_replica_copies_signals_its_own_pxa_does_not_carry() -> None:
    """The CASE_MANAGER names ``P`` and ``A`` while every replica's case
    still reads ``pxa``: a replica that worked the cause out from its own
    state would record no signal, or other signals."""
    net = LedgerNetwork("https://example.org/cases/tc-replica-signals")
    for replica in REPLICAS:
        assert (
            threat_signals_of(net.case(replica).current_status.pxa.state) == []
        )

    result = _bridge(net).execute_with_setup(
        terminate_embargo_bt(
            case_id=net.case_id,
            result_out={},
            termination=ThreatSignalTermination(
                signals=[ThreatSignal.P, ThreatSignal.A]
            ),
        ),
        actor_id=MANAGER,
    )

    assert result.status == py_trees.common.Status.SUCCESS
    _assert_replicas_copy_the_termination(
        net, EmbargoTermination.threat([ThreatSignal.P, ThreatSignal.A])
    )


# ---------------------------------------------------------------------------
# AC-5: every Remove the CASE_MANAGER sends carries the cause it records
# ---------------------------------------------------------------------------


def _bridge(net: LedgerNetwork, actor_id: str = MANAGER) -> BTBridge:
    dl = net.stores[actor_id]
    return BTBridge(
        datalayer=dl,
        trigger_activity=TriggerActivityAdapter(dl),
        wire_render_port=As2WireRenderAdapter(),
        sync_port=SyncActivityAdapter(dl),
    )


def _sent_removes(
    net: LedgerNetwork, actor_id: str = MANAGER
) -> list[dict[str, Any]]:
    """The sealed bodies of every ``Remove`` *actor_id* queued."""
    dl = net.stores[actor_id]
    bodies = []
    for activity_id in dl.outbox_list():
        if cast(VultronActivity, dl.read(activity_id)).type_ != "Remove":
            continue
        body = read_sealed_body_dict(dl, activity_id)
        assert body is not None, f"'{activity_id}' was never sealed"
        bodies.append(body)
    return bodies


@pytest.mark.spec("EMB-13-005")
def test_the_threat_cascade_remove_carries_the_signals_it_records() -> None:
    """The cascade builds its ``Remove`` through the factory, from the
    decided termination."""
    net = LedgerNetwork("https://example.org/cases/tc-cascade")

    result = _bridge(net).execute_with_setup(
        terminate_embargo_bt(
            case_id=net.case_id,
            result_out={},
            termination=ThreatSignalTermination(
                signals=[ThreatSignal.P, ThreatSignal.A]
            ),
        ),
        actor_id=MANAGER,
    )

    assert result.status == py_trees.common.Status.SUCCESS
    recorded = net.case(MANAGER).embargo_termination
    assert recorded == EmbargoTermination.threat(
        [ThreatSignal.P, ThreatSignal.A]
    )
    assert recorded is not None and recorded.cause is not None
    expected = recorded.cause.model_dump(mode="json", by_alias=True)
    sent = _sent_removes(net)
    assert sent, "the cascade queued no Remove"
    assert all(body["terminationCause"] == expected for body in sent)
    (entry,) = [
        e
        for e in ledger_entries(net.stores[MANAGER], net.case_id)
        if e.semantic_type == EMBARGO_TEARDOWN_SEMANTIC_TYPE
    ]
    assert (entry.payload_snapshot or {})["terminationCause"] == expected


@pytest.mark.spec("EMB-13-005")
def test_an_uncaused_remove_carries_no_termination_cause() -> None:
    """An early end with no cause is valid (EMB-13-004), and its ``Remove``
    says so by leaving ``terminationCause`` out."""
    net = LedgerNetwork("https://example.org/cases/tc-uncaused")

    result = _bridge(net).execute_with_setup(
        terminate_embargo_bt(
            case_id=net.case_id,
            result_out={},
            termination=EmbargoTermination.early(),
        ),
        actor_id=MANAGER,
    )

    assert result.status == py_trees.common.Status.SUCCESS
    sent = _sent_removes(net)
    assert sent and all("terminationCause" not in body for body in sent)


def _owner_ask(
    net: LedgerNetwork,
    termination: EmbargoTermination | ThreatSignalTermination,
) -> list[dict[str, Any]]:
    """Run ``terminate_embargo_bt`` as the owner; return the asks it queued."""
    result = _bridge(net, OWNER).execute_with_setup(
        terminate_embargo_bt(
            case_id=net.case_id, result_out={}, termination=termination
        ),
        actor_id=OWNER,
    )

    assert result.status == py_trees.common.Status.SUCCESS
    sent = _sent_removes(net, OWNER)
    assert len(sent) == 1, f"expected one ask, got {sent}"
    return sent


@pytest.mark.spec("EMB-13-005")
def test_a_participant_ask_carries_the_cause_it_may_name() -> None:
    """The owner's ask names its ``FIX_DEPLOYED`` cause."""
    net = LedgerNetwork("https://example.org/cases/tc-ask-cause")

    (ask,) = _owner_ask(
        net,
        EmbargoTermination.from_reason(
            TerminationReason.EARLY, FixDeployedCause()
        ),
    )

    assert ask["terminationCause"] == FixDeployedCause().model_dump(
        mode="json", by_alias=True
    )


@pytest.mark.spec("EMB-13-005")
def test_a_participant_threat_signal_ask_names_no_cause() -> None:
    """Only the CASE_MANAGER may name ``THREAT_SIGNAL``, so the owner's
    threat-signal ask leaves ``terminationCause`` out."""
    net = LedgerNetwork("https://example.org/cases/tc-ask-threat")

    (ask,) = _owner_ask(net, ThreatSignalTermination(signals=[ThreatSignal.X]))

    assert "terminationCause" not in ask
