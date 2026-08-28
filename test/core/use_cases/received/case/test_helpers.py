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
"""Tests for bootstrap helpers and protocol-error enforcement.

Covers:
  CBT-05-007  Bootstrap Create stores the reporter participant at RM.ACCEPTED
              when a fully inline participant object is provided (CBT-01-008).
  CBT-05-008  Bootstrap Create MUST raise VultronProtocolViolationError when
              a participant arrives as a bare URI string (#2736, #2808).
"""

from typing import Any, cast

import pytest

from vultron.adapters.driven.datalayer_sqlite import SqliteDataLayer
from vultron.errors import VultronProtocolViolationError
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
# CBT-05-007: Reporter participant stored at RM.ACCEPTED when inline (#589)
# ---------------------------------------------------------------------------


@pytest.mark.spec("CBT-05-007")
def test_reporter_participant_stored_at_accepted_when_inline(make_payload):
    """Reporter participant at RM.ACCEPTED in inline payload is preserved (#589).

    CBT-01-008 requires the sender to include the reporter's participant inline
    at RM.ACCEPTED.  CBT-05-008 requires the receiver to reject bare-string
    participants.  This test confirms that when the sender complies (fully
    inline participant at RM.ACCEPTED), the receiver stores it correctly via
    _store_embedded_participants so subsequent Add(ParticipantStatus) calls can
    read it at RM.ACCEPTED.
    """
    from vultron.wire.as2.vocab.objects.case_status import as_ParticipantStatus

    _VENDOR_ID = "https://vendor.example.org/actors/vendor-cbt05007"
    _FINDER_ID = "https://finder.example.org/actors/finder-cbt05007"
    _CASE_ID = "https://example.org/cases/case-cbt05007"
    _REPORT_ID = "https://example.org/reports/report-cbt05007"
    _FINDER_PARTICIPANT_ID = f"{_CASE_ID}/participants/finder-cbt05007"
    _VENDOR_PARTICIPANT_ID = f"{_CASE_ID}/participants/vendor-cbt05007"

    dl = SqliteDataLayer("sqlite:///:memory:", actor_id=_FINDER_ID)
    report = VultronReport(id_=_REPORT_ID, attributed_to=_FINDER_ID)
    dl.create(report)
    link = VultronReportCaseLink(
        report_id=_REPORT_ID,
        trusted_case_creator_id=_VENDOR_ID,
    )
    dl.save(link)
    vendor_participant = as_CaseParticipant(
        case_roles=[CVDRole.CASE_MANAGER],
        id_=_VENDOR_PARTICIPANT_ID,
        attributed_to=_VENDOR_ID,
        context=_CASE_ID,
    )
    finder_participant = as_CaseParticipant(
        id_=_FINDER_PARTICIPANT_ID,
        attributed_to=_FINDER_ID,
        context=_CASE_ID,
        participant_statuses=[
            as_ParticipantStatus(
                context=_CASE_ID,
                attributed_to=_FINDER_ID,
                rm_state=RM.ACCEPTED,
            )
        ],
    )
    case = as_VulnerabilityCase(
        id_=_CASE_ID,
        name="CBT-05-007 inline participant test",
        case_participants=[vendor_participant, finder_participant],
    )
    case.actor_participant_index[_VENDOR_ID] = _VENDOR_PARTICIPANT_ID
    case.actor_participant_index[_FINDER_ID] = _FINDER_PARTICIPANT_ID
    activity = create_case_activity(case, actor=_VENDOR_ID)
    event = make_payload(activity, receiving_actor_id=_FINDER_ID)

    CreateCaseReceivedUseCase(dl, event).execute()

    stored = dl.read(_FINDER_PARTICIPANT_ID)
    assert (
        stored is not None
    ), "Reporter participant must exist after bootstrap"
    statuses = getattr(stored, "participant_statuses", [])
    assert statuses, "Reporter participant must have at least one status"
    assert statuses[-1].rm.state == RM.ACCEPTED, (
        f"Reporter participant must be at RM.ACCEPTED after bootstrap;"
        f" got {statuses[-1].rm.state!r}"
    )


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


@pytest.mark.spec("CBT-05-008")
def test_bootstrap_bare_uri_participant_raises_protocol_error(make_payload):
    """Bootstrap with a bare-URI participant MUST raise VultronProtocolViolationError."""
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
    with pytest.raises(VultronProtocolViolationError):
        CreateCaseReceivedUseCase(dl, event).execute()
