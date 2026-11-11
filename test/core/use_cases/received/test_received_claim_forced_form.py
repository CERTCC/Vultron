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

"""A received ``pX`` claim is recorded as sent; the case's status is forced
(SM-09-003, RSH-09-010, #6080).

A participant's ``ParticipantStatus``, the ``CaseStatus`` inside it included,
is its claim about its own view.  The CASE_MANAGER records that claim exactly
as received.  When it adopts the claim, it commits its *own* conclusion as the
case's ``CaseStatus``, in the forced form: a ``pXa`` claim makes the case
``PXa``.  Every case-level decision the act takes (the teardown's cause, the
CSB-18 note) reads the case's status, never the claim.  Replicas copy both
records as committed and promote nothing (CLP-07-013, CM-23-016).

Every activity moves between stores only as the sealed body the sender's
outbox would deliver (:class:`LedgerNetwork`).
"""

import json
from typing import Any, cast

import pytest

from test.support.failed_teardown import fail_pxa_teardown
from test.support.ledger import ledger_entries
from test.support.objects import make
from vultron.adapters.outbox_sealed_body import dump_outbound_body
from vultron.core.models._helpers import _as_id
from vultron.core.models.case_participant import CaseParticipant
from vultron.core.models.case_status import CaseStatus
from vultron.core.models.dimensions import (
    EmDimension,
    PxaDimension,
    VfDimension,
)
from vultron.core.models.embargo_termination import (
    EmbargoTermination,
    ThreatSignal,
)
from vultron.core.models.note import VultronNote
from vultron.core.models.participant_status import ParticipantStatus
from vultron.core.models.use_case_result import HandlerDisposition
from vultron.core.states.cs import CS_pxa, CS_vf
from vultron.core.states.em import EM
from vultron.enums.roles import CVDRole
from vultron.wire.as2.factories import add_status_to_participant_activity
from vultron.wire.as2.vocab.objects.case_participant import (
    as_CaseParticipant,
)

from ._ledger_network import MANAGER, OWNER, REPLICAS, LedgerNetwork

#: Each ephemeral ``pX`` claim and the forced form the case records.
_FORCED = [(CS_pxa.pXa, CS_pxa.PXa), (CS_pxa.pXA, CS_pxa.PXA)]


def _send(net: LedgerNetwork, activity: Any) -> None:
    """Deliver *activity* to the CASE_MANAGER, as its sender's outbox would."""
    verdict = net.receive(MANAGER, json.loads(dump_outbound_body(activity)))
    assert verdict.disposition is HandlerDisposition.APPLIED, verdict.reason


def _claimed_pxa(net: LedgerNetwork, holder: str) -> CS_pxa:
    """The P/X/A the owner's latest status claims, in *holder*'s store."""
    status = net.record(holder, OWNER).participant_status
    assert status is not None
    assert status.case_status is not None
    return status.case_status.pxa.state


def _entry_objects(net: LedgerNetwork, semantic_type: str) -> list[dict]:
    """The ``object`` of each CASE_MANAGER entry of *semantic_type*."""
    return [
        cast(dict, e.payload_snapshot["object"])
        for e in ledger_entries(net.stores[MANAGER], net.case_id)
        if e.semantic_type == semantic_type
    ]


@pytest.mark.spec("SM-09-003")
@pytest.mark.spec("RSH-09-010")
@pytest.mark.spec("RSH-01-003")
@pytest.mark.parametrize(("claimed", "forced"), _FORCED)
def test_a_px_claim_is_recorded_as_sent_and_the_case_status_is_forced(
    claimed: CS_pxa, forced: CS_pxa
) -> None:
    """AC-1: the claim keeps ``pX``; the case's committed status is ``PX``."""
    net = LedgerNetwork(
        f"https://example.org/cases/forced-{claimed.name}", em_state=EM.NONE
    )

    _send(net, net.pxa_report(OWNER, claimed))

    assert _claimed_pxa(net, MANAGER) is claimed
    assert net.case(MANAGER).current_status.pxa.state is forced
    (status,) = _entry_objects(net, "add_participant_status_to_participant")
    assert status["caseStatus"]["pxaState"] == claimed.name
    (case_status,) = _entry_objects(net, "add_case_status_to_case")
    assert case_status["pxaState"] == forced.name


