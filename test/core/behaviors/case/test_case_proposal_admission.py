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

"""Case-proposal admission decision: CP-05-002 and CP-05-004.

The case actor service adjudicates an inbound ``Create(as_CaseProposal)`` at the
``EvaluateCaseProposal`` call-out point and emits ``Reject(as_CaseProposal)``
when it declines. These tests pin five properties:

- The DETERMINISTIC default admits, so the pre-existing accept path is unchanged
  (BT-23-001, BT-23-011).
- A declining backend emits a Reject addressed to the vendor with the proposal
  inline (CP-05-004, CP-05-009).
- A decline writes **no** case state. The decline arm runs ahead of every effect,
  so there is no half-built case paired with a "declined" response (CLP-10-009).
- **A refusal is terminal.** A decline whose Reject cannot be emitted fails the
  tree rather than falling through into the accept flow. This is the regression
  worth guarding: a Selector falls through on FAILURE and
  ``_EmitSingleActivityBase.update()`` converts any exception into FAILURE, so
  before the decline record gated the accept arm a declining policy produced a
  *full accept* — case created, ``Accept`` + ``Create`` queued, status SUCCESS.
- An answered proposal is not re-adjudicated, whether it was accepted
  (CP-05-005, CP-05-006), declined, or has a retry marker in flight.
"""

from types import SimpleNamespace
from typing import cast

import py_trees
import pytest
from py_trees.common import Status

from test.support.ledger import (
    commit_case_fully_closed,
    committed_event_types,
)
from vultron.adapters.driven.datalayer_sqlite import SqliteDataLayer
from vultron.adapters.driven.sync_activity_adapter import SyncActivityAdapter
from vultron.adapters.driven.trigger_activity_adapter import (
    TriggerActivityAdapter,
)
from vultron.adapters.driven.wire_render.as2 import As2WireRenderAdapter
from vultron.adapters.outbox_sealed_body import read_sealed_body_dict
from vultron.core.behaviors.bridge import BTBridge
from vultron.core.behaviors.call_out.bundles.case_proposal import (
    CASE_PROPOSAL_DETERMINISTIC,
    CaseProposalCallOutBundle,
)
from vultron.core.behaviors.case.case_proposal_received_tree import (
    CLOSED_CASE_DECLINE_REASON,
    create_case_proposal_received_tree,
)
from vultron.core.behaviors.case.nodes import proposal_case_lookup
from vultron.core.behaviors.case.nodes.proposal_admission_conditions import (
    CheckProposalCaseFullyClosedNode,
)
from vultron.core.behaviors.case.nodes.proposal_case_lookup import (
    accept_scan_can_match,
    accepted_case_id,
    activity_names_proposal,
)
from vultron.core.behaviors.case.nodes.proposal_retry_marker import (
    case_is_announced,
)
from vultron.core.models.actor import VultronOrganization
from vultron.core.models.case import VulnerabilityCase
from vultron.core.models.case_proposal_admission import (
    CaseProposalAdmissionRecord,
)
from vultron.core.models.case_proposal_decline import (
    CaseProposalDeclineRecord,
)
from vultron.core.models.pending_create_case_activity import (
    PendingCreateCaseActivity,
)
from vultron.core.models.report import VulnerabilityReport
from vultron.core.ports.case_persistence import CasePersistence
from vultron.enums.roles import CVDRole
from vultron.errors import VultronWiringError
from vultron.semantic_registry import extract_event
from vultron.wire.as2.vocab.base.objects.activities.transitive import as_Create
from vultron.wire.as2.vocab.objects.case_proposal import as_CaseProposal
from vultron.wire.as2.vocab.objects.vulnerability_case import (  # noqa: F401
    as_VulnerabilityCase,
)
from vultron.wire.as2.vocab.objects.vulnerability_report import (
    as_VulnerabilityReport,
)

_CASE_ACTOR_URI = "https://case.example.org/actors/case-actor"
_VENDOR_URI = "https://vendor.example.org/actors/vendor"
_REPORTER_URI = "https://finder.example.org/actors/finder"
_REPORT_URI = "https://finder.example.org/reports/r-001"
_PROPOSAL_URI = "https://vendor.example.org/proposals/p-001"


# ---------------------------------------------------------------------------
# Fixtures and helpers
# ---------------------------------------------------------------------------


@pytest.fixture
def dl():
    """Isolated store.

    ``clear_all()`` on both sides is required, not tidiness: the in-memory
    SQLite engine is shared within a process, so a fresh ``SqliteDataLayer``
    still sees another test's outbox rows.
    """
    _dl = SqliteDataLayer("sqlite:///:memory:", actor_id=_CASE_ACTOR_URI)
    _dl.clear_all()
    yield _dl
    _dl.clear_all()
    _dl.close()


class _SpyBackend(py_trees.behaviour.Behaviour):
    """Records every ``update()`` so a test can assert whether it was *ticked*.

    A factory-call counter would not answer the question: tree builders invoke
    the factory while composing the tree, so a bundle field is called even for a
    branch that never runs. Only ``update()`` tells you the decision was made.
    """

    def __init__(self, name: str, ticks: list[str], verdict: Status) -> None:
        super().__init__(name=name)
        self._ticks = ticks
        self._verdict = verdict

    def update(self) -> Status:
        self._ticks.append(self.name)
        return self._verdict


def _spy_bundle(
    ticks: list[str], verdict: Status
) -> CaseProposalCallOutBundle:
    """Bundle whose admission backend returns *verdict* and records its ticks."""

    def _factory(name: str) -> py_trees.behaviour.Behaviour:
        return _SpyBackend(name, ticks, verdict)

    return CaseProposalCallOutBundle(
        evaluate_proposal_factory=_factory,  # type: ignore[arg-type]
    )


def _declining_bundle(ticks: list[str]) -> CaseProposalCallOutBundle:
    return _spy_bundle(ticks, Status.FAILURE)


def _admitting_bundle(ticks: list[str]) -> CaseProposalCallOutBundle:
    return _spy_bundle(ticks, Status.SUCCESS)


def _proposal(
    proposal_uri: str = _PROPOSAL_URI, proposer_uri: str = _VENDOR_URI
) -> as_CaseProposal:
    """A proposal carrying its report inline, as CP-01-004 requires."""
    return as_CaseProposal(
        id_=proposal_uri,
        attributed_to=proposer_uri,
        object_=as_VulnerabilityReport(
            id_=_REPORT_URI, attributed_to=_REPORTER_URI
        ),
        target=_CASE_ACTOR_URI,
    )


