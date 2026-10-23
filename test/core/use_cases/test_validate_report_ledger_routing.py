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

"""Unit tests for the validate_report → CaseActor ledger routing chain.

These tests pin each step needed for ``validate_report`` to appear in the
CaseActor's canonical ledger, replacing the need to wait for the Docker CI
demo to detect regressions.

Chain under test (three layers):

1. **Emit** — validate-report trigger BT addresses the outbound
   ``RmValidateReportActivity`` to the CaseActor when a case already exists
   (CLP-10-001).
2. **Received** — ``ValidateReportReceivedUseCase`` commits a
   ``validate_report`` ledger entry when the CaseActor is the receiving
   actor (CLP-10-002, CLP-10-003).
3. **Full chain** — end-to-end: vendor trigger → CaseActor receives →
   entry in CaseActor's DataLayer.

Context: the case is created at RM.RECEIVED (when the Offer(Report) arrives),
so a case with a CASE_MANAGER participant already exists by the time
``validate-report`` is triggered (ADR-0015).

Spec refs: ADR-0021, CLP-10-001, CLP-10-027, CLP-10-002, CLP-10-003.
"""

from __future__ import annotations

import pytest

from test.support.embargo_register import (
    activate,
    agree_to_active_embargo,
    register,
    write_consent_rows,
)
from test.support.received import with_evidence
from vultron.adapters.driven.datalayer_sqlite import SqliteDataLayer
from vultron.adapters.driven.sync_activity_adapter import SyncActivityAdapter
from vultron.adapters.driven.trigger_activity_adapter import (
    TriggerActivityAdapter,
)
from vultron.adapters.driven.wire_render.as2 import As2WireRenderAdapter
from vultron.core.models._helpers import days_from_now_utc
from vultron.core.models.activity import VultronActivity
from vultron.core.models.case import VulnerabilityCase
from vultron.core.models.dimensions import (
    RmDimension,
)
from vultron.core.models.embargo_event import EmbargoEvent
from vultron.core.models.events.base import MessageSemantics
from vultron.core.models.events.report import (
    InvalidateReportReceivedEvent,
    ValidateReportReceivedEvent,
)
from vultron.core.models.offer_record import VultronOfferRecord
from vultron.core.models.report import VulnerabilityReport
from vultron.core.models.report_case_link import VultronReportCaseLink
from vultron.core.models.use_case_result import HandlerDisposition
from vultron.core.states.rm import RM
from vultron.core.use_cases._helpers import _find_case_actor_id
from vultron.core.use_cases.received.report import (
    InvalidateReportReceivedUseCase,
    ValidateReportReceivedUseCase,
)
from vultron.core.use_cases.triggers.report import SvcValidateReportUseCase
from vultron.core.use_cases.triggers.requests import (
    ValidateReportTriggerRequest,
)
from vultron.enums.roles import CVDRole
from vultron.wire.as2.vocab.base.objects.activities.transitive import as_Offer
from vultron.wire.as2.vocab.base.objects.actors import as_Service
from vultron.wire.as2.vocab.objects.case_participant import (
    as_CaseParticipant,
    as_ParticipantStatus,
)
from vultron.wire.as2.vocab.objects.vulnerability_case import (
    as_VulnerabilityCase,
)
from vultron.wire.as2.vocab.objects.vulnerability_report import (
    as_VulnerabilityReport,
)

# ---------------------------------------------------------------------------
# Shared helpers
# ---------------------------------------------------------------------------


def _make_dl(actor_id: str) -> SqliteDataLayer:
    return SqliteDataLayer(
        "sqlite:///:memory:",
        actor_id=actor_id,
    )