def _vendor_public_report(net: LedgerNetwork) -> Any:
    """The owner, seated as a VENDOR in every store, claims ``vP``: public
    aware (``P``) while it states its own ``vf`` (vendor unaware)."""
    for dl in net.stores.values():
        record = cast(
            CaseParticipant,
            dl.read(net.case(MANAGER).actor_participant_index[OWNER]),
        )
        record.add_role(CVDRole.VENDOR)
        dl.save(record)
    record = net.record(MANAGER, OWNER)
    current = record.participant_status
    assert current is not None
    status = make(
        ParticipantStatus,
        context=net.case_id,
        attributed_to=OWNER,
        rm=current.rm,
        vf=VfDimension(state=CS_vf.vf),
        cvd_role=record.case_roles,
        case_status=make(
            CaseStatus,
            context=net.case_id,
            attributed_to=OWNER,
            em=EmDimension(state=net.case(MANAGER).em_state),
            pxa=PxaDimension(state=CS_pxa.Pxa),
        ),
    )
    return add_status_to_participant_activity(
        status,
        target=make(
            as_CaseParticipant,
            id_=record.id_,
            context=net.case_id,
            attributed_to=OWNER,
        ),
        actor=OWNER,
        to=[MANAGER],
    )


@pytest.mark.spec("SM-09-003")
@pytest.mark.spec("RSH-09-010")
def test_a_vp_claim_keeps_the_senders_own_vf() -> None:
    """AC-1: a ``vP`` claim is recorded as sent, ``vf`` included, in the
    CASE_MANAGER's store and in each replica's; the case's status records
    the adopted ``P``."""
    net = LedgerNetwork(
        "https://example.org/cases/forced-vp", em_state=EM.NONE
    )

    _send(net, _vendor_public_report(net))

    for holder in (MANAGER, *REPLICAS):
        if holder != MANAGER:
            net.replay_ledger(holder)
        status = net.record(holder, OWNER).participant_status
        assert status is not None
        assert status.vf is not None
        assert status.vf.state is CS_vf.vf, holder
        assert _claimed_pxa(net, holder) is CS_pxa.Pxa, holder
        assert net.case(holder).current_status.pxa.state is CS_pxa.Pxa


@pytest.mark.spec("SM-09-003")
@pytest.mark.spec("CLP-07-013")
@pytest.mark.spec("CM-23-016")
@pytest.mark.parametrize(("claimed", "forced"), _FORCED)
def test_a_replica_copies_the_claim_and_the_forced_case_status(
    claimed: CS_pxa, forced: CS_pxa
) -> None:
    """AC-2: each replica holds the claim as sent and the case status as
    forced, exactly as the CASE_MANAGER committed them; it promotes
    neither."""
    net = LedgerNetwork(
        f"https://example.org/cases/forced-replica-{claimed.name}",
        em_state=EM.NONE,
    )
    _send(net, net.pxa_report(OWNER, claimed))

    for replica in REPLICAS:
        delivered = net.replay_ledger(replica)

        assert "add_participant_status_to_participant" in delivered, replica
        assert "add_case_status_to_case" in delivered, replica
        assert _claimed_pxa(net, replica) is claimed, replica
        assert net.case(replica).current_status.pxa.state is forced, replica
        assert net.case(replica).current_status == (
            net.case(MANAGER).current_status
        ), replica


@pytest.mark.spec("SM-09-003")
@pytest.mark.spec("EMB-13-005")
def test_the_teardown_names_the_signals_of_the_forced_case_status() -> None:
    """AC-4: the termination cause is the CASE_MANAGER's conclusion, so it
    names the case's ``P`` and ``X``, not the claim's ``X`` alone."""
    net = LedgerNetwork(
        "https://example.org/cases/forced-teardown", em_state=EM.ACTIVE
    )

    _send(net, net.pxa_report(OWNER, CS_pxa.pXa))

    assert net.case(MANAGER).em_state is EM.EXITED
    assert net.case(MANAGER).embargo_termination == EmbargoTermination.threat(
        [ThreatSignal.P, ThreatSignal.X]
    )