def _run_tree(
    dl,
    *,
    call_out: CaseProposalCallOutBundle | None = None,
    report_id: str | None = _REPORT_URI,
    with_proposal_dict: bool = True,
    with_trigger_port: bool = True,
    proposal_uri: str = _PROPOSAL_URI,
    proposer_uri: str = _VENDOR_URI,
) -> Status:
    """Build and run the received-side tree the way the use case does.

    ``proposal_uri`` and ``proposer_uri`` let a test send a second proposal, from
    the same or another proposer, for the report an earlier one named.

    ``with_proposal_dict`` and ``with_trigger_port`` model the two ways the
    ``Reject`` emit can fail: a replay path that carries no wire proposal, and a
    caller that injected no ``TriggerActivityPort``.
    """
    proposal = _proposal(proposal_uri, proposer_uri)
    activity = as_Create(
        actor=VultronOrganization(id_=proposer_uri),
        object_=proposal,
        to=[_CASE_ACTOR_URI],
    )
    event = extract_event(activity).model_copy(
        update={"receiving_actor_id": _CASE_ACTOR_URI}
    )
    tree = create_case_proposal_received_tree(
        report_id=report_id,
        proposal_id=proposal_uri,
        proposer_uri=proposer_uri,
        proposal_dict=(
            proposal.model_dump(by_alias=True, serialize_as_any=True)
            if with_proposal_dict
            else None
        ),
        inline_report=VulnerabilityReport(
            id_=_REPORT_URI, attributed_to=_REPORTER_URI
        ),
        call_out=call_out,
    )
    result = BTBridge(
        datalayer=dl,
        wire_render_port=As2WireRenderAdapter(),
        trigger_activity=(
            TriggerActivityAdapter(dl) if with_trigger_port else None
        ),
        sync_port=SyncActivityAdapter(dl),
    ).execute_with_setup(
        tree=tree,
        actor_id=_CASE_ACTOR_URI,
        activity=event,
        owner_profile=activity.actor,
    )
    return result.status


def _outbox_activities(dl) -> list:
    """Return the stored activity objects currently queued in the outbox."""
    return [obj for obj in (dl.read(i) for i in dl.outbox_list()) if obj]


def _types_in_outbox(dl) -> list[str]:
    return [str(getattr(a, "type_", "")) for a in _outbox_activities(dl)]


def _cases(dl) -> list:
    return [
        c
        for c in dl.list_objects("VulnerabilityCase")
        if isinstance(c, VulnerabilityCase)
    ]


# ---------------------------------------------------------------------------
# The default admits — the pre-existing path is unchanged
# ---------------------------------------------------------------------------


@pytest.mark.spec("CP-05-002")
@pytest.mark.spec("BT-23-001")
class TestDeterministicDefaultAdmits:
    def test_default_bundle_creates_the_case_and_accepts(self, dl):
        """An unconfigured deployment admits every well-formed proposal."""
        status = _run_tree(dl)

        assert status == Status.SUCCESS
        assert len(_cases(dl)) == 1, "the accept flow must create the case"
        assert "Accept" in _types_in_outbox(dl)
        assert "Reject" not in _types_in_outbox(dl)

    def test_explicit_deterministic_singleton_matches_the_default(self, dl):
        """Passing CASE_PROPOSAL_DETERMINISTIC is the same as passing nothing."""
        status = _run_tree(dl, call_out=CASE_PROPOSAL_DETERMINISTIC)

        assert status == Status.SUCCESS
        assert len(_cases(dl)) == 1
        assert "Reject" not in _types_in_outbox(dl)

    def test_admitting_backend_is_ticked_exactly_once(self, dl):
        """The admission decision is made once, not once per Selector branch."""
        ticks: list[str] = []

        _run_tree(dl, call_out=_admitting_bundle(ticks))

        assert ticks == ["EvaluateCaseProposal"]


# ---------------------------------------------------------------------------
# A decline emits Reject and writes nothing
# ---------------------------------------------------------------------------


@pytest.mark.spec("CP-05-004")
class TestDeclineEmitsReject:
    def test_reject_is_queued_to_the_outbox(self, dl):
        """CP-05-004: declining sends Reject(as_CaseProposal)."""
        status = _run_tree(dl, call_out=_declining_bundle([]))

        assert status == Status.SUCCESS, (
            "a declined proposal is a completed protocol step, "
            "not a processing failure"
        )
        assert _types_in_outbox(dl) == ["Reject"]

    def test_reject_is_addressed_to_the_vendor(self, dl):
        """The vendor that proposed is the one told it was declined."""
        _run_tree(dl, call_out=_declining_bundle([]))

        (reject,) = _outbox_activities(dl)
        assert reject.to == [_VENDOR_URI]
        assert reject.actor == _CASE_ACTOR_URI

    @pytest.mark.spec("CP-05-009")
    def test_reject_carries_the_proposal_inline(self, dl):
        """AKM-03-003: the vendor cannot dereference a URI in our store.

        ``dl.read()`` rehydrates the stored activity, so the assertion reads the
        typed ``as_CaseProposal`` rather than the dict that was written. A bare
        URI would come back as a ``str``, which is the failure this pins.
        """
        _run_tree(dl, call_out=_declining_bundle([]))

        (reject,) = _outbox_activities(dl)
        proposal = reject.object_
        assert not isinstance(proposal, str), (
            f"object_ must not be a bare URI, got {proposal!r}"
        )
        assert getattr(proposal, "id_", None) == _PROPOSAL_URI
        # The report the proposal was about travels with it, so the vendor can
        # correlate the refusal without reading anything from our store.
        assert (
            getattr(getattr(proposal, "object_", None), "id_", None)
            == _REPORT_URI
        )

    def test_decline_still_emits_reject_without_a_report_uri(self, dl):
        """The decision does not depend on the report URI being extractable."""
        status = _run_tree(dl, call_out=_declining_bundle([]), report_id=None)

        assert status == Status.SUCCESS
        assert _types_in_outbox(dl) == ["Reject"]


@pytest.mark.spec("CLP-10-009")
class TestDeclineWritesNoCaseState:
    """A refusal precedes every effect, so nothing half-built is left behind."""

    def test_no_case_is_created(self, dl):
        _run_tree(dl, call_out=_declining_bundle([]))

        assert _cases(dl) == []

    def test_no_accept_is_sent(self, dl):
        """The vendor must not receive both an Accept and a Reject."""
        _run_tree(dl, call_out=_declining_bundle([]))

        assert "Accept" not in _types_in_outbox(dl)

    def test_no_retry_marker_is_written(self, dl):
        """No Create(VulnerabilityCase) is owed, so no marker may linger."""
        _run_tree(dl, call_out=_declining_bundle([]))

        assert (
            dl.read(PendingCreateCaseActivity.build_id(_PROPOSAL_URI)) is None
        )


# ---------------------------------------------------------------------------
# A refusal is terminal: a failed Reject must never become an accept
# ---------------------------------------------------------------------------


@pytest.mark.spec("CP-05-002")
@pytest.mark.spec("CLP-10-009")
class TestAFailedRejectDoesNotBecomeAnAccept:
    """The regression this arm's structure exists to prevent.

    ``_EmitSingleActivityBase.update()`` converts any exception into FAILURE, and
    a Selector falls through on FAILURE. Before the decline record gated the
    accept arm, a decline whose Reject could not be built produced a *full
    accept*: case created, ledger entries committed, ``Accept`` + ``Create``
    queued, status SUCCESS. A refusal gate whose failure direction is "admit" is
    worse than no gate.
    """

    def test_no_wire_proposal_fails_instead_of_accepting(self, dl):
        """A replay path with no wire proposal cannot build an inline Reject."""
        status = _run_tree(
            dl, call_out=_declining_bundle([]), with_proposal_dict=False
        )

        assert status == Status.FAILURE
        assert _cases(dl) == [], "a declined proposal must create no case"
        assert _types_in_outbox(dl) == [], "nothing may be sent to the vendor"

    def test_missing_trigger_port_fails_instead_of_accepting(self, dl):
        """A caller that injected no TriggerActivityPort cannot emit."""
        status = _run_tree(
            dl, call_out=_declining_bundle([]), with_trigger_port=False
        )

        assert status == Status.FAILURE
        assert _cases(dl) == []
        assert _types_in_outbox(dl) == []

    def test_the_decline_is_recorded_even_when_the_emit_fails(self, dl):
        """The record is written first, which is what makes the refusal stick."""
        _run_tree(dl, call_out=_declining_bundle([]), with_proposal_dict=False)

        record_id = CaseProposalDeclineRecord.build_id(_PROPOSAL_URI)
        assert dl.read(record_id) is not None

    def test_a_later_admitting_delivery_does_not_reverse_the_decline(self, dl):
        """Once declined, an admitting backend cannot accept the proposal."""
        _run_tree(dl, call_out=_declining_bundle([]), with_proposal_dict=False)

        status = _run_tree(dl)  # deterministic default admits

        assert _cases(dl) == [], "the recorded refusal outranks a later admit"
        assert "Accept" not in _types_in_outbox(dl)
        assert status == Status.SUCCESS, (
            "the resend arm completes the owed Reject, so the delivery is "
            "handled rather than failed"
        )
        assert _types_in_outbox(dl) == ["Reject"]