def _make_case_at_received(
    dl: SqliteDataLayer,
    vendor_id: str,
    finder_id: str,
    report_id: str,
) -> tuple[VulnerabilityCase, as_Offer]:
    """Create a case at RM.RECEIVED, simulating what CaseActor provides.

    ADR-0041: the vendor tree no longer creates a VulnerabilityCase.  This
    helper creates one directly with an active embargo and a CASE_MANAGER
    Service, reproducing the state the CaseActor would establish after
    accepting a CaseProposal.

    Returns:
        (case, offer) — both persisted in *dl*.
    """
    report_obj = as_VulnerabilityReport(id_=report_id, name="Test Vul Report")
    dl.save(report_obj)
    offer = as_Offer(
        actor=finder_id,
        object_=report_obj.id_,
        target=vendor_id,
    )
    dl.create(offer)
    offer_record = VultronOfferRecord(
        offer_id=offer.id_,
        report_id=report_obj.id_,
        offer_actor_id=finder_id,
        offer_to=[vendor_id],
    )
    dl.create(offer_record)

    embargo_id = f"{vendor_id}/embargoes/test-embargo"
    case_id = f"{vendor_id}/cases/test-case-received"
    case = VulnerabilityCase(
        id_=case_id,
        name="Test Case at Received",
        attributed_to=vendor_id,
        vulnerability_reports=[report_id],
        embargo_register=register(active=embargo_id),
    )
    dl.create(case)

    case_actor = as_Service(
        name="Case Actor Service",
        context=case_id,
    )
    dl.create(case_actor)
    case_manager_participant = as_CaseParticipant(
        attributed_to=case_actor.id_,
        context=case_id,
        case_roles=[CVDRole.CASE_MANAGER],
    )
    dl.create(case_manager_participant)
    case.actor_participant_index[case_actor.id_] = case_manager_participant.id_
    case.case_participants.append(case_manager_participant.id_)

    # RM.VALID is case-scoped, so the vendor must be a participant of its own
    # case replica — what Create(VulnerabilityCase) delivers (ADR-0041,
    # CBT-01-002).  Absent that, the validate-report BT refuses to act instead
    # of latching a transition that never happened (ISSUE-2548).
    vendor_participant = as_CaseParticipant(
        attributed_to=vendor_id,
        context=case_id,
        case_roles=[CVDRole.VENDOR],
        participant_statuses=[
            as_ParticipantStatus(
                attributed_to=vendor_id,
                context=case_id,
                rm=RmDimension(state=RM.RECEIVED),
            )
        ],
    )
    dl.create(vendor_participant)
    case.actor_participant_index[vendor_id] = vendor_participant.id_
    case.case_participants.append(vendor_participant.id_)
    dl.save(case)
    write_consent_rows(dl, case)
    dl.create(VultronReportCaseLink(report_id=report_id, rm_state=RM.RECEIVED))

    return case, offer


def _add_participant_at_received(
    dl: SqliteDataLayer, case: VulnerabilityCase, actor_id: str
) -> None:
    """Add *actor_id* to *case* as a participant at RM.RECEIVED.

    The caller saves *case* afterwards.
    """
    participant = as_CaseParticipant(
        attributed_to=actor_id,
        context=case.id_,
        case_roles=[CVDRole.VENDOR],
        participant_statuses=[
            as_ParticipantStatus(
                attributed_to=actor_id,
                context=case.id_,
                rm=RmDimension(state=RM.RECEIVED),
            )
        ],
    )
    dl.create(participant)
    case.actor_participant_index[actor_id] = participant.id_
    case.case_participants.append(participant.id_)


def _ledger_semantic_types(dl: SqliteDataLayer) -> list[str]:
    """Return all ``semantic_type`` values in the DataLayer's CaseLedgerEntry set."""
    return [
        getattr(e, "semantic_type", "")
        for e in dl.list_objects("CaseLedgerEntry")
    ]


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

_CASE_ACTOR_SERVICE_URL = "http://case-actor:7999/api/v2"


@pytest.fixture(autouse=True)
def _configure_case_actor_url(monkeypatch):
    """Set VULTRON_ACTOR__CASE_ACTOR_SERVICE_URL for ResolveCaseActorUrlsNode."""
    monkeypatch.setenv(
        "VULTRON_ACTOR__CASE_ACTOR_SERVICE_URL", _CASE_ACTOR_SERVICE_URL
    )
    from vultron.config.app import reload_config

    reload_config()
    yield
    # Undo the env patch BEFORE reloading: monkeypatch's own undo runs after
    # this teardown, so reloading first would re-cache this fixture's URL into
    # the module-level config for the rest of the session (#2086).
    monkeypatch.undo()
    reload_config()


