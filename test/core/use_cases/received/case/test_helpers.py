#  Copyright (c) 2026 Carnegie Mellon University and Contributors.
#  - see Contributors.md for a full list of Contributors
#  - see ContributionInstructions.md for information on how you can Contribute
#    to this project
#  Vultron Multiparty Coordinated Vulnerability Disclosure Protocol Prototype
#  is licensed under a MIT (SEI)-style license, please see LICENSE.md
#  distributed with this Software or contact permission@sei.cmu.edu for full
#  terms.
#  Created, in part, with funding and support from the United States Government
#  (see Acknowledgments file). This program may include and/or can make use of
#  certain third party source code, object code, documentation and other files
#  ("Third Party Software"). See LICENSE.md for more details.
#  Carnegie Mellon®, CERT® and CERT Coordination Center® are registered in the
#  U.S. Patent and Trademark Office by Carnegie Mellon University
"""Tests for _ensure_reporter_participant helper and EnsureReporterParticipantAtAcceptedNode
(CBT-05-006/007, #589, #624).

Covers:
  CBT-05-006  Bootstrap Create seeds the reporter participant at RM.ACCEPTED
              when the participant arrives as a bare string ID (fix for #589).
  CBT-05-007  Bootstrap Create upgrades an existing RM.START participant to
              RM.ACCEPTED (fix for #624).

Both requirements are now exercised via ``EnsureReporterParticipantAtAcceptedNode``
(a BT leaf node) called through BTBridge from ``CreateCaseReceivedUseCase._handle_bootstrap``
(BT-06-001, BT-15-001, #943).
"""

from typing import Any, cast

import pytest

from vultron.adapters.driven.datalayer_sqlite import SqliteDataLayer
from vultron.core.models.participant import VultronParticipant
from vultron.core.models.dimensions import RmDimension
from vultron.core.models.participant_status import ParticipantStatus
from vultron.core.models.report import VultronReport
from vultron.core.models.report_case_link import VultronReportCaseLink
from vultron.core.states.rm import RM
from vultron.enums.roles import CVDRole
from vultron.core.use_cases.received.case.create import (
    CreateCaseReceivedUseCase,
)
from vultron.wire.as2.factories import create_case_activity
from vultron.wire.as2.vocab.objects.case_participant import as_CaseParticipant
from vultron.wire.as2.vocab.objects.vulnerability_case import (
    as_VulnerabilityCase,
)

# ---------------------------------------------------------------------------
# CBT-05-006: Reporter participant seeded with RM.ACCEPTED on bootstrap (#589)
# ---------------------------------------------------------------------------


