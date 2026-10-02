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
"""Tests for seeding a participant case replica from a received snapshot.

Covers the RM-regression guard (#2232) and the wire→core participant ingress
of :mod:`vultron.core.services.case_replica_seeding`.
"""

from typing import Any, cast

import pytest

from vultron.adapters.driven.datalayer_sqlite import SqliteDataLayer
from vultron.core.models.case_participant import CaseParticipant
from vultron.core.models.dimensions import (
    RmDimension,
)
from vultron.core.models.participant_status import ParticipantStatus
from vultron.core.states.rm import RM
from vultron.wire.as2.vocab.objects.case_participant import as_CaseParticipant
from vultron.wire.as2.vocab.objects.vulnerability_case import (
    as_VulnerabilityCase,
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
        from test.support.participant_status import advance_participant_rm
        from vultron.core.models.case_participant import CaseParticipant
        from vultron.core.services.case_replica_seeding import (
            _participant_rm_state,
        )

        actor = "https://example.org/actors/alice"
        participant = CaseParticipant(
            attributed_to=actor, context=self._CONTEXT
        )
        advance_participant_rm(
            participant, RM.RECEIVED, actor=actor, context=self._CONTEXT
        )
        assert _participant_rm_state(participant) is RM.RECEIVED

    def test_returns_none_for_empty_status_list(self):
        """Lenient where absence is legitimate (notes/domain-validation.md)."""
        from vultron.core.services.case_replica_seeding import (
            _participant_rm_state,
        )

        class _NoStatuses:
            participant_statuses: list = []

        assert _participant_rm_state(_NoStatuses()) is None

    def test_reads_the_rm_state_of_an_as_prefixed_participant(self):
        """An ``as_CaseParticipant`` now carries a readable RM dimension.

        This asserted the opposite: that the wire class's nested status had no
        ``rm`` at all, and that reading it raised. ADR-0099 detail 3 collapses the
        pair, so ``as_CaseParticipant`` *is* ``CaseParticipant`` and its seeded
        status carries a real dimension — there is no wire shape left to refuse.

        The helper's guard is still covered by
        ``test_returns_none_when_there_are_no_statuses`` above and by
        ``test_participant_status_shape``, for objects that genuinely cannot supply
        a dimension.
        """
        from vultron.core.services.case_replica_seeding import (
            _participant_rm_state,
        )
        from vultron.core.states.rm import RM
        from vultron.wire.as2.vocab.objects.case_participant import (
            as_CaseParticipant,
        )

        wire_participant = as_CaseParticipant(
            attributed_to="https://example.org/actors/vendor",
            context=self._CONTEXT,
        )
        latest = wire_participant.participant_statuses[-1]
        assert latest.rm.state is RM.START

        assert _participant_rm_state(wire_participant) is RM.START


# ---------------------------------------------------------------------------
# Wire-shaped ingress must not abort the received-case path (issue #2232)
# ---------------------------------------------------------------------------


class TestStoreEmbeddedParticipantsProjectsWireIngress:
    """``store_embedded_participants`` must survive a wire-shaped snapshot.

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
                    rm=RmDimension(state=rm_state),
                )
            ],
        )
        # The nested status now carries a real dimension: as_ParticipantStatus is
        # ParticipantStatus (ADR-0099 detail 3), and the flat ``rm_state`` kwarg is
        # an alias of it (detail 5).  This previously asserted ``rm`` was absent,
        # which was the whole reason ingress needed projecting.
        assert wire_participant.participant_statuses[-1].rm.state == rm_state
        return as_VulnerabilityCase.model_construct(
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
            CaseParticipant(
                id_=self._PARTICIPANT_ID,
                attributed_to=self._ACTOR_ID,
                context=self._CASE_ID,
                participant_statuses=[status],
            )
        )

    def test_wire_shaped_participant_is_stored_in_the_core_shape(self, dl):
        """No raise escapes, and the persisted row is core-shaped."""
        from vultron.core.models.case_participant import CaseParticipant
        from vultron.core.services.case_replica_seeding import (
            store_embedded_participants,
        )

        case = self._wire_case(RM.RECEIVED)

        # The annotation says core ``VulnerabilityCase``, but the received
        # path really hands it the deserialised wire case — that mismatch is
        # exactly the shape duality under test (issue #2232).
        store_embedded_participants(cast(Any, case), dl, self._CASE_ID)

        stored = dl.read(self._PARTICIPANT_ID)
        assert isinstance(stored, CaseParticipant), (
            "ingress must persist the canonical core type so dl.read() returns"
            " a core object (DL-05-001)"
        )
        latest = stored.participant_statuses[-1]
        assert latest.rm.state == RM.RECEIVED
        # ``not hasattr(latest, "rm_state")`` used to stand in for "this is the
        # core shape, not the wire one". That proxy is retired: ``rm_state`` is now
        # a deliberate read/write view onto the dimension (ADR-0099 detail 5), so
        # its presence says nothing about shape. The shape itself is asserted
        # directly by the isinstance check above; what is worth adding is that the
        # view and the dimension cannot disagree.
        assert latest.rm_state == latest.rm.state

    def test_regression_guard_still_protects_a_local_core_participant(
        self, dl
    ):
        """A behind-the-times wire snapshot must not roll local RM back.

        This is the case that exposed the ingress gap: the guard has to compare
        a wire-shaped incoming against a core-shaped stored row, so it only
        works once both sides go through the same projection.
        """
        from vultron.core.services.case_replica_seeding import (
            store_embedded_participants,
        )

        self._seed_core_participant(dl, RM.ACCEPTED)
        case = self._wire_case(RM.RECEIVED)

        # The annotation says core ``VulnerabilityCase``, but the received
        # path really hands it the deserialised wire case — that mismatch is
        # exactly the shape duality under test (issue #2232).
        store_embedded_participants(cast(Any, case), dl, self._CASE_ID)

        stored = dl.read(self._PARTICIPANT_ID)
        assert stored is not None
        latest_rm = stored.participant_statuses[-1].rm.state
        assert latest_rm == RM.ACCEPTED, (
            "local RM.ACCEPTED must survive an incoming RM.RECEIVED snapshot;"
            f" got {latest_rm!r} (issue #2232)"
        )

    def test_forward_wire_snapshot_still_upgrades_local_participant(self, dl):
        """A forward snapshot is applied — the guard is not blanket-inert."""
        from vultron.core.services.case_replica_seeding import (
            store_embedded_participants,
        )

        self._seed_core_participant(dl, RM.RECEIVED)
        case = self._wire_case(RM.VALID)

        # The annotation says core ``VulnerabilityCase``, but the received
        # path really hands it the deserialised wire case — that mismatch is
        # exactly the shape duality under test (issue #2232).
        store_embedded_participants(cast(Any, case), dl, self._CASE_ID)

        stored = dl.read(self._PARTICIPANT_ID)
        assert stored is not None
        assert stored.participant_statuses[-1].rm.state == RM.VALID

    def test_unprojectable_participant_is_skipped_not_fatal(self, caplog):
        """One malformed participant must not cost the receiver the whole case.

        The HTTP inbox re-queues on exception, so letting a projection failure
        propagate would turn the activity into an undrainable poison message.
        """
        import logging

        from vultron.core.services.case_replica_seeding import (
            _project_to_core_participant,
        )

        class _NotAParticipant:
            """Carries an id but is not a core ``CaseParticipant``."""

            id_ = "https://example.org/cases/x/participants/bogus"

        with caplog.at_level(logging.ERROR):
            result = _project_to_core_participant(
                _NotAParticipant(), _NotAParticipant.id_
            )

        assert result is None
        assert "cannot be projected" in caplog.text