# ---------------------------------------------------------------------------
# Layer 1 — Trigger emits to the CaseActor's outbox
# ---------------------------------------------------------------------------


@pytest.mark.spec("CLP-10-027")
class TestTriggerEmitsToCaseActorOutbox:
    """validate-report trigger routes the activity to the CaseActor's outbox.

    Per CLP-10-027: when a case already exists with a CASE_MANAGER, the
    trigger BT MUST address the outbound RmValidateReportActivity to the
    case_manager_id rather than back to the sender or the finder.
    """

    VENDOR_ID = "https://example.org/actors/vendor-emit"
    FINDER_ID = "https://example.org/actors/finder-emit"
    REPORT_ID = "https://example.org/reports/r-emit-test"

    def _setup(
        self,
    ) -> tuple[SqliteDataLayer, VulnerabilityCase, as_Offer, str]:
        """Return (dl, case, offer, case_actor_id) after BT receive-report."""
        dl = _make_dl(self.VENDOR_ID)
        vendor = as_Service(id_=self.VENDOR_ID, name="Vendor")
        finder = as_Service(id_=self.FINDER_ID, name="Finder")
        dl.save(vendor)
        dl.save(finder)
        case, offer = _make_case_at_received(
            dl, self.VENDOR_ID, self.FINDER_ID, self.REPORT_ID
        )
        case_actor_id = _find_case_actor_id(dl, case.id_)
        assert case_actor_id is not None, (
            "BT must register a CaseActor Service"
        )
        return dl, case, offer, case_actor_id

    def test_emit_addressed_to_case_actor_id(self):
        """Emitted RmValidateReportActivity has ``to=[case_actor_id]``.

        Per CLP-10-027: the trigger tree MUST emit to the CaseActor so the
        CaseActor can execute the guarded commit.
        """
        from vultron.core.use_cases._helpers import outbox_ids

        dl, _case, offer, case_actor_id = self._setup()

        before = outbox_ids(self.VENDOR_ID, dl)
        SvcValidateReportUseCase(
            dl,
            ValidateReportTriggerRequest(
                actor_id=self.VENDOR_ID, offer_id=offer.id_
            ),
            trigger_activity=TriggerActivityAdapter(dl),
            wire_render_port=As2WireRenderAdapter(),
            sync_port=SyncActivityAdapter(dl),
        ).execute()
        after = outbox_ids(self.VENDOR_ID, dl)

        new_ids = after - before
        assert new_ids, (
            "validate-report trigger must emit at least one activity"
        )

        activity_id = next(iter(new_ids))
        emitted = dl.read(activity_id)
        assert emitted is not None, (
            f"Emitted activity '{activity_id}' not found in DL"
        )

        to_list = getattr(emitted, "to", None) or []
        assert case_actor_id in to_list, (
            f"Emitted activity must be addressed to CaseActor {case_actor_id!r}; "
            f"got to={to_list!r}"
        )

    def test_emit_not_addressed_back_to_sender(self):
        """The emitted activity MUST NOT be addressed to the sending vendor.

        ``_compute_report_addressees`` excludes the sending actor to prevent
        self-delivery.
        """
        from vultron.core.use_cases._helpers import outbox_ids

        dl, _case, offer, _case_actor_id = self._setup()

        before = outbox_ids(self.VENDOR_ID, dl)
        SvcValidateReportUseCase(
            dl,
            ValidateReportTriggerRequest(
                actor_id=self.VENDOR_ID, offer_id=offer.id_
            ),
            trigger_activity=TriggerActivityAdapter(dl),
            wire_render_port=As2WireRenderAdapter(),
            sync_port=SyncActivityAdapter(dl),
        ).execute()
        after = outbox_ids(self.VENDOR_ID, dl)

        new_ids = after - before
        assert new_ids, (
            "validate-report trigger must emit at least one activity"
        )

        activity_id = next(iter(new_ids))
        emitted = dl.read(activity_id)
        to_list = getattr(emitted, "to", None) or []
        assert self.VENDOR_ID not in to_list, (
            "Emitted activity must not be addressed back to the sending vendor"
        )