# ---------------------------------------------------------------------------
# A declined proposal is not re-adjudicated, and a lost Reject is recoverable
# ---------------------------------------------------------------------------


@pytest.mark.spec("CP-05-004")
class TestDeclineIsIdempotent:
    def test_redelivery_does_not_queue_a_second_reject(self, dl):
        """A retrying proposer gets one Reject, not one per delivery."""
        _run_tree(dl, call_out=_declining_bundle([]))
        assert _types_in_outbox(dl) == ["Reject"]

        ticks: list[str] = []
        status = _run_tree(dl, call_out=_declining_bundle(ticks))

        assert status == Status.SUCCESS
        assert _types_in_outbox(dl) == ["Reject"]
        assert ticks == [], "the decision stands; do not consult the backend"

    def test_redelivery_after_the_reject_was_delivered_emits_nothing(self, dl):
        """The bound holds *after* delivery, which is when the outbox empties.

        Delivery is what makes this hard. ``outbox_pop`` removes the ``Reject``
        while its stored copy remains, so "is one queued?" answers no for a
        refusal that was successfully delivered — indistinguishable from one
        that was never sent. A guard reading the outbox therefore re-emits on
        every later delivery, and nothing bounds that: whoever replays the
        proposal chooses how many ``Reject`` activities this service mints and
        stores. The answer has to come from the decline record's
        ``reject_activity_id``, which survives delivery.
        """
        _run_tree(dl, call_out=_declining_bundle([]))
        assert _types_in_outbox(dl) == ["Reject"]

        first = dl.outbox_pop()
        assert dl.outbox_list() == [], "the Reject has now been delivered"

        ticks: list[str] = []
        for _ in range(3):
            assert (
                _run_tree(dl, call_out=_declining_bundle(ticks))
                == Status.SUCCESS
            )
            assert _types_in_outbox(dl) == [], (
                "the proposer was already told; a redelivery must not mint a "
                "fresh Reject"
            )

        assert ticks == [], "the decision stands; do not consult the backend"
        rejects = [
            a
            for a in dl.list_objects("Reject")
            if str(getattr(a, "type_", "")) == "Reject"
        ]
        assert len(rejects) == 1, (
            "exactly one Reject was ever built; three redeliveries produced "
            "no more"
        )
        assert rejects[0].id_ == first

        record = dl.read(CaseProposalDeclineRecord.build_id(_PROPOSAL_URI))
        assert record.reject_activity_id == first, (
            "the record names what was queued — this is the fact the outbox "
            "cannot keep"
        )

    def test_redelivery_emits_a_reject_that_was_never_queued(self, dl):
        """Because the record is written first, a lost Reject is recoverable."""
        _run_tree(dl, call_out=_declining_bundle([]), with_proposal_dict=False)
        assert _types_in_outbox(dl) == []

        status = _run_tree(dl, call_out=_declining_bundle([]))

        assert status == Status.SUCCESS
        assert _types_in_outbox(dl) == ["Reject"]
        assert _cases(dl) == []


# ---------------------------------------------------------------------------
# An answered proposal is never re-adjudicated (CP-05-005, CP-05-006)
# ---------------------------------------------------------------------------


@pytest.mark.spec("CP-05-005")
@pytest.mark.spec("CP-05-006")
class TestAnsweredProposalsAreNotReAdjudicated:
    def test_duplicate_does_not_consult_the_call_out_point(self, dl):
        """An Accept already sent is irrevocable, so no later decline may run."""
        _run_tree(dl)  # first delivery admits
        assert len(_cases(dl)) == 1

        ticks: list[str] = []
        status = _run_tree(dl, call_out=_declining_bundle(ticks))

        assert status == Status.SUCCESS
        assert ticks == [], (
            "a proposal already accepted must not be re-adjudicated — "
            "a later 'decline' would contradict the Accept already sent"
        )
        assert "Reject" not in _types_in_outbox(dl)

    def test_guard_survives_a_missing_report_uri(self, dl):
        """A stored ``Accept`` answers the guard even with no report URI.

        The guard prefers an indexed case lookup, which needs ``report_id``; the
        ``Accept`` scan is what covers ``report_id=None``. Without that half, a
        redelivery could be Rejected after its Accept had gone out.
        """
        _run_tree(dl)
        assert "Accept" in _types_in_outbox(dl)

        ticks: list[str] = []
        _run_tree(dl, report_id=None, call_out=_declining_bundle(ticks))

        assert ticks == []
        assert "Reject" not in _types_in_outbox(dl)
        assert (
            dl.read(CaseProposalDeclineRecord.build_id(_PROPOSAL_URI)) is None
        )
        # The accept arm finds the case through the stored Accept, so a
        # redelivery that names no report creates no second case (#4650).
        assert len(_cases(dl)) == 1

    def test_in_flight_retry_marker_short_circuits_before_the_decision(
        self, dl
    ):
        """The marker branch precedes the decline arm, so neither fires."""
        dl.save(
            PendingCreateCaseActivity(
                id_=PendingCreateCaseActivity.build_id(_PROPOSAL_URI),
                proposal_id=_PROPOSAL_URI,
                case_actor_id=_CASE_ACTOR_URI,
                owner_uri=_VENDOR_URI,
                create_activity_payload={},
            )
        )

        ticks: list[str] = []
        status = _run_tree(dl, call_out=_declining_bundle(ticks))

        assert status == Status.SUCCESS
        assert ticks == []
        assert _types_in_outbox(dl) == []


# ---------------------------------------------------------------------------
# Bundle wiring (BT-23-003, BT-23-008, BT-23-009)
# ---------------------------------------------------------------------------


@pytest.mark.spec("BT-23-008")
def test_deterministic_singleton_lives_in_core():
    """BT-23-008: the dataclass and DETERMINISTIC default are core concerns."""
    assert (
        CASE_PROPOSAL_DETERMINISTIC.__class__.__module__
        == "vultron.core.behaviors.call_out.bundles.case_proposal"
    )


