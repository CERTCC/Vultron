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
  inline (CP-05-004, AKM-03-001).
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

import py_trees
import pytest
from py_trees.common import Status

from vultron.adapters.driven.datalayer_sqlite import SqliteDataLayer
from vultron.adapters.driven.trigger_activity_adapter import (
    TriggerActivityAdapter,
)
from vultron.adapters.driven.wire_render.as2 import As2WireRenderAdapter
from vultron.core.behaviors.bridge import BTBridge
from vultron.core.behaviors.call_out.bundles.case_proposal import (
    CASE_PROPOSAL_DETERMINISTIC,
    CaseProposalCallOutBundle,
)
from vultron.core.behaviors.case.case_proposal_received_tree import (
    create_case_proposal_received_tree,
)
from vultron.core.models.case import VulnerabilityCase
from vultron.core.models.case_proposal_decline import (
    CaseProposalDeclineRecord,
)
from vultron.core.models.pending_create_case_activity import (
    PendingCreateCaseActivity,
)
from vultron.core.models.report import VulnerabilityReport
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


def _proposal() -> as_CaseProposal:
    """A proposal carrying its report inline, as CP-01-004 requires."""
    return as_CaseProposal(
        id_=_PROPOSAL_URI,
        attributed_to=_VENDOR_URI,
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
) -> Status:
    """Build and run the received-side tree the way the use case does.

    ``with_proposal_dict`` and ``with_trigger_port`` model the two ways the
    ``Reject`` emit can fail: a replay path that carries no wire proposal, and a
    caller that injected no ``TriggerActivityPort``.
    """
    proposal = _proposal()
    activity = as_Create(
        actor=_VENDOR_URI, object_=proposal, to=[_CASE_ACTOR_URI]
    )
    event = extract_event(activity).model_copy(
        update={"receiving_actor_id": _CASE_ACTOR_URI}
    )
    tree = create_case_proposal_received_tree(
        report_id=report_id,
        proposal_id=_PROPOSAL_URI,
        vendor_uri=_VENDOR_URI,
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
    ).execute_with_setup(tree=tree, actor_id=_CASE_ACTOR_URI, activity=event)
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

    def test_reject_carries_the_proposal_inline(self, dl):
        """AKM-03-001: the vendor cannot dereference a URI in our store.

        ``dl.read()`` rehydrates the stored activity, so the assertion reads the
        typed ``as_CaseProposal`` rather than the dict that was written. A bare
        URI would come back as a ``str``, which is the failure this pins.
        """
        _run_tree(dl, call_out=_declining_bundle([]))

        (reject,) = _outbox_activities(dl)
        proposal = reject.object_
        assert not isinstance(
            proposal, str
        ), f"object_ must not be a bare URI, got {proposal!r}"
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
        # The duplicate case below is pre-existing and NOT what this test
        # guards: `LoadExistingCaseNode(report_id=None)` cannot resolve the
        # existing case, so the accept path creates a second one. Asserted so a
        # reader is not misled into thinking `report_id=None` is fully handled —
        # that gap is #2890 / the ASK-08-002 xfail.
        assert len(_cases(dl)) == 2

    def test_in_flight_retry_marker_short_circuits_before_the_decision(
        self, dl
    ):
        """The marker branch precedes the decline arm, so neither fires."""
        dl.save(
            PendingCreateCaseActivity(
                id_=PendingCreateCaseActivity.build_id(_PROPOSAL_URI),
                proposal_id=_PROPOSAL_URI,
                case_actor_id=_CASE_ACTOR_URI,
                vendor_uri=_VENDOR_URI,
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
                vendor_uri=_VENDOR_URI,
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
            assert (
                len(_cases(dl)) == 1
            ), "the case was created before the fault"
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
        second_vendor_uri = "https://evil.example.org/actors/attacker"

        _dl = SqliteDataLayer("sqlite:///:memory:", actor_id=_CASE_ACTOR_URI)
        _dl.clear_all()
        try:
            # First proposal is admitted normally: a case now exists for
            # _REPORT_URI, which is the state the bypass fed on.
            assert _run_tree(_dl, call_out=_admitting_bundle([])) == (
                Status.SUCCESS
            )
            assert len(_cases(_dl)) == 1
            _dl.outbox_pop()
            _dl.outbox_pop()
            assert _dl.outbox_list() == []

            # A different proposal, from a different actor, naming the same
            # report. The deployment's policy refuses it.
            proposal = as_CaseProposal(
                id_=second_proposal_uri,
                attributed_to=second_vendor_uri,
                object_=as_VulnerabilityReport(
                    id_=_REPORT_URI, attributed_to=_REPORTER_URI
                ),
                target=_CASE_ACTOR_URI,
            )
            activity = as_Create(
                actor=second_vendor_uri,
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
                vendor_uri=second_vendor_uri,
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
                )
                .execute_with_setup(
                    tree=tree, actor_id=_CASE_ACTOR_URI, activity=event
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
            assert (
                len(_cases(_dl)) == 1
            ), "no second case, and the first is untouched"
            participants = [
                p
                for p in _dl.list_objects("CaseParticipant")
                if second_vendor_uri in str(getattr(p, "actor_id", ""))
            ]
            assert participants == [], (
                "a refused actor must not end up on the roster of the case it "
                "was refused from"
            )
        finally:
            _dl.clear_all()
            _dl.close()