# ---------------------------------------------------------------------------
# Layer 2 — CaseActor received use case writes the ledger entry
# ---------------------------------------------------------------------------


class TestCaseActorReceivedWritesLedgerEntry:
    """ValidateReportReceivedUseCase writes a ``validate_report`` ledger entry.

    Per CLP-10-002: when receiving_actor_id == case_actor_id the guarded
    commit BT MUST execute, resulting in a persisted CaseLedgerEntry with
    ``semantic_type == "validate_report"``.

    The case-actor DataLayer is set up directly (without running the full BT
    chain) to isolate the received use-case layer.
    """

    CASE_ACTOR_ID = "https://example.org/actors/case-actor-ledger"
    VENDOR_ID = "https://example.org/actors/vendor-ledger"
    REPORT_ID = "https://example.org/reports/r-ledger-test"
    OFFER_ID = "https://example.org/activities/offer-ledger"
    ACCEPT_ID = "https://example.org/activities/accept-ledger"
    CASE_ID = "https://example.org/cases/c-ledger-test"
    PARTICIPANT_ID = "https://example.org/actors/participant-ledger"

    def _make_case_actor_dl(
        self, owner_id: str | None = None
    ) -> SqliteDataLayer:
        """DataLayer as seen by the CaseActor: case + CASE_MANAGER + Service link.

        With *owner_id* the same case is that participant's replica instead.
        """
        from vultron.core.models.actor import VultronService

        dl = _make_dl(owner_id or self.CASE_ACTOR_ID)

        # The CaseActor Service must have context=case_id so that
        # _find_case_actor_id resolves it via the Service scan.
        case_actor_svc = VultronService(
            id_=self.CASE_ACTOR_ID,
            context=self.CASE_ID,
        )
        dl.save(case_actor_svc)

        # An embargo is part of what a delivered Create(VulnerabilityCase)
        # replica carries, alongside the participant index (ADR-0041,
        # CBT-01-002).  ValidateReportBT now resolves the case *before* it
        # writes anything, so a replica missing the embargo blocks the
        # RM.VALID transition outright rather than latching a phantom
        # report-phase record (DUR-07-004, ISSUE-2548).
        case = as_VulnerabilityCase(
            id_=self.CASE_ID,
            name="Ledger Routing Test Case",
            attributed_to=self.CASE_ACTOR_ID,
            embargo_register=register(
                active=f"{self.CASE_ID}/embargoes/ledger-test"
            ),
        )
        case.vulnerability_reports.append(self.REPORT_ID)

        cm_participant = as_CaseParticipant(
            attributed_to=self.CASE_ACTOR_ID,
            context=self.CASE_ID,
            case_roles=[CVDRole.CASE_MANAGER],
        )
        dl.create(cm_participant)
        case.case_participants.append(cm_participant.id_)
        case.actor_participant_index[self.CASE_ACTOR_ID] = cm_participant.id_
        # The sender must be an active participant of the case the CaseActor
        # manages: its declaration is refused before the commit otherwise
        # (HP-01-006, CM-10-004, CM-23-018), so it is a signatory to the
        # embargo in force.  RM.RECEIVED is the state it holds before
        # validate-report.
        _add_participant_at_received(dl, case, self.VENDOR_ID)
        if owner_id is not None:
            _add_participant_at_received(dl, case, owner_id)
        dl.save(case)
        write_consent_rows(dl, case)
        agree_to_active_embargo(dl, case, self.VENDOR_ID)
        dl.create(
            VultronReportCaseLink(
                report_id=self.REPORT_ID, rm_state=RM.RECEIVED
            )
        )

        return dl

    def _at_participant(
        self,
        event: ValidateReportReceivedEvent | InvalidateReportReceivedEvent,
    ) -> ValidateReportReceivedEvent | InvalidateReportReceivedEvent:
        """*event* as the copy a participant that is not the CASE_MANAGER got.

        Addressed to that participant too, so the run reaches the role gate
        rather than stopping at the door (HP-01-012).
        """
        assert event.activity is not None
        return event.model_copy(
            update={
                "receiving_actor_id": self.PARTICIPANT_ID,
                "activity": event.activity.model_copy(
                    update={"to": [self.CASE_ACTOR_ID, self.PARTICIPANT_ID]}
                ),
            }
        )

    def _make_invalidate_event(self) -> InvalidateReportReceivedEvent:
        """The TentativeReject(Offer(Report)) twin of the validate event."""
        validate = self._make_validate_event()
        assert validate.activity is not None
        return with_evidence(
            InvalidateReportReceivedEvent(
                semantic_type=MessageSemantics.INVALIDATE_REPORT,
                activity_id=validate.activity_id,
                actor_id=validate.actor_id,
                object_=validate.object_,
                inner_object=validate.inner_object,
                activity=validate.activity.model_copy(
                    update={"type_": "TentativeReject"}
                ),
                receiving_actor_id=validate.receiving_actor_id,
            )
        )

    @pytest.mark.spec("HP-01-005")
    @pytest.mark.parametrize(
        ("use_case", "make_event"),
        [
            (ValidateReportReceivedUseCase, "_make_validate_event"),
            (InvalidateReportReceivedUseCase, "_make_invalidate_event"),
        ],
        ids=["validate", "invalidate"],
    )
    def test_participant_that_is_not_the_case_manager_refuses(
        self, use_case, make_event
    ):
        """A participant the Accept/TentativeReject reached refuses it.

        The RM write, the commit and every effect sit behind the CASE_MANAGER
        gate, so the participant does nothing; it reports the misaddressed
        message as a refusal, never as applied (HP-01-005).
        """
        dl = self._make_case_actor_dl(owner_id=self.PARTICIPANT_ID)
        event = self._at_participant(getattr(self, make_event)())

        result = use_case(
            dl,
            event,
            wire_render_port=As2WireRenderAdapter(),
            sync_port=SyncActivityAdapter(dl),
            trigger_activity=TriggerActivityAdapter(dl),
        ).execute()

        assert result.disposition is HandlerDisposition.REFUSED
        assert result.reason is not None
        assert "not the CASE_MANAGER" in result.reason
        assert dl.outbox_list() == []
        assert _ledger_semantic_types(dl) == []

    @pytest.mark.spec("HP-01-005")
    @pytest.mark.parametrize(
        ("use_case", "make_event"),
        [
            (ValidateReportReceivedUseCase, "_make_validate_event"),
            (InvalidateReportReceivedUseCase, "_make_invalidate_event"),
        ],
        ids=["validate", "invalidate"],
    )
    def test_case_manager_still_applies(self, use_case, make_event):
        """The control: the CASE_MANAGER itself applies the declaration."""
        dl = self._make_case_actor_dl()

        result = use_case(
            dl,
            getattr(self, make_event)(),
            wire_render_port=As2WireRenderAdapter(),
            sync_port=SyncActivityAdapter(dl),
            trigger_activity=TriggerActivityAdapter(dl),
        ).execute()

        assert result.disposition is HandlerDisposition.APPLIED

    def _make_validate_event(
        self, receiving_actor_id: str | None = None
    ) -> ValidateReportReceivedEvent:
        """Construct a ValidateReportReceivedEvent for the CaseActor's inbox.

        The wire format is Accept(Offer(as_VulnerabilityReport)).  The activity
        must carry an ``object_`` with ``type_="Offer"`` so the canonical
        signature check in ``_validate_canonical_entry`` sees
        ``("Accept", "Offer")``.
        """
        if receiving_actor_id is None:
            receiving_actor_id = self.CASE_ACTOR_ID

        # The inner Offer carries the as_VulnerabilityReport.
        report_obj = VulnerabilityReport(id_=self.REPORT_ID)
        offer_obj = VultronActivity(
            id_=self.OFFER_ID,
            type_="Offer",
            actor=self.VENDOR_ID,
            object_=report_obj,
            context=self.CASE_ID,
        )
        # The Accept wraps the Offer.
        activity = VultronActivity(
            id_=self.ACCEPT_ID,
            type_="Accept",
            actor=self.VENDOR_ID,
            to=[self.CASE_ACTOR_ID],
            object_=offer_obj,
            context=self.CASE_ID,
        )
        return with_evidence(
            ValidateReportReceivedEvent(
                semantic_type=MessageSemantics.VALIDATE_REPORT,
                activity_id=self.ACCEPT_ID,
                actor_id=self.VENDOR_ID,
                object_=offer_obj,
                inner_object=report_obj,
                activity=activity,
                receiving_actor_id=receiving_actor_id,
            )
        )

    def test_ledger_has_validate_report_entry(self):
        """CaseLedgerEntry with semantic_type='validate_report' is persisted.

        This is the invariant checked by the CI ratchet test
        ``test_invariant_5_expected_semantic_types_present[validate_report]``.
        """
        dl = self._make_case_actor_dl()
        ValidateReportReceivedUseCase(
            dl,
            self._make_validate_event(),
            wire_render_port=As2WireRenderAdapter(),
            sync_port=SyncActivityAdapter(dl),
            trigger_activity=TriggerActivityAdapter(dl),
        ).execute()

        semantic_types = _ledger_semantic_types(dl)
        assert "validate_report" in semantic_types, (
            "Expected a CaseLedgerEntry with semantic_type='validate_report'; "
            f"found: {semantic_types}"
        )

    def test_ledger_entry_links_to_correct_case(self):
        """The persisted ledger entry references the correct case_id."""
        dl = self._make_case_actor_dl()
        ValidateReportReceivedUseCase(
            dl,
            self._make_validate_event(),
            wire_render_port=As2WireRenderAdapter(),
            sync_port=SyncActivityAdapter(dl),
            trigger_activity=TriggerActivityAdapter(dl),
        ).execute()

        entries = list(dl.list_objects("CaseLedgerEntry"))
        vr_entries = [
            e
            for e in entries
            if getattr(e, "semantic_type", "") == "validate_report"
        ]
        assert vr_entries, "No validate_report ledger entry found"
        assert all(
            getattr(e, "case_id", None) == self.CASE_ID for e in vr_entries
        ), f"validate_report entry must reference case_id={self.CASE_ID!r}"

    def test_no_ledger_entry_when_receiving_actor_is_not_case_actor(self):
        """Non-CaseActor receiving actors do NOT write a ledger entry.

        Per CLP-10-003: the pre-flight guard skips the commit when
        receiving_actor_id != case_actor_id.
        """
        dl = self._make_case_actor_dl()
        event = self._make_validate_event(receiving_actor_id=self.VENDOR_ID)

        ValidateReportReceivedUseCase(
            dl,
            event,
            wire_render_port=As2WireRenderAdapter(),
            sync_port=SyncActivityAdapter(dl),
            trigger_activity=TriggerActivityAdapter(dl),
        ).execute()

        semantic_types = _ledger_semantic_types(dl)
        assert "validate_report" not in semantic_types, (
            "Non-CaseActor receiving actor must NOT write a validate_report "
            f"ledger entry; found semantic_types={semantic_types}"
        )

    def test_sender_rm_state_transitions_to_valid(self):
        """Vendor (sender) RM state is set to VALID even when CaseActor is receiver.

        Verifies the sender_actor_id threading introduced in ADR-0022: nodes
        CheckRMStateValid, CheckRMStateReceivedOrInvalid, and TransitionRMtoValid
        receive ``sender_actor_id=VENDOR_ID`` so the RM transition targets the
        message sender regardless of which actor ``execute_with_setup`` runs
        under (receiving_actor_id=CASE_ACTOR_ID).
        """
        from vultron.core.models.report_case_link import VultronReportCaseLink
        from vultron.core.states.rm import RM

        dl = self._make_case_actor_dl()

        # The fixture registers VENDOR as a RM.RECEIVED participant so
        # TransitionRMtoValid can persist the status record; RECEIVED -> VALID
        # is a legal move, START -> VALID would be a gap (ISSUE-2548).
        ValidateReportReceivedUseCase(
            dl,
            self._make_validate_event(),  # actor_id=VENDOR, receiving=CASE_ACTOR,
            wire_render_port=As2WireRenderAdapter(),
            sync_port=SyncActivityAdapter(dl),
            trigger_activity=TriggerActivityAdapter(dl),
        ).execute()

        link = dl.read(VultronReportCaseLink.build_id(self.REPORT_ID))
        assert (
            isinstance(link, VultronReportCaseLink)
            and link.rm_state == RM.VALID
        ), (
            f"Vendor (sender) {self.VENDOR_ID!r} must have RM.VALID persisted "
            "after validate-report; sender_actor_id threading may be broken "
            "(ADR-0022 single-BT migration)"
        )