class TestBootstrapCreateReporterParticipant:
    """Bootstrap Create must seed the reporter's participant at RM.ACCEPTED.

    When Create(as_VulnerabilityCase) arrives with participant IDs as bare
    strings, _store_embedded_participants skips them.  The reporter's own
    participant record would then be absent from their DataLayer, causing
    SvcAddParticipantStatusUseCase._resolve_current_participant_state to
    fall back to RM.START — the root cause of #589.

    The fix: _handle_bootstrap calls EnsureReporterParticipantAtAcceptedNode
    via BTBridge, which infers from the reporter's submitted report that they
    have already RM.ACCEPTED and creates the participant record with that state
    if it is not already present (BT-06-001, BT-15-001, #943).
    """

    _VENDOR_ID = "https://vendor.example.org/actors/vendor-589"
    _FINDER_ID = "https://finder.example.org/actors/finder-589"
    _CASE_ID = "https://example.org/cases/case-589"
    _REPORT_ID = "https://example.org/reports/report-589"
    _FINDER_PARTICIPANT_ID = f"{_CASE_ID}/participants/finder-589"
    _VENDOR_PARTICIPANT_ID = f"{_CASE_ID}/participants/vendor-589"

    @pytest.fixture()
    def dl(self):
        return SqliteDataLayer(
            "sqlite:///:memory:",
            # The *receiving* actor's own store (ADR-0041 AC-5): a received
            # Create(VulnerabilityCase) is applied to the receiver's replica.
            actor_id=self._FINDER_ID,
        )

    @pytest.fixture()
    def seeded_dl(self, dl):
        """DataLayer with the Finder's pre-existing report and case link."""
        report = VultronReport(
            id_=self._REPORT_ID,
            attributed_to=self._FINDER_ID,
        )
        dl.create(report)

        link = VultronReportCaseLink(
            report_id=self._REPORT_ID,
            trusted_case_creator_id=self._VENDOR_ID,
        )
        dl.save(link)
        return dl

    @pytest.fixture()
    def case_with_string_participants(self):
        """as_VulnerabilityCase whose participants are bare string IDs.

        This is the common wire representation when the sender serialises the
        domain VultronCase (which stores participant IDs, not objects).
        The fixture also includes a CASE_MANAGER participant inline so that
        the bootstrap trust path extracts a trusted_case_actor_id.
        """
        case_actor_participant = as_CaseParticipant(
            case_roles=[CVDRole.CASE_MANAGER],
            id_=self._VENDOR_PARTICIPANT_ID,
            attributed_to=self._VENDOR_ID,
            context=self._CASE_ID,
        )
        case = as_VulnerabilityCase(
            id_=self._CASE_ID,
            name="Bug #589 regression case",
            case_participants=[
                case_actor_participant,  # inline so CBT-01-003 can extract it
                self._FINDER_PARTICIPANT_ID,  # bare string — typical case
            ],
        )
        case.actor_participant_index[self._VENDOR_ID] = (
            self._VENDOR_PARTICIPANT_ID
        )
        case.actor_participant_index[self._FINDER_ID] = (
            self._FINDER_PARTICIPANT_ID
        )
        return case

    @pytest.fixture()
    def create_event(self, make_payload, case_with_string_participants):
        activity = create_case_activity(
            case_with_string_participants, actor=self._VENDOR_ID
        )
        return make_payload(activity, receiving_actor_id=self._FINDER_ID)

    def test_reporter_participant_created_after_bootstrap(
        self, seeded_dl, create_event
    ):
        """Reporter participant must exist in DataLayer after bootstrap (#589).

        When the bootstrap Create(as_VulnerabilityCase) carries the reporter's
        participant as a bare string ID, the DataLayer must still produce a
        standalone participant record for the reporter so that subsequent
        SvcAddParticipantStatusUseCase calls can read it.
        """
        CreateCaseReceivedUseCase(seeded_dl, create_event).execute()

        stored = seeded_dl.read(self._FINDER_PARTICIPANT_ID)
        assert stored is not None, (
            "Reporter participant must be created in the DataLayer after "
            "bootstrap even when case_participants contains a bare string ID "
            "(regression #589)"
        )

    def test_reporter_participant_has_rm_accepted_after_bootstrap(
        self, seeded_dl, create_event
    ):
        """Reporter participant must start at RM.ACCEPTED after bootstrap.

        The reporter submitted a report — by definition they have accepted the
        vulnerability from their own RM perspective.  The seeded participant
        must reflect this so that _resolve_current_participant_state returns
        RM.ACCEPTED rather than RM.START (#589).
        """
        CreateCaseReceivedUseCase(seeded_dl, create_event).execute()

        stored = seeded_dl.read(self._FINDER_PARTICIPANT_ID)
        assert stored is not None
        statuses = getattr(stored, "participant_statuses", [])
        assert statuses, (
            "Reporter participant must have at least one ParticipantStatus "
            "after bootstrap (#589)"
        )
        latest = statuses[-1]
        rm_state = latest.rm.state if hasattr(latest, "rm") else None
        assert rm_state == RM.ACCEPTED, (
            f"Reporter participant must have rm_state=RM.ACCEPTED after "
            f"bootstrap; got {rm_state!r} (#589)"
        )


# ---------------------------------------------------------------------------
# CBT-05-007: Reporter participant upgraded from RM.START to RM.ACCEPTED (#624)
# ---------------------------------------------------------------------------