@pytest.mark.spec("BT-23-009")
def test_stochastic_singleton_lives_in_the_simulation_layer():
    """BT-23-009: the probabilistic backend stays out of core."""
    from vultron.demo.fuzzer.bundles.case_proposal import (
        CASE_PROPOSAL_STOCHASTIC,
    )
    from vultron.demo.fuzzer.case_management import EvaluateCaseProposal

    node = CASE_PROPOSAL_STOCHASTIC.evaluate_proposal_factory(
        "EvaluateCaseProposal"
    )
    # The bundle base guards every factory (BT-18-011), so unwrap the decorator.
    inner = getattr(node, "decorated", node)
    assert isinstance(inner, EvaluateCaseProposal)


@pytest.mark.spec("BT-18-001")
def test_stochastic_backend_declares_its_blackboard_output():
    """BT-18-001: an Evaluator declares the keys it writes on SUCCESS."""
    from vultron.demo.fuzzer.case_management import EvaluateCaseProposal

    assert EvaluateCaseProposal.output_keys == {
        "evaluate_case_proposal_verdict": str
    }


@pytest.mark.spec("CP-06-004")
class TestDeclineReasonReachesTheProposer:
    """The reason travels on the decline record, not as a call argument.

    A `Reject` re-emitted on a later delivery must carry the reason the original
    decision gave, which is why the node reads the record rather than being
    constructed with the text. Nothing writes a reason yet — a call-out point
    signals refusal by returning FAILURE and BT-18 defines outputs only for the
    SUCCESS case — so these tests exercise the read path a future backend needs
    (see #3399).
    """

    def test_reject_carries_no_summary_when_no_reason_was_recorded(self, dl):
        """A decline is never blocked on having an explanation to give."""
        _run_tree(dl, call_out=_declining_bundle([]))

        (reject,) = _outbox_activities(dl)
        assert getattr(reject, "summary", None) is None

    def test_reject_carries_the_recorded_reason(self, dl):
        """A pre-recorded decline reason reaches the wire as the summary."""
        dl.save(
            CaseProposalDeclineRecord(
                proposal_id=_PROPOSAL_URI,
                case_actor_id=_CASE_ACTOR_URI,
                proposer_uri=_VENDOR_URI,
                reason="proposing actor is not on the admission list",
            )
        )

        # The record already exists, so the resend arm owes the Reject.
        status = _run_tree(dl, call_out=_declining_bundle([]))

        assert status == Status.SUCCESS
        (reject,) = _outbox_activities(dl)
        assert reject.summary == "proposing actor is not on the admission list"


# ---------------------------------------------------------------------------
# A store that cannot answer must fail the tree, never admit
# ---------------------------------------------------------------------------


class _AnsweredGuardFaults(SqliteDataLayer):
    """Store whose "was this already answered?" reads both fault."""

    def list_objects(self, type_key):  # type: ignore[override]
        if type_key == "Accept":
            raise RuntimeError("database is locked")
        return super().list_objects(type_key)

    def find_case_by_report_id(self, report_id):  # type: ignore[override]
        raise RuntimeError("database is locked")


class _OutboxAppendFaults(SqliteDataLayer):
    """Store that persists an activity but cannot enqueue it."""

    fail = True

    def outbox_append(self, activity_id):  # type: ignore[override]
        if self.fail:
            raise RuntimeError("queue write fault")
        return super().outbox_append(activity_id)


class _AcceptWriteFaults(SqliteDataLayer):
    """Store that fails only the ``Accept`` activity write."""

    fail = True

    def create(self, obj):  # type: ignore[override]
        if self.fail and str(getattr(obj, "type_", "")) == "Accept":
            raise ValueError("simulated Accept write fault")
        return super().create(obj)


def _fault_store(cls):
    _dl = cls("sqlite:///:memory:", actor_id=_CASE_ACTOR_URI)
    _dl.clear_all()
    return _dl


@pytest.mark.spec("CP-05-002")
class TestAnUnanswerableStoreFailsRatherThanAdmits:
    """In a Selector, both directions of "I could not tell" mean admit.

    A guard in a refusal arm that swallows its store error has no safe status to
    return: FAILURE runs the accept arm, and SUCCESS skips the refusal arm and
    runs it too. Letting the exception reach ``BTBridge`` is the only safe answer.
    """

    def test_unreadable_answered_guard_does_not_admit(self):
        dl = _fault_store(_AnsweredGuardFaults)
        try:
            ticks: list[str] = []
            status = _run_tree(dl, call_out=_declining_bundle(ticks))

            assert status == Status.FAILURE
            assert _cases(dl) == [], "an unanswerable store must not admit"
            assert _types_in_outbox(dl) == []
        finally:
            dl.clear_all()
            dl.close()

    def test_unrecordable_decline_does_not_admit(self, dl, monkeypatch):
        """If the refusal cannot be made terminal, the tree fails.

        The write that cannot happen is ``RecordProposalDeclineNode``'s, in
        ``vultron.core.behaviors.case.nodes.proposal_admission_actions``.
        """

        def _boom(self, obj):
            if str(getattr(obj, "type_", "")) == "CaseProposalDeclineRecord":
                raise ValueError("simulated decline-record write fault")
            return SqliteDataLayer.create(self, obj)

        monkeypatch.setattr(type(dl), "create", _boom, raising=False)

        status = _run_tree(dl, call_out=_declining_bundle([]))

        assert status == Status.FAILURE
        assert _cases(dl) == []
        assert "Accept" not in _types_in_outbox(dl)


@pytest.mark.spec("CP-05-004")
class TestQueuedNotMerelyStored:
    """A Reject that was persisted but never enqueued is still owed.

    The adapter persists the activity and *then* enqueues it, so a queue fault
    leaves a stored ``Reject`` nobody will deliver. A store-only check reads that
    as "already told them" and reports SUCCESS forever with an empty outbox.
    """

    def test_a_reject_that_was_never_enqueued_is_re_emitted(self):
        dl = _fault_store(_OutboxAppendFaults)
        try:
            first = _run_tree(dl, call_out=_declining_bundle([]))
            assert first == Status.FAILURE
            assert _types_in_outbox(dl) == [], "the queue write faulted"
            assert (
                dl.read(CaseProposalDeclineRecord.build_id(_PROPOSAL_URI))
                is not None
            ), "the decision must still be recorded"

            dl.fail = False
            status = _run_tree(dl, call_out=_declining_bundle([]))

            assert status == Status.SUCCESS
            assert _types_in_outbox(dl) == ["Reject"]
            assert _cases(dl) == []
        finally:
            dl.clear_all()
            dl.close()


@pytest.mark.spec("CLP-10-009")
class TestAHalfBuiltCaseIsNotRejected:
    """``main_flow`` creates the case before it emits the ``Accept``.

    A delivery that fails in between leaves a case with no stored ``Accept``. An
    Accept-only "already answered" guard cannot see that, and a later declining
    delivery would Reject a case this store had already half-built — then block
    the accept arm forever, leaving the case permanently unfinishable.
    """

    def test_declining_redelivery_completes_the_case_instead(self):
        dl = _fault_store(_AcceptWriteFaults)
        try:
            assert _run_tree(dl, call_out=_admitting_bundle([])) == (
                Status.FAILURE
            )
            assert len(_cases(dl)) == 1, (
                "the case was created before the fault"
            )
            assert _types_in_outbox(dl) == []

            dl.fail = False
            status = _run_tree(dl, call_out=_declining_bundle([]))

            assert status == Status.SUCCESS
            assert "Reject" not in _types_in_outbox(dl), (
                "a case that already exists has been answered; refusing it now "
                "would strand it with no Accept and no way to get one"
            )
            assert "Accept" in _types_in_outbox(dl)
            assert (
                dl.read(CaseProposalDeclineRecord.build_id(_PROPOSAL_URI))
                is None
            )
            assert len(_cases(dl)) == 1
        finally:
            dl.clear_all()
            dl.close()