class TestFullValidateReportLedgerChain:
    """End-to-end: vendor trigger → CaseActor inbox → CaseLedgerEntry.

    Uses two distinct DataLayer instances (vendor_dl, case_actor_dl) to
    simulate the real two-actor scenario.  A failure here pinpoints which
    layer broke without requiring the Docker CI demo.

    Steps:
    1. vendor_dl — case at RM.RECEIVED, CaseActor already registered by BT.
    2. Trigger validate-report on vendor_dl → BT emits to CaseActor outbox.
    3. Extract emitted activity; verify it targets the CaseActor.
    4. Build case_actor_dl with the same case (same IDs).
    5. Dispatch ValidateReportReceivedUseCase on case_actor_dl.
    6. Assert case_actor_dl ledger contains 'validate_report'.
    """

    VENDOR_ID = "https://example.org/actors/vendor-chain"
    FINDER_ID = "https://example.org/actors/finder-chain"
    REPORT_ID = "https://example.org/reports/r-chain-test"

    def test_case_actor_ledger_contains_validate_report_after_trigger(self):
        """CaseActor ledger has 'validate_report' after vendor triggers validate."""
        from vultron.core.models.actor import VultronService
        from vultron.core.use_cases._helpers import outbox_ids

        # ── Step 1: vendor_dl — case at RM.RECEIVED ──────────────────────────
        vendor_dl = _make_dl(self.VENDOR_ID)
        vendor = as_Service(id_=self.VENDOR_ID, name="Vendor Co")
        finder = as_Service(id_=self.FINDER_ID, name="Finder Co")
        vendor_dl.save(vendor)
        vendor_dl.save(finder)

        case, offer = _make_case_at_received(
            vendor_dl, self.VENDOR_ID, self.FINDER_ID, self.REPORT_ID
        )
        case_actor_id = _find_case_actor_id(vendor_dl, case.id_)
        assert case_actor_id is not None, (
            "BT must register a CaseActor Service"
        )

        # ── Step 2: trigger validate-report on vendor_dl ─────────────────────
        before = outbox_ids(self.VENDOR_ID, vendor_dl)
        SvcValidateReportUseCase(
            vendor_dl,
            ValidateReportTriggerRequest(
                actor_id=self.VENDOR_ID, offer_id=offer.id_
            ),
            trigger_activity=TriggerActivityAdapter(vendor_dl),
            wire_render_port=As2WireRenderAdapter(),
            sync_port=SyncActivityAdapter(vendor_dl),
        ).execute()
        after = outbox_ids(self.VENDOR_ID, vendor_dl)

        new_ids = after - before
        assert new_ids, (
            "validate-report trigger must emit at least one activity"
        )

        # ── Step 3: verify emitted activity targets the CaseActor ────────────
        emitted_id = next(iter(new_ids))
        emitted = vendor_dl.read(emitted_id)
        assert emitted is not None, (
            f"Emitted activity '{emitted_id}' not in vendor_dl"
        )
        to_list = getattr(emitted, "to", None) or []
        assert case_actor_id in to_list, (
            f"Emitted activity should target CaseActor {case_actor_id!r}; "
            f"got to={to_list!r}"
        )

        # ── Step 4: build case_actor_dl with same case identifiers ────────────
        # Keyed by the CaseActor, not the vendor. Two things were wrong with
        # `_make_dl(self.VENDOR_ID)` here: the use case receives as the CaseActor,
        # so the tree runs in the CaseActor's store and found no case there; and
        # an actor id *is* a store name, so passing the vendor's id handed back
        # the very same in-memory database as `vendor_dl` above. The two halves of
        # this "vendor triggers, CaseActor receives" chain were one store, which
        # is exactly the sharing that hides a missing cross-store write.
        case_actor_dl = _make_dl(case_actor_id)

        # The CaseActor Service needs context=case.id_ for _find_case_actor_id.
        ca_svc = VultronService(id_=case_actor_id, context=case.id_)
        case_actor_dl.save(ca_svc)

        ca_case = as_VulnerabilityCase(
            id_=case.id_,
            name=case.name or "Test Case",
            attributed_to=case_actor_id,
        )
        ca_case.vulnerability_reports.append(self.REPORT_ID)
        # DUR-07-004: validation needs an embargo in force.  The validation
        # and the received act's entry are one act (CLP-07-015), so a
        # validation that fails keeps no validate_report entry either.
        embargo = EmbargoEvent(
            id_=f"{ca_case.id_}/embargoes/chain-embargo",
            context=ca_case.id_,
            end_time=days_from_now_utc(45),
        )
        case_actor_dl.create(embargo)
        activate(ca_case, embargo.id_)

        ca_participant = as_CaseParticipant(
            attributed_to=case_actor_id,
            context=ca_case.id_,
            case_roles=[CVDRole.CASE_MANAGER],
        )
        case_actor_dl.create(ca_participant)
        ca_case.case_participants.append(ca_participant.id_)
        ca_case.actor_participant_index[case_actor_id] = ca_participant.id_
        # The vendor is a participant of the case the CaseActor manages; the
        # CaseActor refuses a declaration from anyone else (HP-01-006).
        _add_participant_at_received(case_actor_dl, ca_case, self.VENDOR_ID)
        case_actor_dl.save(ca_case)
        write_consent_rows(case_actor_dl, ca_case)

        # ── Step 5: dispatch ValidateReportReceivedUseCase on case_actor_dl ───
        # Seed the report-phase RM state on the CaseActor's DataLayer.
        case_actor_dl.create(
            VultronReportCaseLink(
                report_id=self.REPORT_ID, rm_state=RM.RECEIVED
            )
        )
        report_obj = VulnerabilityReport(id_=self.REPORT_ID)
        offer_obj = VultronActivity(
            id_=offer.id_,
            type_="Offer",
            actor=self.FINDER_ID,
            object_=report_obj,
            context=ca_case.id_,
        )
        # The Accept wraps the Offer — canonical signature ("Accept", "Offer").
        activity = VultronActivity(
            id_=emitted_id,
            type_="Accept",
            actor=self.VENDOR_ID,
            # Addressed as the trigger addressed the emitted activity.
            to=list(to_list),
            object_=offer_obj,
            context=ca_case.id_,
        )
        event = with_evidence(
            ValidateReportReceivedEvent(
                semantic_type=MessageSemantics.VALIDATE_REPORT,
                activity_id=emitted_id,
                actor_id=self.VENDOR_ID,
                object_=offer_obj,
                inner_object=report_obj,
                activity=activity,
                receiving_actor_id=case_actor_id,
            )
        )

        ValidateReportReceivedUseCase(
            case_actor_dl,
            event,
            wire_render_port=As2WireRenderAdapter(),
            sync_port=SyncActivityAdapter(case_actor_dl),
            trigger_activity=TriggerActivityAdapter(case_actor_dl),
        ).execute()

        # ── Step 6: assert CaseActor ledger has the validate_report entry ─────
        semantic_types = _ledger_semantic_types(case_actor_dl)
        assert "validate_report" in semantic_types, (
            "Expected CaseActor DataLayer to contain a CaseLedgerEntry with "
            f"semantic_type='validate_report'; found: {semantic_types}"
        )