@pytest.mark.spec("CBT-05-007")
class TestBootstrapReporterUpgradesFromStart:
    """Bootstrap Create upgrades an existing RM.START participant to RM.ACCEPTED.

    When ``_store_embedded_participants`` stores the wire-layer snapshot, it may
    seed the reporter's participant with ``rm_state=RM.START`` (the wire default).
    ``EnsureReporterParticipantAtAcceptedNode`` must detect this and upgrade the
    participant to ``RM.ACCEPTED`` via BTBridge (#624, BT-06-001, BT-15-001,
    #943).
    """

    _VENDOR_ID = "https://vendor.example.org/actors/vendor-624"
    _FINDER_ID = "https://finder.example.org/actors/finder-624"
    _CASE_ID = "https://example.org/cases/case-624"
    _REPORT_ID = "https://example.org/reports/report-624"
    _FINDER_PARTICIPANT_ID = f"{_CASE_ID}/participants/finder-624"
    _VENDOR_PARTICIPANT_ID = f"{_CASE_ID}/participants/vendor-624"

    @pytest.fixture()
    def dl(self):
        return SqliteDataLayer(
            "sqlite:///:memory:",
            # The *receiving* actor's own store (ADR-0041 AC-5): a received
            # Create(VulnerabilityCase) is applied to the receiver's replica.
            actor_id=self._FINDER_ID,
        )

    @pytest.fixture()
    def base_dl(self, dl):
        """DataLayer with report and link pre-seeded."""
        report = VultronReport(
            id_=self._REPORT_ID,
            attributed_to=self._FINDER_ID,
        )
        dl.create(report)

        link = VultronReportCaseLink(
            report_id=self._REPORT_ID,
            trusted_case_creator_id=self._VENDOR_ID,
        )
        dl.save(link)
        return dl

    @pytest.fixture()
    def case_with_string_participants(self):
        case_actor_participant = as_CaseParticipant(
            case_roles=[CVDRole.CASE_MANAGER],
            id_=self._VENDOR_PARTICIPANT_ID,
            attributed_to=self._VENDOR_ID,
            context=self._CASE_ID,
        )
        case = as_VulnerabilityCase(
            id_=self._CASE_ID,
            name="Bug #624 regression case",
            case_participants=[
                case_actor_participant,
                self._FINDER_PARTICIPANT_ID,  # bare string
            ],
        )
        case.actor_participant_index[self._VENDOR_ID] = (
            self._VENDOR_PARTICIPANT_ID
        )
        case.actor_participant_index[self._FINDER_ID] = (
            self._FINDER_PARTICIPANT_ID
        )
        return case

    def _create_event(self, make_payload, case):
        activity = create_case_activity(case, actor=self._VENDOR_ID)
        return make_payload(activity, receiving_actor_id=self._FINDER_ID)

    def _pre_seed_participant(self, dl, rm_state: RM) -> VultronParticipant:
        """Store a finder participant at the given rm_state before bootstrap."""
        status = ParticipantStatus(
            rm=RmDimension(state=rm_state),
            context=self._CASE_ID,
            attributed_to=self._FINDER_ID,
        )
        participant = VultronParticipant(
            id_=self._FINDER_PARTICIPANT_ID,
            attributed_to=self._FINDER_ID,
            context=self._CASE_ID,
            participant_statuses=[status],
        )
        dl.create(participant)
        return participant

    def test_reporter_participant_upgraded_from_start_to_accepted(
        self, base_dl, make_payload, case_with_string_participants
    ):
        """Reporter participant at RM.START must be upgraded to RM.ACCEPTED (#624).

        Pre-condition: reporter's participant is already in the DataLayer at
        RM.START (seeded by _store_embedded_participants or a prior bootstrap).
        Post-condition: after CreateCaseReceivedUseCase, the participant's latest
        rm_state is RM.ACCEPTED.
        """
        self._pre_seed_participant(base_dl, RM.START)
        event = self._create_event(make_payload, case_with_string_participants)

        CreateCaseReceivedUseCase(base_dl, event).execute()

        stored = base_dl.read(self._FINDER_PARTICIPANT_ID)
        assert stored is not None
        statuses = getattr(stored, "participant_statuses", [])
        assert statuses, "Reporter participant must have at least one status"
        latest_rm = statuses[-1].rm.state
        assert latest_rm == RM.ACCEPTED, (
            f"Reporter participant must be upgraded to RM.ACCEPTED from "
            f"RM.START; got {latest_rm!r} (#624)"
        )

    def test_reporter_participant_noop_if_already_accepted(
        self, base_dl, make_payload, case_with_string_participants
    ):
        """Reporter participant already at RM.ACCEPTED must not be modified (#624)."""
        self._pre_seed_participant(base_dl, RM.ACCEPTED)
        event = self._create_event(make_payload, case_with_string_participants)

        CreateCaseReceivedUseCase(base_dl, event).execute()

        stored = base_dl.read(self._FINDER_PARTICIPANT_ID)
        assert stored is not None
        statuses = getattr(stored, "participant_statuses", [])
        assert len(statuses) == 1, (
            "Reporter participant already at RM.ACCEPTED must not gain extra "
            f"statuses; got {len(statuses)} (#624)"
        )
        assert statuses[0].rm.state == RM.ACCEPTED

    def test_reporter_participant_noop_if_already_closed(
        self, base_dl, make_payload, case_with_string_participants
    ):
        """Reporter participant already at RM.CLOSED must not be downgraded (#624)."""
        self._pre_seed_participant(base_dl, RM.CLOSED)
        event = self._create_event(make_payload, case_with_string_participants)

        CreateCaseReceivedUseCase(base_dl, event).execute()

        stored = base_dl.read(self._FINDER_PARTICIPANT_ID)
        assert stored is not None
        statuses = getattr(stored, "participant_statuses", [])
        assert len(statuses) == 1, (
            "Reporter participant at RM.CLOSED must not gain extra statuses "
            f"(it is already beyond ACCEPTED); got {len(statuses)} (#624)"
        )
        assert statuses[0].rm.state == RM.CLOSED

    def test_reporter_participant_noop_if_at_invalid(
        self, base_dl, make_payload, case_with_string_participants
    ):
        """Reporter participant at RM.INVALID must not be upgraded to ACCEPTED.

        RM.INVALID is a validation-failure branch: the report was determined
        invalid.  Bypassing re-validation by jumping directly to RM.ACCEPTED
        violates SM-04-001 (explicit precondition guard before state write).
        The participant must remain at RM.INVALID (#2481).
        """
        self._pre_seed_participant(base_dl, RM.INVALID)
        event = self._create_event(make_payload, case_with_string_participants)

        CreateCaseReceivedUseCase(base_dl, event).execute()

        stored = base_dl.read(self._FINDER_PARTICIPANT_ID)
        assert stored is not None
        statuses = getattr(stored, "participant_statuses", [])
        assert len(statuses) == 1, (
            "Reporter participant at RM.INVALID must not gain extra statuses "
            f"(upgrade to ACCEPTED must be blocked); got {len(statuses)} (#2481)"
        )
        assert statuses[0].rm.state == RM.INVALID