@pytest.mark.spec("CP-05-002")
@pytest.mark.spec("CP-05-006")
class TestTheGateIsKeyedOnTheProposalNotTheReport:
    """A sender must not be able to skip admission by naming a known report.

    ``report_id`` reaches this tree as ``request.inner_object_id`` — the id of
    the report the *sender* embedded in its own proposal. So it is sender-chosen,
    and two proposals may name one report.

    That makes a report-keyed "has this been answered?" guard worse than useless:
    it answers SUCCESS for a proposal the service has never adjudicated, which
    short-circuits the decline arm *before* the admission call-out point is
    ticked and admits the proposal through the duplicate-reuse path. An actor
    that knows one report id this service already holds a case for could then
    obtain CASE_OWNER on that case while the deployment's admission policy was
    never consulted. A gate a sender can arrange to skip is not a gate.
    """

    def test_a_second_proposal_on_the_same_report_is_still_adjudicated(self):
        second_proposal_uri = "https://evil.example.org/proposals/p-002"
        second_proposer_uri = "https://evil.example.org/actors/attacker"

        _dl = SqliteDataLayer("sqlite:///:memory:", actor_id=_CASE_ACTOR_URI)
        _dl.clear_all()
        try:
            # First proposal is admitted normally: a case now exists for
            # _REPORT_URI, which is the state the bypass fed on.
            assert _run_tree(_dl, call_out=_admitting_bundle([])) == (
                Status.SUCCESS
            )
            assert len(_cases(_dl)) == 1
            # Drain the first admission's mail: its Create and Accept, plus
            # the Announce(CaseLedgerEntry) fan-out of every entry it
            # committed (SYNC-02-003).
            while _dl.outbox_list():
                _dl.outbox_pop()

            # A different proposal, from a different actor, naming the same
            # report. The deployment's policy refuses it.
            proposal = as_CaseProposal(
                id_=second_proposal_uri,
                attributed_to=second_proposer_uri,
                object_=as_VulnerabilityReport(
                    id_=_REPORT_URI, attributed_to=_REPORTER_URI
                ),
                target=_CASE_ACTOR_URI,
            )
            activity = as_Create(
                actor=VultronOrganization(id_=second_proposer_uri),
                object_=proposal,
                to=[_CASE_ACTOR_URI],
            )
            event = extract_event(activity).model_copy(
                update={"receiving_actor_id": _CASE_ACTOR_URI}
            )
            ticks: list[str] = []
            tree = create_case_proposal_received_tree(
                report_id=_REPORT_URI,
                proposal_id=second_proposal_uri,
                proposer_uri=second_proposer_uri,
                proposal_dict=proposal.model_dump(
                    by_alias=True, serialize_as_any=True
                ),
                inline_report=VulnerabilityReport(
                    id_=_REPORT_URI, attributed_to=_REPORTER_URI
                ),
                call_out=_declining_bundle(ticks),
            )
            status = (
                BTBridge(
                    datalayer=_dl,
                    wire_render_port=As2WireRenderAdapter(),
                    trigger_activity=TriggerActivityAdapter(_dl),
                    sync_port=SyncActivityAdapter(_dl),
                )
                .execute_with_setup(
                    tree=tree,
                    actor_id=_CASE_ACTOR_URI,
                    activity=event,
                    owner_profile=activity.actor,
                )
                .status
            )

            assert ticks == ["EvaluateCaseProposal"], (
                "the admission policy MUST be consulted: this proposal has "
                "never been adjudicated, and an existing case for a "
                "sender-supplied report id is not an answer to it"
            )
            assert status == Status.SUCCESS
            assert _types_in_outbox(_dl) == ["Reject"], (
                "the refusal must reach the wire, addressed to the actor that "
                "proposed"
            )
            assert (
                _dl.read(
                    CaseProposalDeclineRecord.build_id(second_proposal_uri)
                )
                is not None
            )
            assert len(_cases(_dl)) == 1, (
                "no second case, and the first is untouched"
            )
            participants = [
                p
                for p in _dl.list_objects("CaseParticipant")
                if second_proposer_uri in str(getattr(p, "actor_id", ""))
            ]
            assert participants == [], (
                "a refused actor must not end up on the roster of the case it "
                "was refused from"
            )
        finally:
            _dl.clear_all()
            _dl.close()


# ---------------------------------------------------------------------------
# A new proposal id for an accepted report is a new request (CP-05-008)
# ---------------------------------------------------------------------------


@pytest.mark.spec("CP-05-008")
def test_second_proposer_for_an_accepted_report_gets_its_own_case(dl):
    """Reuse is keyed on (report, proposer), never on the report alone.

    The first proposer's case stays its own: the second proposer is admitted
    through the normal gate, gets a separate case it owns, and is not added to
    the first proposer's roster.
    """
    second_proposal_uri = "https://other.example.org/proposals/p-002"
    second_proposer_uri = "https://other.example.org/actors/other-vendor"

    _run_tree(dl)  # the first proposer's proposal is accepted
    first_case = _cases(dl)[0]

    status = _run_tree(
        dl,
        proposal_uri=second_proposal_uri,
        proposer_uri=second_proposer_uri,
    )

    assert status == Status.SUCCESS
    cases = _cases(dl)
    assert len(cases) == 2, "each proposer gets a case of its own"
    owners = {str(c.attributed_to) for c in cases}
    assert owners == {_VENDOR_URI, second_proposer_uri}
    on_first_roster = [
        p
        for p in dl.list_objects("CaseParticipant")
        if second_proposer_uri in str(getattr(p, "actor_id", ""))
        and str(getattr(p, "context", "")) == str(first_case.id_)
    ]
    assert on_first_roster == [], (
        "the second proposer must not join the first proposer's case"
    )


@pytest.mark.spec("CP-05-008")
def test_new_proposal_id_from_the_owner_reuses_its_case(dl):
    """The owner's second proposal for its own report is answered, not re-created.

    It gets its own ``Accept`` (a new proposal is a new request) whose result
    names the existing case; no second case is created, and committing the
    canonical ledger entries again does not raise "log entry already exists".
    """
    second_proposal_uri = "https://vendor.example.org/proposals/p-002"

    assert _run_tree(dl) == Status.SUCCESS
    (first_case,) = _cases(dl)
    ledger_before = len(list(dl.list_objects("CaseLedgerEntry")))
    types_before = _types_in_outbox(dl)

    status = _run_tree(dl, proposal_uri=second_proposal_uri)

    assert status == Status.SUCCESS
    assert [c.id_ for c in _cases(dl)] == [first_case.id_], (
        "the owner's case is reused, never duplicated"
    )
    all_accepts = list(dl.list_objects("Accept"))
    assert len(all_accepts) == 2, "each proposal is answered by its own Accept"
    assert len({a.id_ for a in all_accepts}) == 2
    assert {str(getattr(a.result, "id_", a.result)) for a in all_accepts} == {
        str(first_case.id_)
    }, "both Accepts name the one case"
    creates = [
        c
        for c in dl.list_objects("Create")
        if str(first_case.id_) in str(getattr(c, "object_", ""))
    ]
    assert len(creates) == 1, "no second Create(VulnerabilityCase)"
    # The native ledger commits are skipped, not re-run: a re-run reuses each
    # recorded entry but fans it out to every recipient a second time.
    assert len(list(dl.list_objects("CaseLedgerEntry"))) == ledger_before
    new_types = _types_in_outbox(dl)[len(types_before) :]
    assert new_types == ["Accept"], (
        "the new proposal is answered with its Accept and nothing else"
    )


