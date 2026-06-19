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

Spec refs: ADR-0021, CLP-10-001, CLP-10-002, CLP-10-003.
"""

from __future__ import annotations

import pytest

from vultron.adapters.driven.datalayer_sqlite import SqliteDataLayer
from vultron.adapters.driven.trigger_activity_adapter import (
    TriggerActivityAdapter,
)
from vultron.core.models.activity import VultronActivity
from vultron.core.models.events.base import MessageSemantics
from vultron.core.models.events.report import ValidateReportReceivedEvent
from vultron.core.models.report import VultronReport
from vultron.core.states.roles import CVDRole
from vultron.core.use_cases._helpers import _find_case_actor_id
from vultron.core.use_cases.received.report import (
    ValidateReportReceivedUseCase,
)
from vultron.core.use_cases.triggers.service import TriggerService
from vultron.wire.as2.vocab.base.objects.activities.transitive import as_Offer
from vultron.wire.as2.vocab.base.objects.actors import as_Service
from vultron.wire.as2.vocab.objects.case_participant import CaseParticipant
from vultron.wire.as2.vocab.objects.vulnerability_case import VulnerabilityCase
from vultron.wire.as2.vocab.objects.vulnerability_report import (
    VulnerabilityReport,
)

# ---------------------------------------------------------------------------
# Shared helpers
# ---------------------------------------------------------------------------


def _make_dl() -> SqliteDataLayer:
    return SqliteDataLayer("sqlite:///:memory:")


def _make_case_at_received(
    dl: SqliteDataLayer,
    vendor_id: str,
    finder_id: str,
    report_id: str,
) -> tuple[VulnerabilityCase, as_Offer]:
    """Create a case at RM.RECEIVED via the receive-report BT.

    Mirrors the real production path: Offer(Report) arrives → BT creates a
    case and the CaseActor Service at RM.RECEIVED (ADR-0015).  The returned
    case already has a CASE_MANAGER entry in ``actor_participant_index``
    populated by ``CreateCaseActorNode``.

    Returns:
        (case, offer) — both persisted in *dl*.
    """
    from vultron.core.behaviors.bridge import BTBridge
    from vultron.core.behaviors.case.receive_report_case_tree import (
        create_receive_report_case_tree,
    )

    report_obj = VulnerabilityReport(id_=report_id, name="Test Vul Report")
    dl.save(report_obj)
    offer = as_Offer(
        actor=finder_id,
        object_=report_obj.id_,
        target=vendor_id,
    )
    dl.create(offer)

    bridge = BTBridge(
        datalayer=dl, trigger_activity=TriggerActivityAdapter(dl)
    )
    tree = create_receive_report_case_tree(
        report_id=report_id,
        offer_id=offer.id_,
        reporter_actor_id=finder_id,
    )
    bridge.execute_with_setup(tree, actor_id=vendor_id)

    case = dl.find_case_by_report_id(report_id)
    assert (
        case is not None
    ), "receive_report BT must create a VulnerabilityCase"
    assert isinstance(
        case, VulnerabilityCase
    ), f"Expected VulnerabilityCase, got {type(case)}"
    return case, offer


def _ledger_event_types(dl: SqliteDataLayer) -> list[str]:
    """Return all ``event_type`` values in the DataLayer's CaseLedgerEntry set."""
    return [
        getattr(e, "event_type", "")
        for e in dl.list_objects("CaseLedgerEntry")
    ]


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture(autouse=True)
def _clear_blackboard():
    import py_trees

    py_trees.blackboard.Blackboard.storage.clear()
    yield
    py_trees.blackboard.Blackboard.storage.clear()


# ---------------------------------------------------------------------------
# Layer 1 — Trigger emits to the CaseActor's outbox
# ---------------------------------------------------------------------------