# ---------------------------------------------------------------------------
# _upgrade_participant_to_accepted must be a silent no-op on RM.ACCEPTED
# (issue #2763)
# ---------------------------------------------------------------------------


class TestUpgradeParticipantIdempotencyWhenAlreadyAccepted:
    """``_upgrade_participant_to_accepted`` must be a silent no-op when already at RM.ACCEPTED.

    Regression for #2763: when ``latest_rm == RM.ACCEPTED``,
    ``is_valid_rm_transition(RM.ACCEPTED, RM.ACCEPTED)`` is ``False`` (no
    self-loop).  Before the fix, the SM-04-001 guard fired a misleading
    ``WARNING``, filling logs on every ledger replay and masking genuine
    SM-04-001 violations.

    The function must:
    - log nothing at WARNING or above,
    - write no new DataLayer record,

    when called with ``latest_rm == RM.ACCEPTED``.
    """

    _ACTOR_ID = "https://finder.example.org/actors/finder-2763"
    _CASE_ID = "https://example.org/cases/case-2763"
    _PARTICIPANT_ID = f"{_CASE_ID}/participants/finder-2763"

    @pytest.fixture()
    def dl(self):
        return SqliteDataLayer("sqlite:///:memory:", actor_id=self._ACTOR_ID)

    @pytest.fixture()
    def participant_at_accepted(self, dl):
        """Participant already at RM.ACCEPTED stored in the DataLayer."""
        status = ParticipantStatus(
            rm=RmDimension(state=RM.ACCEPTED),
            context=self._CASE_ID,
            attributed_to=self._ACTOR_ID,
        )
        participant = VultronParticipant(
            id_=self._PARTICIPANT_ID,
            attributed_to=self._ACTOR_ID,
            context=self._CASE_ID,
            participant_statuses=[status],
        )
        dl.create(participant)
        return participant

    def test_no_warning_and_no_extra_status_when_already_accepted(
        self, dl, participant_at_accepted, caplog
    ):
        """No WARNING logged and no extra status written on idempotent replay (#2763).

        SM-04-001 guard must not fire when ``latest_rm == RM.ACCEPTED`` —
        the participant is already at the target state, so there is no
        illegal transition.
        """
        import logging

        from vultron.core.behaviors.case.nodes.participant.common import (
            _upgrade_participant_to_accepted,
        )

        with caplog.at_level(logging.WARNING):
            _upgrade_participant_to_accepted(
                dl=dl,
                existing=participant_at_accepted,
                participant_id=self._PARTICIPANT_ID,
                case_id=self._CASE_ID,
                reporter_actor_id=self._ACTOR_ID,
                latest_rm=RM.ACCEPTED,
            )

        warning_messages = [
            r.message for r in caplog.records if r.levelno >= logging.WARNING
        ]
        assert not warning_messages, (
            "No WARNING must be logged when participant is already at "
            f"RM.ACCEPTED; got: {warning_messages!r} (#2763)"
        )

        stored = dl.read(self._PARTICIPANT_ID)
        assert stored is not None
        statuses = getattr(stored, "participant_statuses", [])
        assert len(statuses) == 1, (
            "No extra status must be written when participant is already "
            f"at RM.ACCEPTED; got {len(statuses)} status(es) (#2763)"
        )
        assert statuses[0].rm.state == RM.ACCEPTED