@pytest.mark.spec("CP-05-008")
def test_an_unannounced_owner_case_is_completed_not_skipped(dl):
    """A case no ``Create`` has announced yet still gets its ``Create``.

    The reuse path skips the announcement only for a case already announced; a
    half-built case left by a failed earlier delivery must still be finished.
    """
    assert _run_tree(dl) == Status.SUCCESS
    (case,) = _cases(dl)
    for create in list(dl.list_objects("Create")):
        if str(getattr(create, "context", "")) == str(case.id_):
            dl.delete("Create", create.id_)
    assert not case_is_announced(dl, str(case.id_))

    status = _run_tree(
        dl, proposal_uri="https://vendor.example.org/proposals/p-002"
    )

    assert status == Status.SUCCESS
    assert case_is_announced(dl, str(case.id_))
    assert len(_cases(dl)) == 1


@pytest.mark.spec("CP-05-008")
@pytest.mark.spec("CBT-06-002")
def test_second_proposer_re_proposing_reuses_its_own_case(dl):
    """The report-only fast path returns the first proposer's case; the second
    proposer's own case is still found, not duplicated.
    """
    second_proposer_uri = "https://other.example.org/actors/other-vendor"

    assert _run_tree(dl) == Status.SUCCESS
    assert (
        _run_tree(
            dl,
            proposal_uri="https://other.example.org/proposals/p-002",
            proposer_uri=second_proposer_uri,
        )
        == Status.SUCCESS
    )
    assert len(_cases(dl)) == 2

    status = _run_tree(
        dl,
        proposal_uri="https://other.example.org/proposals/p-003",
        proposer_uri=second_proposer_uri,
    )

    assert status == Status.SUCCESS
    cases = _cases(dl)
    assert len(cases) == 2, "the second proposer's own case is reused"
    assert sorted(str(c.attributed_to) for c in cases) == sorted(
        [_VENDOR_URI, second_proposer_uri]
    )


# ---------------------------------------------------------------------------
# A proposal that resolves to a fully closed case is declined
# (CP-05-006, CP-05-008, CM-23-013)
# ---------------------------------------------------------------------------

_SECOND_PROPOSAL_URI = "https://vendor.example.org/proposals/p-002"
_OTHER_PROPOSER_URI = "https://other.example.org/actors/other-vendor"
_OTHER_PROPOSAL_URI = "https://other.example.org/proposals/p-001"


def _drain_outbox(dl) -> None:
    """Deliver everything queued, so the next assertion sees only new sends."""
    while dl.outbox_pop() is not None:
        pass


def _accepted_then_closed(dl) -> VulnerabilityCase:
    """Accept the first proposal, deliver its answers, then close its case."""
    assert _run_tree(dl) == Status.SUCCESS
    (case,) = _cases(dl)
    assert isinstance(case, VulnerabilityCase)
    _drain_outbox(dl)
    commit_case_fully_closed(dl, str(case.id_), _VENDOR_URI)
    return case


def _case_state(dl) -> list[str]:
    """Every case and participant row, serialised, to detect any write."""
    rows = list(dl.list_objects("VulnerabilityCase")) + list(
        dl.list_objects("CaseParticipant")
    )
    return sorted(row.model_dump_json() for row in rows)


def _ledger_count(dl) -> int:
    return len(list(dl.list_objects("CaseLedgerEntry")))


def _proposal_id_of(activity) -> str:
    return str(getattr(activity.object_, "id_", activity.object_))


def _decline_record(dl, proposal_uri: str) -> CaseProposalDeclineRecord:
    record = dl.read(CaseProposalDeclineRecord.build_id(proposal_uri))
    assert isinstance(record, CaseProposalDeclineRecord)
    return record


@pytest.mark.spec("CP-05-008")
@pytest.mark.spec("CM-23-013")
@pytest.mark.spec("CP-05-004")
class TestTheOwnersNewProposalForAClosedCaseIsDeclined:
    """A new proposal id from the owner of a fully closed case is declined.

    Before #4468 the accept arm reused the closed case and sent an ``Accept``
    for it.
    """

    def test_it_is_answered_with_a_reject_and_nothing_else(self, dl):
        _accepted_then_closed(dl)

        status = _run_tree(dl, proposal_uri=_SECOND_PROPOSAL_URI)

        assert status == Status.SUCCESS
        assert _types_in_outbox(dl) == ["Reject"], (
            "a closed case's owner gets a Reject: no Accept, no Create"
        )
        (reject,) = _outbox_activities(dl)
        assert _proposal_id_of(reject) == _SECOND_PROPOSAL_URI
        assert not [
            a
            for a in dl.list_objects("Accept")
            if activity_names_proposal(a, _SECOND_PROPOSAL_URI)
        ], "no Accept is even stored for the new proposal"

    def test_the_reject_carries_the_proposal_inline_and_a_reason(self, dl):
        _accepted_then_closed(dl)

        _run_tree(dl, proposal_uri=_SECOND_PROPOSAL_URI)

        (reject,) = _outbox_activities(dl)
        assert isinstance(reject.object_, as_CaseProposal)
        assert reject.summary == CLOSED_CASE_DECLINE_REASON

    def test_nothing_is_written_for_the_case(self, dl):
        _accepted_then_closed(dl)
        ledger_before = _ledger_count(dl)
        state_before = _case_state(dl)

        _run_tree(dl, proposal_uri=_SECOND_PROPOSAL_URI)

        assert _ledger_count(dl) == ledger_before, (
            "no CaseLedgerEntry for the closed case (CM-23-013)"
        )
        assert _case_state(dl) == state_before, (
            "no new case and no case or participant change"
        )
        assert (
            dl.read(PendingCreateCaseActivity.build_id(_SECOND_PROPOSAL_URI))
            is None
        )

    def test_the_decline_is_recorded_on_the_proposal(self, dl):
        _accepted_then_closed(dl)

        _run_tree(dl, proposal_uri=_SECOND_PROPOSAL_URI)

        record = _decline_record(dl, _SECOND_PROPOSAL_URI)
        assert record.reject_activity_id is not None
        assert record.reason == CLOSED_CASE_DECLINE_REASON
        assert (
            dl.read(CaseProposalAdmissionRecord.build_id(_SECOND_PROPOSAL_URI))
            is None
        ), "the accept path never began"

    def test_the_admission_policy_is_not_consulted(self, dl):
        """The case's closure decides; the admission backend is not ticked."""
        _accepted_then_closed(dl)
        ticks: list[str] = []

        _run_tree(
            dl,
            proposal_uri=_SECOND_PROPOSAL_URI,
            call_out=_admitting_bundle(ticks),
        )

        assert ticks == []