class TestTriggerEmitsToCaseActorOutbox:
    """validate-report trigger routes the activity to the CaseActor's outbox.

    Per CLP-10-001: when a case already exists with a CASE_MANAGER, the
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
        dl = _make_dl()
        vendor = as_Service(id_=self.VENDOR_ID, name="Vendor")
        finder = as_Service(id_=self.FINDER_ID, name="Finder")
        dl.save(vendor)
        dl.save(finder)
        case, offer = _make_case_at_received(
            dl, self.VENDOR_ID, self.FINDER_ID, self.REPORT_ID
        )
        case_actor_id = _find_case_actor_id(dl, case.id_)
        assert (
            case_actor_id is not None
        ), "BT must register a CaseActor Service"
        return dl, case, offer, case_actor_id

    def test_emit_addressed_to_case_actor_id(self):
        """Emitted RmValidateReportActivity has ``to=[case_actor_id]``.

        Per CLP-10-001: the trigger tree MUST emit to the CaseActor so the
        CaseActor can execute the guarded commit.
        """
        from vultron.core.use_cases.triggers._helpers import outbox_ids

        dl, _case, offer, case_actor_id = self._setup()

        before = outbox_ids(self.VENDOR_ID, dl)
        TriggerService(
            dl, trigger_activity=TriggerActivityAdapter(dl)
        ).validate_report(self.VENDOR_ID, offer.id_, None)
        after = outbox_ids(self.VENDOR_ID, dl)

        new_ids = after - before
        assert (
            new_ids
        ), "validate-report trigger must emit at least one activity"

        activity_id = next(iter(new_ids))
        emitted = dl.read(activity_id)
        assert (
            emitted is not None
        ), f"Emitted activity '{activity_id}' not found in DL"

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
        from vultron.core.use_cases.triggers._helpers import outbox_ids

        dl, _case, offer, _case_actor_id = self._setup()

        before = outbox_ids(self.VENDOR_ID, dl)
        TriggerService(
            dl, trigger_activity=TriggerActivityAdapter(dl)
        ).validate_report(self.VENDOR_ID, offer.id_, None)
        after = outbox_ids(self.VENDOR_ID, dl)

        new_ids = after - before
        assert (
            new_ids
        ), "validate-report trigger must emit at least one activity"

        activity_id = next(iter(new_ids))
        emitted = dl.read(activity_id)
        to_list = getattr(emitted, "to", None) or []
        assert (
            self.VENDOR_ID not in to_list
        ), "Emitted activity must not be addressed back to the sending vendor"


# ---------------------------------------------------------------------------
# Layer 2 — CaseActor received use case writes the ledger entry
# ---------------------------------------------------------------------------


class TestCaseActorReceivedWritesLedgerEntry:
    """ValidateReportReceivedUseCase writes a ``validate_report`` ledger entry.

    Per CLP-10-002: when receiving_actor_id == case_actor_id the guarded
    commit BT MUST execute, resulting in a persisted CaseLedgerEntry with
    ``event_type == "validate_report"``.

    The case-actor DataLayer is set up directly (without running the full BT
    chain) to isolate the received use-case layer.
    """

    CASE_ACTOR_ID = "https://example.org/actors/case-actor-ledger"
    VENDOR_ID = "https://example.org/actors/vendor-ledger"
    REPORT_ID = "https://example.org/reports/r-ledger-test"
    OFFER_ID = "https://example.org/activities/offer-ledger"
    ACCEPT_ID = "https://example.org/activities/accept-ledger"
    CASE_ID = "https://example.org/cases/c-ledger-test"

    def _make_case_actor_dl(self) -> SqliteDataLayer:
        """DataLayer as seen by the CaseActor: case + CASE_MANAGER + Service link."""
        from vultron.core.models.case_actor import VultronCaseActor

        dl = _make_dl()

        # The CaseActor Service must have context=case_id so that
        # _find_case_actor_id resolves it via the Service scan.
        case_actor_svc = VultronCaseActor(
            id_=self.CASE_ACTOR_ID,
            context=self.CASE_ID,
        )
        dl.save(case_actor_svc)

        case = VulnerabilityCase(
            id_=self.CASE_ID,
            name="Ledger Routing Test Case",
            attributed_to=self.CASE_ACTOR_ID,
        )
        case.vulnerability_reports.append(self.REPORT_ID)

        cm_participant = CaseParticipant(
            attributed_to=self.CASE_ACTOR_ID,
            context=self.CASE_ID,
            case_roles=[CVDRole.CASE_MANAGER],
        )
        dl.create(cm_participant)
        case.case_participants.append(cm_participant.id_)
        case.actor_participant_index[self.CASE_ACTOR_ID] = cm_participant.id_
        dl.save(case)

        return dl

    def _make_validate_event(
        self, receiving_actor_id: str | None = None
    ) -> ValidateReportReceivedEvent:
        """Construct a ValidateReportReceivedEvent for the CaseActor's inbox.

        The wire format is Accept(Offer(VulnerabilityReport)).  The activity
        must carry an ``object_`` with ``type_="Offer"`` so the canonical
        signature check in ``_validate_canonical_entry`` sees
        ``("Accept", "Offer")``.
        """
        if receiving_actor_id is None:
            receiving_actor_id = self.CASE_ACTOR_ID

        # The inner Offer carries the VulnerabilityReport.
        report_obj = VultronReport(id_=self.REPORT_ID)
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
            object_=offer_obj,
            context=self.CASE_ID,
        )
        return ValidateReportReceivedEvent(
            semantic_type=MessageSemantics.VALIDATE_REPORT,
            activity_id=self.ACCEPT_ID,
            actor_id=self.VENDOR_ID,
            object_=offer_obj,
            inner_object=report_obj,
            activity=activity,
            receiving_actor_id=receiving_actor_id,
        )

    def test_ledger_has_validate_report_entry(self):
        """CaseLedgerEntry with event_type='validate_report' is persisted.

        This is the invariant checked by the CI ratchet test
        ``test_invariant_5_expected_event_types_present[validate_report]``.
        """
        dl = self._make_case_actor_dl()
        ValidateReportReceivedUseCase(
            dl, self._make_validate_event()
        ).execute()

        event_types = _ledger_event_types(dl)
        assert "validate_report" in event_types, (
            "Expected a CaseLedgerEntry with event_type='validate_report'; "
            f"found: {event_types}"
        )

    def test_ledger_entry_links_to_correct_case(self):
        """The persisted ledger entry references the correct case_id."""
        dl = self._make_case_actor_dl()
        ValidateReportReceivedUseCase(
            dl, self._make_validate_event()
        ).execute()

        entries = list(dl.list_objects("CaseLedgerEntry"))
        vr_entries = [
            e
            for e in entries
            if getattr(e, "event_type", "") == "validate_report"
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

        ValidateReportReceivedUseCase(dl, event).execute()

        event_types = _ledger_event_types(dl)
        assert "validate_report" not in event_types, (
            "Non-CaseActor receiving actor must NOT write a validate_report "
            f"ledger entry; found event_types={event_types}"
        )

    def test_sender_rm_state_transitions_to_valid(self):
        """Vendor (sender) RM state is set to VALID even when CaseActor is receiver.

        Verifies the sender_actor_id threading introduced in ADR-0022: nodes
        CheckRMStateValid, CheckRMStateReceivedOrInvalid, and TransitionRMtoValid
        receive ``sender_actor_id=VENDOR_ID`` so the RM transition targets the
        message sender regardless of which actor ``execute_with_setup`` runs
        under (receiving_actor_id=CASE_ACTOR_ID).
        """
        from vultron.core.states.rm import RM
        from vultron.core.use_cases._helpers import _report_phase_status_id

        dl = self._make_case_actor_dl()

        # Register VENDOR as a case participant so TransitionRMtoValid can
        # persist the status record.
        case = dl.read(self.CASE_ID)
        assert isinstance(case, VulnerabilityCase)
        from vultron.core.models.case_actor import VultronCaseActor

        vendor_svc = VultronCaseActor(id_=self.VENDOR_ID)
        dl.save(vendor_svc)
        vendor_p = CaseParticipant(
            attributed_to=self.VENDOR_ID,
            context=self.CASE_ID,
            case_roles=[CVDRole.COORDINATOR],
        )
        dl.create(vendor_p)
        case.case_participants.append(vendor_p.id_)
        case.actor_participant_index[self.VENDOR_ID] = vendor_p.id_
        dl.save(case)

        ValidateReportReceivedUseCase(
            dl,
            self._make_validate_event(),  # actor_id=VENDOR, receiving=CASE_ACTOR
        ).execute()

        valid_id = _report_phase_status_id(
            self.VENDOR_ID, self.REPORT_ID, RM.VALID.value
        )
        assert dl.get("ParticipantStatus", valid_id) is not None, (
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
        from vultron.core.models.case_actor import VultronCaseActor
        from vultron.core.use_cases.triggers._helpers import outbox_ids

        # ── Step 1: vendor_dl — case at RM.RECEIVED ──────────────────────────
        vendor_dl = _make_dl()
        vendor = as_Service(id_=self.VENDOR_ID, name="Vendor Co")
        finder = as_Service(id_=self.FINDER_ID, name="Finder Co")
        vendor_dl.save(vendor)
        vendor_dl.save(finder)

        case, offer = _make_case_at_received(
            vendor_dl, self.VENDOR_ID, self.FINDER_ID, self.REPORT_ID
        )
        case_actor_id = _find_case_actor_id(vendor_dl, case.id_)
        assert (
            case_actor_id is not None
        ), "BT must register a CaseActor Service"

        # ── Step 2: trigger validate-report on vendor_dl ─────────────────────
        before = outbox_ids(self.VENDOR_ID, vendor_dl)
        TriggerService(
            vendor_dl, trigger_activity=TriggerActivityAdapter(vendor_dl)
        ).validate_report(self.VENDOR_ID, offer.id_, None)
        after = outbox_ids(self.VENDOR_ID, vendor_dl)

        new_ids = after - before
        assert (
            new_ids
        ), "validate-report trigger must emit at least one activity"

        # ── Step 3: verify emitted activity targets the CaseActor ────────────
        emitted_id = next(iter(new_ids))
        emitted = vendor_dl.read(emitted_id)
        assert (
            emitted is not None
        ), f"Emitted activity '{emitted_id}' not in vendor_dl"
        to_list = getattr(emitted, "to", None) or []
        assert case_actor_id in to_list, (
            f"Emitted activity should target CaseActor {case_actor_id!r}; "
            f"got to={to_list!r}"
        )

        # ── Step 4: build case_actor_dl with same case identifiers ────────────
        case_actor_dl = _make_dl()

        # The CaseActor Service needs context=case.id_ for _find_case_actor_id.
        ca_svc = VultronCaseActor(id_=case_actor_id, context=case.id_)
        case_actor_dl.save(ca_svc)

        ca_case = VulnerabilityCase(
            id_=case.id_,
            name=case.name or "Test Case",
            attributed_to=case_actor_id,
        )
        ca_case.vulnerability_reports.append(self.REPORT_ID)

        ca_participant = CaseParticipant(
            attributed_to=case_actor_id,
            context=ca_case.id_,
            case_roles=[CVDRole.CASE_MANAGER],
        )
        case_actor_dl.create(ca_participant)
        ca_case.case_participants.append(ca_participant.id_)
        ca_case.actor_participant_index[case_actor_id] = ca_participant.id_
        case_actor_dl.save(ca_case)

        # ── Step 5: dispatch ValidateReportReceivedUseCase on case_actor_dl ───
        report_obj = VultronReport(id_=self.REPORT_ID)
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
            object_=offer_obj,
            context=ca_case.id_,
        )
        event = ValidateReportReceivedEvent(
            semantic_type=MessageSemantics.VALIDATE_REPORT,
            activity_id=emitted_id,
            actor_id=self.VENDOR_ID,
            object_=offer_obj,
            inner_object=report_obj,
            activity=activity,
            receiving_actor_id=case_actor_id,
        )

        ValidateReportReceivedUseCase(case_actor_dl, event).execute()

        # ── Step 6: assert CaseActor ledger has the validate_report entry ─────
        event_types = _ledger_event_types(case_actor_dl)
        assert "validate_report" in event_types, (
            "Expected CaseActor DataLayer to contain a CaseLedgerEntry with "
            f"event_type='validate_report'; found: {event_types}"
        )