# ---------------------------------------------------------------------------
# RM-regression guard must not go inert on a shape mismatch (issue #2232)
# ---------------------------------------------------------------------------


class TestParticipantRmStateShapeGuard:
    """``_participant_rm_state`` must raise on a wire-shaped status.

    Regression for #2232: on a wire-shaped participant ``getattr(status, "rm")``
    was ``None``, so ``_participant_rm_state`` returned ``None`` and
    ``_would_regress_participant`` returned ``False`` — the RM-rollback guard
    shipped inert.  A shape mismatch must raise (ARCH-15-001, ARCH-15-002); an
    empty status list legitimately stays ``None``.
    """

    _CONTEXT = "https://example.org/cases/case-2232"

    def test_returns_latest_state_for_core_shaped_participant(self):
        from vultron.core.models.case_participant import CaseParticipant
        from vultron.core.use_cases.received.case._helpers import (
            _participant_rm_state,
        )

        actor = "https://example.org/actors/alice"
        participant = CaseParticipant(
            attributed_to=actor, context=self._CONTEXT
        )
        participant.append_rm_state(
            RM.RECEIVED, actor=actor, context=self._CONTEXT
        )
        assert _participant_rm_state(participant) is RM.RECEIVED

    def test_returns_none_for_empty_status_list(self):
        """Lenient where absence is legitimate (notes/domain-validation.md)."""
        from vultron.core.use_cases.received.case._helpers import (
            _participant_rm_state,
        )

        class _NoStatuses:
            participant_statuses: list = []

        assert _participant_rm_state(_NoStatuses()) is None

    def test_raises_on_wire_shaped_participant(self):
        from vultron.core.use_cases.received.case._helpers import (
            _participant_rm_state,
        )
        from vultron.errors import VultronValidationError
        from vultron.wire.as2.vocab.objects.case_participant import (
            as_CaseParticipant,
        )

        wire_participant = as_CaseParticipant(
            attributed_to="https://example.org/actors/vendor",
            context=self._CONTEXT,
        )
        latest = wire_participant.participant_statuses[-1]
        assert getattr(latest, "rm", None) is None

        with pytest.raises(VultronValidationError):
            _participant_rm_state(wire_participant)


# ---------------------------------------------------------------------------
# Wire-shaped ingress must not abort the received-case path (issue #2232)
# ---------------------------------------------------------------------------