@pytest.mark.spec("CP-05-006")
@pytest.mark.spec("CM-23-013")
@pytest.mark.spec("ASK-08-001")
class TestARedeliveryAfterCloseIsDeclined:
    """The original proposal, accepted before close, is declined on redelivery.

    The ``Reject`` declines only the redelivery; the stored ``Accept`` stands
    (CP-05-005) and is not re-sent.
    """

    def test_it_is_answered_with_a_reject_not_the_stored_accept(self, dl):
        _accepted_then_closed(dl)
        (stored_accept,) = list(dl.list_objects("Accept"))

        status = _run_tree(dl)

        assert status == Status.SUCCESS
        assert _types_in_outbox(dl) == ["Reject"]
        (reject,) = _outbox_activities(dl)
        assert _proposal_id_of(reject) == _PROPOSAL_URI
        assert [a.id_ for a in dl.list_objects("Accept")] == [
            stored_accept.id_
        ], "the stored Accept is kept, not revoked or re-minted"

    def test_nothing_is_written_for_the_case(self, dl):
        _accepted_then_closed(dl)
        ledger_before = _ledger_count(dl)
        state_before = _case_state(dl)

        _run_tree(dl)

        assert _ledger_count(dl) == ledger_before
        assert _case_state(dl) == state_before

    def test_a_second_redelivery_is_answered_from_the_record(self, dl):
        """The decision is not re-made and the Reject is not sent twice."""
        _accepted_then_closed(dl)
        _run_tree(dl)
        first = _decline_record(dl, _PROPOSAL_URI)
        _drain_outbox(dl)
        ledger_before = _ledger_count(dl)

        status = _run_tree(dl)

        assert status == Status.SUCCESS
        assert _types_in_outbox(dl) == [], (
            "the Reject already went out; the record answers the redelivery"
        )
        assert _decline_record(dl, _PROPOSAL_URI) == first
        assert _ledger_count(dl) == ledger_before

    def test_a_former_owner_is_declined_after_an_ownership_transfer(self, dl):
        """The proposal's own Accept names the case, not the current owner.

        After a transfer the owner lookup finds nothing for the former owner,
        so without the Accept lookup the redelivery would build a new case.
        """
        case = _accepted_then_closed(dl)
        dl.save(case.model_copy(update={"attributed_to": _OTHER_PROPOSER_URI}))

        status = _run_tree(dl)

        assert status == Status.SUCCESS
        assert _types_in_outbox(dl) == ["Reject"]
        assert [c.id_ for c in _cases(dl)] == [case.id_]


@pytest.mark.spec("CP-05-008")
@pytest.mark.spec("CM-23-013")
class TestTheClosedCaseCheckFailsTowardRefusal:
    """The closure check sits on a refusal arm, so it fails the tree, never admits.

    See ``notes/bt-pitfalls.md`` § "A Refusal Arm in a Selector Fails Toward
    'Admit'".
    """

    def test_an_unreadable_ledger_fails_the_tree(self, dl, monkeypatch):
        case = _accepted_then_closed(dl)
        ledger_before = _ledger_count(dl)
        real_list = SqliteDataLayer.list_objects

        def _locked(self, type_key):
            if type_key == "CaseLedgerEntry":
                raise RuntimeError("database is locked")
            return real_list(self, type_key)

        monkeypatch.setattr(type(dl), "list_objects", _locked, raising=False)

        status = _run_tree(dl, proposal_uri=_SECOND_PROPOSAL_URI)

        monkeypatch.undo()
        assert status == Status.FAILURE
        assert _types_in_outbox(dl) == [], "no Accept, no Reject"
        assert [c.id_ for c in _cases(dl)] == [case.id_]
        assert _ledger_count(dl) == ledger_before
        assert (
            dl.read(CaseProposalAdmissionRecord.build_id(_SECOND_PROPOSAL_URI))
            is None
        ), "the accept arm never began"

    def test_a_missing_datalayer_raises_rather_than_answering(self):
        """With no store the node cannot tell, so neither status is safe."""
        node = CheckProposalCaseFullyClosedNode(
            proposal_id=_PROPOSAL_URI,
            proposer_uri=_VENDOR_URI,
            report_id=_REPORT_URI,
        )

        with pytest.raises(VultronWiringError):
            node.update()

    @pytest.mark.parametrize(
        "broken_emit",
        [{"with_proposal_dict": False}, {"with_trigger_port": False}],
        ids=["no-wire-proposal", "no-trigger-port"],
    )
    def test_a_failed_reject_does_not_reuse_the_closed_case(
        self, dl, broken_emit
    ):
        _accepted_then_closed(dl)
        ledger_before = _ledger_count(dl)
        state_before = _case_state(dl)

        status = _run_tree(
            dl, proposal_uri=_SECOND_PROPOSAL_URI, **broken_emit
        )

        assert status == Status.FAILURE
        assert _types_in_outbox(dl) == []
        assert _ledger_count(dl) == ledger_before
        assert _case_state(dl) == state_before
        assert (
            _decline_record(dl, _SECOND_PROPOSAL_URI).reject_activity_id
            is None
        )

    def test_the_owed_reject_is_sent_on_the_next_delivery(self, dl):
        _accepted_then_closed(dl)
        _run_tree(
            dl, proposal_uri=_SECOND_PROPOSAL_URI, with_trigger_port=False
        )

        status = _run_tree(dl, proposal_uri=_SECOND_PROPOSAL_URI)

        assert status == Status.SUCCESS
        assert _types_in_outbox(dl) == ["Reject"]


@pytest.mark.spec("CP-05-008")
def test_another_proposer_for_a_closed_cases_report_gets_its_own_case(dl):
    """Another party's closed case does not decline this proposer (CP-05-008)."""
    closed = _accepted_then_closed(dl)
    closed_ledger = committed_event_types(dl, str(closed.id_))

    status = _run_tree(
        dl,
        proposal_uri=_OTHER_PROPOSAL_URI,
        proposer_uri=_OTHER_PROPOSER_URI,
    )

    assert status == Status.SUCCESS
    assert "Accept" in _types_in_outbox(dl)
    assert "Reject" not in _types_in_outbox(dl)
    owners = sorted(str(c.attributed_to) for c in _cases(dl))
    assert owners == sorted([_VENDOR_URI, _OTHER_PROPOSER_URI])
    assert committed_event_types(dl, str(closed.id_)) == closed_ledger, (
        "the closed case gains nothing"
    )


@pytest.mark.spec("CP-05-006")
@pytest.mark.spec("CM-23-013")
def test_a_legacy_redelivery_with_no_report_id_is_declined(dl):
    """With no report id and no admission record, the Accept scan still runs.

    A store written before the admission record existed holds only the
    ``Accept``, and a redelivery that names no report gives the owner lookup
    nothing to go on.  The ``Accept``'s ``result`` is then the only way to find
    the closed case.
    """
    case = _accepted_then_closed(dl)
    assert dl.delete(
        "CaseProposalAdmissionRecord",
        CaseProposalAdmissionRecord.build_id(_PROPOSAL_URI),
    )
    ledger_before = _ledger_count(dl)

    status = _run_tree(dl, report_id=None)

    assert status == Status.SUCCESS
    assert _types_in_outbox(dl) == ["Reject"]
    assert [c.id_ for c in _cases(dl)] == [case.id_]
    assert _ledger_count(dl) == ledger_before