def _no_threat_report(net: LedgerNetwork) -> Any:
    """The owner's status restating its record with no embedded case
    status: a claim that names no P, X or A (RSH-09-003)."""
    record = net.record(MANAGER, OWNER)
    current = record.participant_status
    assert current is not None
    status = make(
        ParticipantStatus,
        context=net.case_id,
        attributed_to=OWNER,
        rm=current.rm,
        vf=current.vf,
        d=current.d,
        cvd_role=current.cvd_role,
    )
    return add_status_to_participant_activity(
        status,
        target=make(
            as_CaseParticipant,
            id_=record.id_,
            context=net.case_id,
            attributed_to=OWNER,
        ),
        actor=OWNER,
        to=[MANAGER],
    )


def _csb_18_notes(net: LedgerNetwork) -> list[str]:
    """The content of each CASE_MANAGER note naming the case's ``PXa``."""
    dl = net.stores[MANAGER]
    notes = [
        cast(VultronNote, dl.read(str(_as_id(n))))
        for n in net.case(MANAGER).notes
    ]
    return [n.content or "" for n in notes if "PXA='PXa'" in (n.content or "")]


@pytest.mark.spec("RSH-03-001")
@pytest.mark.spec("CSB-18-002")
@pytest.mark.spec("EMB-13-005")
def test_a_later_claim_with_no_threat_ends_the_embargo_the_case_calls_for(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """AC-4: the teardown follows the case's status, not the claim that
    starts the act.  After a failed teardown leaves the case ``PXa`` beside
    an active embargo, a later status of the owner's that names no P, X or
    A ends the embargo, with the case's ``P`` and ``X`` as the cause."""
    net = LedgerNetwork(
        "https://example.org/cases/forced-retry", em_state=EM.ACTIVE
    )
    with monkeypatch.context() as failing:
        fail_pxa_teardown(failing)
        _send(net, net.pxa_report(OWNER, CS_pxa.pXa))
    assert net.case(MANAGER).em_state is EM.ACTIVE

    _send(net, _no_threat_report(net))

    assert net.case(MANAGER).em_state is EM.EXITED
    assert net.case(MANAGER).embargo_termination == EmbargoTermination.threat(
        [ThreatSignal.P, ThreatSignal.X]
    )


@pytest.mark.spec("CSB-18-002")
def test_each_act_that_leaves_the_gap_reports_it(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """AC-4: the CSB-18 check reads the case's status after every adopted
    status, so a later status that names no P, X or A and leaves the case
    ``PXa`` beside the embargo reports the gap again (CSB-18-002: the
    invariant holds once each CASE_MANAGER act commits)."""
    fail_pxa_teardown(monkeypatch)
    net = LedgerNetwork(
        "https://example.org/cases/forced-csb-18-repeat", em_state=EM.ACTIVE
    )
    _send(net, net.pxa_report(OWNER, CS_pxa.pXa))
    assert len(_csb_18_notes(net)) == 1

    _send(net, _no_threat_report(net))

    assert net.case(MANAGER).em_state is EM.ACTIVE
    assert len(_csb_18_notes(net)) == 2


@pytest.mark.spec("SM-09-003")
@pytest.mark.spec("CSB-18-002")
def test_the_csb_18_note_names_the_forced_case_status(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """AC-4: with the teardown failed, the CASE_MANAGER's note reports the
    case's ``PXa`` beside the embargo, not the claim's ``pXa``."""
    fail_pxa_teardown(monkeypatch)
    net = LedgerNetwork(
        "https://example.org/cases/forced-csb-18", em_state=EM.ACTIVE
    )

    _send(net, net.pxa_report(OWNER, CS_pxa.pXa))

    dl = net.stores[MANAGER]
    notes = [
        cast(VultronNote, dl.read(str(_as_id(n))))
        for n in net.case(MANAGER).notes
    ]
    contents = [n.content or "" for n in notes]
    assert [c for c in contents if "PXA='PXa'" in c], contents
    assert not [c for c in contents if "PXA='pXa'" in c], contents