class TestStoreEmbeddedParticipantsProjectsWireIngress:
    """``_store_embedded_participants`` must survive a wire-shaped snapshot.

    A received ``VulnerabilityCase`` is deserialised from AS2, so its embedded
    participants are wire objects with a flat ``rm_state``.  Making
    ``_participant_rm_state`` raise on that shape (issue #2232) turned every
    inbound ``Announce(VulnerabilityCase)`` into an aborted behavior tree unless
    the participants are projected to core *at this ingress boundary* first.

    These tests pin the projection, not the raise: the raise is correct for a
    corrupt stored row, and wrong as a response to legitimate inbound data.
    """

    _CASE_ID = "https://example.org/cases/case-2232-ingress"
    _ACTOR_ID = "https://vendor.example.org/actors/vendor-2232"
    _PARTICIPANT_ID = f"{_CASE_ID}/participants/vendor-2232"

    @pytest.fixture()
    def dl(self):
        return SqliteDataLayer(
            "sqlite:///:memory:",
            # The *receiving* actor's own store (ADR-0041 AC-5): a received
            # Create(VulnerabilityCase) is applied to the receiver's replica.
            actor_id=self._ACTOR_ID,
        )

    def _wire_case(self, rm_state: RM) -> as_VulnerabilityCase:
        """A received-shaped case carrying one wire participant at *rm_state*."""
        from vultron.wire.as2.vocab.objects.case_status import (
            as_ParticipantStatus,
        )

        wire_participant = as_CaseParticipant(
            id_=self._PARTICIPANT_ID,
            attributed_to=self._ACTOR_ID,
            context=self._CASE_ID,
            participant_statuses=[
                as_ParticipantStatus(
                    context=self._CASE_ID,
                    attributed_to=self._ACTOR_ID,
                    rm_state=rm_state,
                )
            ],
        )
        assert (
            getattr(wire_participant.participant_statuses[-1], "rm", None)
            is None
        )
        return as_VulnerabilityCase(
            id_=self._CASE_ID,
            name="Bug #2232 ingress case",
            case_participants=[wire_participant],
        )

    def _seed_core_participant(self, dl, rm_state: RM) -> None:
        """Store a core-shaped participant at *rm_state* before ingress."""
        status = ParticipantStatus(
            rm=RmDimension(state=rm_state),
            context=self._CASE_ID,
            attributed_to=self._ACTOR_ID,
        )
        dl.create(
            VultronParticipant(
                id_=self._PARTICIPANT_ID,
                attributed_to=self._ACTOR_ID,
                context=self._CASE_ID,
                participant_statuses=[status],
            )
        )

    def test_wire_shaped_participant_is_stored_in_the_core_shape(self, dl):
        """No raise escapes, and the persisted row is core-shaped."""
        from vultron.core.models.case_participant import CaseParticipant
        from vultron.core.use_cases.received.case._helpers import (
            _store_embedded_participants,
        )

        case = self._wire_case(RM.RECEIVED)

        # The annotation says core ``VulnerabilityCase``, but the received
        # path really hands it the deserialised wire case — that mismatch is
        # exactly the shape duality under test (issue #2232).
        _store_embedded_participants(cast(Any, case), dl, self._CASE_ID)

        stored = dl.read(self._PARTICIPANT_ID)
        assert isinstance(stored, CaseParticipant), (
            "ingress must persist the canonical core type so dl.read() returns"
            " a core object (DL-05-001)"
        )
        latest = stored.participant_statuses[-1]
        assert latest.rm.state == RM.RECEIVED
        assert not hasattr(latest, "rm_state")

    def test_regression_guard_still_protects_a_local_core_participant(
        self, dl
    ):
        """A behind-the-times wire snapshot must not roll local RM back.

        This is the case that exposed the ingress gap: the guard has to compare
        a wire-shaped incoming against a core-shaped stored row, so it only
        works once both sides go through the same projection.
        """
        from vultron.core.use_cases.received.case._helpers import (
            _store_embedded_participants,
        )

        self._seed_core_participant(dl, RM.ACCEPTED)
        case = self._wire_case(RM.RECEIVED)

        # The annotation says core ``VulnerabilityCase``, but the received
        # path really hands it the deserialised wire case — that mismatch is
        # exactly the shape duality under test (issue #2232).
        _store_embedded_participants(cast(Any, case), dl, self._CASE_ID)

        stored = dl.read(self._PARTICIPANT_ID)
        assert stored is not None
        latest_rm = stored.participant_statuses[-1].rm.state
        assert latest_rm == RM.ACCEPTED, (
            "local RM.ACCEPTED must survive an incoming RM.RECEIVED snapshot;"
            f" got {latest_rm!r} (issue #2232)"
        )

    def test_forward_wire_snapshot_still_upgrades_local_participant(self, dl):
        """A forward snapshot is applied — the guard is not blanket-inert."""
        from vultron.core.use_cases.received.case._helpers import (
            _store_embedded_participants,
        )

        self._seed_core_participant(dl, RM.RECEIVED)
        case = self._wire_case(RM.VALID)

        # The annotation says core ``VulnerabilityCase``, but the received
        # path really hands it the deserialised wire case — that mismatch is
        # exactly the shape duality under test (issue #2232).
        _store_embedded_participants(cast(Any, case), dl, self._CASE_ID)

        stored = dl.read(self._PARTICIPANT_ID)
        assert stored is not None
        assert stored.participant_statuses[-1].rm.state == RM.VALID

    def test_unprojectable_participant_is_skipped_not_fatal(self, caplog):
        """One malformed participant must not cost the receiver the whole case.

        The HTTP inbox re-queues on exception, so letting a projection failure
        propagate would turn the activity into an undrainable poison message.
        """
        import logging

        from vultron.core.use_cases.received.case._helpers import (
            _project_to_core_participant,
        )

        class _NoToCore:
            """Neither a core participant nor a wire projection."""

            id_ = "https://example.org/cases/x/participants/bogus"

        with caplog.at_level(logging.ERROR):
            result = _project_to_core_participant(_NoToCore(), _NoToCore.id_)

        assert result is None
        assert "cannot be projected" in caplog.text