@pytest.mark.spec("CP-05-008")
def test_the_accept_scan_is_skipped_when_the_owners_case_is_closed(
    dl, monkeypatch
):
    """The owner's closed case decides; the ``Accept`` rows are not scanned."""
    _accepted_then_closed(dl)

    def _no_scan(*_args: object, **_kwargs: object) -> None:
        raise AssertionError("the Accept scan ran after the owner's case")

    monkeypatch.setattr(proposal_case_lookup, "accepted_case_id", _no_scan)

    status = _run_tree(dl, proposal_uri=_SECOND_PROPOSAL_URI)

    assert status == Status.SUCCESS
    assert _types_in_outbox(dl) == ["Reject"]


class _AcceptStore:
    """A store stub that holds one ``Accept`` for the proposal."""

    def __init__(self, result: object) -> None:
        self._accept = SimpleNamespace(
            type_="Accept", object_=_PROPOSAL_URI, result=result
        )

    def list_objects(self, type_key: str) -> list[object]:
        return [self._accept] if type_key == "Accept" else []


_CASE_ID = "https://case-actor.example.org/cases/c-001"


@pytest.mark.spec("CP-05-006")
@pytest.mark.parametrize(
    ("result", "expected"),
    [
        (_CASE_ID, _CASE_ID),
        (SimpleNamespace(id_=_CASE_ID), _CASE_ID),
        ({"id": _CASE_ID}, _CASE_ID),
        (None, None),
        ("", None),
        ({"type": "VulnerabilityCase"}, None),
        (SimpleNamespace(id_=None), None),
    ],
    ids=[
        "bare-id",
        "object",
        "dict",
        "no-result",
        "empty-id",
        "dict-without-id",
        "object-without-id",
    ],
)
def test_accepted_case_id_reads_every_result_shape(result, expected):
    store = cast(CasePersistence, _AcceptStore(result))

    assert accepted_case_id(store, _PROPOSAL_URI) == expected


def test_accepted_case_id_is_none_without_a_stored_accept():
    store = cast(CasePersistence, _AcceptStore(_CASE_ID))

    assert accepted_case_id(store, _SECOND_PROPOSAL_URI) is None


@pytest.mark.parametrize(
    ("report_id", "case_exists", "expected"),
    [
        (None, False, True),
        (_REPORT_URI, False, False),
        (_REPORT_URI, True, True),
    ],
    ids=["no-report-id", "no-case-for-report", "case-for-report"],
)
def test_accept_scan_can_match_is_a_negative_prefilter(
    report_id, case_exists, expected
):
    found = SimpleNamespace(id_=_CASE_ID) if case_exists else None
    store = cast(
        CasePersistence,
        SimpleNamespace(find_case_by_report_id=lambda _report_id: found),
    )

    assert accept_scan_can_match(store, report_id) is expected


# ---------------------------------------------------------------------------
# A former owner's redelivery reuses the accepted case (CP-05-006, #4650)
# ---------------------------------------------------------------------------


def _participants_of(dl, case_id: str, actor_uri: str) -> list:
    return [
        p
        for p in dl.list_objects("CaseParticipant")
        if str(getattr(p, "attributed_to", "")) == actor_uri
        and str(getattr(p, "context", "")) == case_id
    ]


def _accepted_then_transferred(dl) -> VulnerabilityCase:
    """Accept the first proposal, deliver its answers, then move ownership.

    The transfer is applied as CM-21-002/003 leave it: the case is attributed
    to the new owner, and the former owner stays a participant (CM-21-009)
    without ``CASE_OWNER``.
    """
    assert _run_tree(dl) == Status.SUCCESS
    (case,) = _cases(dl)
    assert isinstance(case, VulnerabilityCase)
    _drain_outbox(dl)
    for participant in _participants_of(dl, str(case.id_), _VENDOR_URI):
        dl.save(
            participant.model_copy(
                update={
                    "case_roles": [
                        r
                        for r in participant.case_roles
                        if r != CVDRole.CASE_OWNER
                    ]
                }
            )
        )
    transferred = case.model_copy(
        update={"attributed_to": _OTHER_PROPOSER_URI}
    )
    dl.save(transferred)
    return transferred


@pytest.mark.spec("CP-05-006")
@pytest.mark.spec("ASK-08-001")
@pytest.mark.spec("ASK-08-002")
@pytest.mark.spec("CM-21-001")
class TestAFormerOwnersRedeliveryReusesTheAcceptedCase:
    """The original proposal, redelivered after an ownership transfer.

    The owner lookup finds nothing for the former owner, so the case is found
    through the proposal's stored ``Accept`` instead.  Before #4650 the
    redelivery created a second case and then failed.
    """

    def test_no_second_case_is_created(self, dl):
        case = _accepted_then_transferred(dl)

        status = _run_tree(dl)

        assert status == Status.SUCCESS
        assert [c.id_ for c in _cases(dl)] == [case.id_], (
            "the redelivery must not create a second case (CP-05-006)"
        )
        (stored,) = _cases(dl)
        assert str(stored.attributed_to) == _OTHER_PROPOSER_URI

    def test_it_is_answered_with_the_stored_accept_unchanged(self, dl):
        case = _accepted_then_transferred(dl)
        (stored_accept,) = list(dl.list_objects("Accept"))
        sealed_before = read_sealed_body_dict(dl, str(stored_accept.id_))
        assert sealed_before is not None

        _run_tree(dl)

        assert _types_in_outbox(dl) == ["Accept"], (
            "the stored Accept is re-sent, and nothing else"
        )
        (resent,) = _outbox_activities(dl)
        assert resent.id_ == stored_accept.id_
        assert [a.id_ for a in dl.list_objects("Accept")] == [
            stored_accept.id_
        ], "no second Accept is minted"
        assert read_sealed_body_dict(dl, str(resent.id_)) == sealed_before, (
            "the outbound body is the original, unchanged (ASK-08-001)"
        )
        assert accepted_case_id(dl, _PROPOSAL_URI) == str(case.id_)

    def test_nothing_is_written_for_the_case(self, dl):
        _accepted_then_transferred(dl)
        ledger_before = _ledger_count(dl)
        state_before = _case_state(dl)

        _run_tree(dl)

        assert _ledger_count(dl) == ledger_before
        assert _case_state(dl) == state_before, (
            "the former owner is not made CASE_OWNER again (CM-21-001)"
        )

    def test_a_former_owner_off_the_roster_is_not_made_case_owner(self, dl):
        """Native initialization adds a CASE_OWNER only for the case's owner.

        CM-21-009 keeps the former owner on the roster, so this state is not
        reached in practice; it pins that the owner step is keyed on the
        case's owner, not on the proposer (CM-21-001, CP-09-001).
        """
        case = _accepted_then_transferred(dl)
        index = dict(case.actor_participant_index)
        index.pop(_VENDOR_URI)
        dl.save(case.model_copy(update={"actor_participant_index": index}))
        rows_before = len(_participants_of(dl, str(case.id_), _VENDOR_URI))

        status = _run_tree(dl)

        assert status == Status.SUCCESS
        assert [c.id_ for c in _cases(dl)] == [case.id_]
        (stored,) = _cases(dl)
        assert _VENDOR_URI not in stored.actor_participant_index
        assert (
            len(_participants_of(dl, str(case.id_), _VENDOR_URI))
            == rows_before
        ), "no new participant is created for the former owner"