# ---------------------------------------------------------------------------
# CBT-05-008: Bare-URI participant MUST raise a protocol error, not silently
# fall back to domain-knowledge inference.  Tracked by #2736.
# ---------------------------------------------------------------------------


@pytest.mark.xfail(
    strict=True,
    reason=(
        "CBT-05-008: receiver MUST raise a protocol error for a bare-URI "
        "participant — NOT fall back to domain-knowledge inference. "
        "Tracked by #2736."
    ),
)
@pytest.mark.spec("CBT-05-008")
def test_bootstrap_bare_uri_participant_raises_protocol_error(make_payload):
    """Bootstrap with a bare-URI participant MUST raise a protocol error."""
    _VENDOR_ID = "https://vendor.example.org/actors/vendor-cbt05008"
    _FINDER_ID = "https://finder.example.org/actors/finder-cbt05008"
    _CASE_ID = "https://example.org/cases/case-cbt05008"
    _REPORT_ID = "https://example.org/reports/report-cbt05008"
    _FINDER_PARTICIPANT_ID = f"{_CASE_ID}/participants/finder-cbt05008"
    _VENDOR_PARTICIPANT_ID = f"{_CASE_ID}/participants/vendor-cbt05008"

    dl = SqliteDataLayer("sqlite:///:memory:", actor_id=_FINDER_ID)
    report = VultronReport(id_=_REPORT_ID, attributed_to=_FINDER_ID)
    dl.create(report)
    link = VultronReportCaseLink(
        report_id=_REPORT_ID,
        trusted_case_creator_id=_VENDOR_ID,
    )
    dl.save(link)
    case_actor_participant = as_CaseParticipant(
        case_roles=[CVDRole.CASE_MANAGER],
        id_=_VENDOR_PARTICIPANT_ID,
        attributed_to=_VENDOR_ID,
        context=_CASE_ID,
    )
    case = as_VulnerabilityCase(
        id_=_CASE_ID,
        name="CBT-05-008 bare URI test",
        case_participants=[
            case_actor_participant,
            _FINDER_PARTICIPANT_ID,  # bare string — protocol violation
        ],
    )
    case.actor_participant_index[_VENDOR_ID] = _VENDOR_PARTICIPANT_ID
    case.actor_participant_index[_FINDER_ID] = _FINDER_PARTICIPANT_ID
    activity = create_case_activity(case, actor=_VENDOR_ID)
    event = make_payload(activity, receiving_actor_id=_FINDER_ID)
    with pytest.raises(Exception):  # MUST raise a protocol error
        CreateCaseReceivedUseCase(dl, event).execute()
