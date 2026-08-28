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

"""Regression tests for the canonical ParticipantStatus shape (issue #2232).

``ParticipantStatus`` exists in two incompatible shapes:

- **core** (``vultron/core/models/participant_status.py``) — nested
  ``rm: RmDimension``, read as ``status.rm.state``.
- **wire** (``vultron/wire/as2/vocab/objects/case_status.py``) — flat
  ``rm_state: RM``, and no ``rm`` attribute at all.

Two silent-failure modes followed from that, both reproduced here:

1. Core ``CaseParticipant`` has no ``alias_generator``, so a wire-spelled
   (camelCase) ``participantStatuses`` key was an unknown key, silently
   dropped, and ``_init_participant_status_if_empty`` re-seeded a single
   status at ``RM.START`` — losing the whole RM ladder.
2. Reading ``rm`` off a wire-shaped status yielded ``None``, so every core
   reader degraded instead of failing (ARCH-15-001, ARCH-15-002).

The fix keeps core snake_case-canonical (ARCH-12-003 forbids
``alias_generator=to_camel`` in core-branch types) and makes both failure
modes raise.  Related: #2264 (RM.START substitution sites).
"""

import pytest

from vultron.core.models.case_participant import CaseParticipant
from vultron.core.models.dimensions import (
    DDimension,
    PecDimension,
    RmDimension,
    VfDimension,
)
from vultron.core.states.participant_embargo_consent import PEC
from vultron.core.models.participant_status import (
    ParticipantStatus,
    participant_status_d_state,
    participant_status_rm_state,
    participant_status_vf_state,
)
from vultron.core.states.cs import CS_d, CS_vf
from vultron.core.states.rm import RM
from vultron.errors import VultronValidationError

_ACTOR = "https://example.org/actors/alice"
_CONTEXT = "https://example.org/cases/case-2232"


def _core_participant_with_ladder() -> CaseParticipant:
    """Return a core participant whose RM ladder is START → RECEIVED."""
    participant = CaseParticipant(attributed_to=_ACTOR, context=_CONTEXT)
    participant.append_rm_state(RM.RECEIVED, actor=_ACTOR, context=_CONTEXT)
    assert [s.rm.state.name for s in participant.participant_statuses] == [
        "START",
        "RECEIVED",
    ]
    return participant


# ---------------------------------------------------------------------------
# Failure mode 1 — wire-spelled keys must not be silently dropped
# ---------------------------------------------------------------------------


class TestCaseParticipantRejectsWireSpelledKeys:
    """Core ``CaseParticipant`` must raise, not silently drop, camelCase keys."""

    def test_camel_case_participant_statuses_raises(self):
        """``participantStatuses`` must raise instead of resetting the ladder.

        Before the fix this validated cleanly and returned a participant with
        a single re-seeded ``RM.START`` status — a two-entry ladder silently
        became one entry.
        """
        data = _core_participant_with_ladder().model_dump(mode="json")
        data["participantStatuses"] = data.pop("participant_statuses")

        with pytest.raises(
            VultronValidationError, match="participantStatuses"
        ):
            CaseParticipant.model_validate(data)

    def test_camel_case_case_roles_raises(self):
        """The same silent drop applied to every snake-only core field."""
        data = _core_participant_with_ladder().model_dump(mode="json")
        data["caseRoles"] = data.pop("case_roles")

        with pytest.raises(VultronValidationError, match="caseRoles"):
            CaseParticipant.model_validate(data)

    def test_snake_case_round_trip_is_unaffected(self):
        """The canonical core shape must still round-trip losslessly."""
        original = _core_participant_with_ladder()
        restored = CaseParticipant.model_validate(
            original.model_dump(mode="json")
        )
        assert [s.rm.state.name for s in restored.participant_statuses] == [
            "START",
            "RECEIVED",
        ]

    def test_sanctioned_camel_case_aliases_still_accepted(self):
        """Fields with an explicit camelCase ``validation_alias`` stay valid.

        ``in_reply_to``/``inReplyTo`` and ``id``/``type`` are declared aliases,
        not accidental wire spellings, so the guard must not reject them.
        """
        participant = CaseParticipant.model_validate(
            {
                "id": "urn:uuid:2232-alias-check",
                "type": "CaseParticipant",
                "attributed_to": _ACTOR,
                "context": _CONTEXT,
                "inReplyTo": "urn:uuid:2232-parent",
            }
        )
        assert participant.in_reply_to == "urn:uuid:2232-parent"


# ---------------------------------------------------------------------------
# Failure mode 2 — a shape mismatch must raise, not degrade to None
# ---------------------------------------------------------------------------


class TestParticipantStatusRmStateHelper:
    """``participant_status_rm_state`` is the canonical RM-dimension reader."""

    def test_returns_state_for_core_shaped_status(self):
        status = ParticipantStatus(
            context=_CONTEXT, rm=RmDimension(state=RM.RECEIVED)
        )
        assert participant_status_rm_state(status) is RM.RECEIVED

    def test_raises_on_wire_shaped_status(self):
        """A flat ``rm_state`` status has no ``rm`` — that must raise."""
        from vultron.wire.as2.vocab.objects.case_status import (
            as_ParticipantStatus,
        )

        wire_status = as_ParticipantStatus(
            context=_CONTEXT, rm_state=RM.RECEIVED
        )
        assert getattr(wire_status, "rm", None) is None

        with pytest.raises(VultronValidationError, match="rm"):
            participant_status_rm_state(wire_status)

    def test_raises_when_rm_carries_no_rm_state(self):
        """A present-but-unusable ``rm`` must raise rather than return None.

        ``match=`` pins the *second* guard: without it this test also passes if
        the ``rm is None`` branch fires, so it would not distinguish the two.
        """

        class _Bogus:
            rm = object()

        with pytest.raises(VultronValidationError, match="no valid RM state"):
            participant_status_rm_state(_Bogus())


class TestParticipantStatusVfStateHelper:
    """``participant_status_vf_state`` is the canonical VF-dimension reader."""

    def test_returns_state_for_core_shaped_vendor_status(self):
        status = ParticipantStatus(
            context=_CONTEXT, vf=VfDimension(state=CS_vf.Vf)
        )
        assert participant_status_vf_state(status) is CS_vf.Vf

    def test_returns_none_when_no_vf_dimension(self):
        """A non-vendor status has no vf dimension — returns None, not an error."""
        status = ParticipantStatus(context=_CONTEXT)
        assert participant_status_vf_state(status) is None

    def test_raises_when_vf_carries_no_valid_state(self):
        """A present-but-unusable ``vf`` must raise rather than substitute."""

        class _Bogus:
            vf = object()

        with pytest.raises(VultronValidationError, match="'vf' dimension"):
            participant_status_vf_state(_Bogus())


class TestParticipantStatusDStateHelper:
    """``participant_status_d_state`` is the canonical D-dimension reader."""

    def test_returns_state_for_core_shaped_deployer_status(self):
        status = ParticipantStatus(
            context=_CONTEXT, d=DDimension(state=CS_d.D)
        )
        assert participant_status_d_state(status) is CS_d.D

    def test_returns_none_when_no_d_dimension(self):
        """A non-deployer status has no d dimension — returns None, not an error."""
        status = ParticipantStatus(context=_CONTEXT)
        assert participant_status_d_state(status) is None

    def test_raises_when_d_carries_no_valid_state(self):
        """A present-but-unusable ``d`` must raise rather than substitute."""

        class _Bogus:
            d = object()

        with pytest.raises(VultronValidationError, match="'d' dimension"):
            participant_status_d_state(_Bogus())


# ---------------------------------------------------------------------------
# AC-3 — embargo_adherence is a computed field derived from consent.state
# ---------------------------------------------------------------------------


class TestEmbargoAdherenceComputedField:
    """``embargo_adherence`` is True iff consent.state == SIGNATORY (ADR-0056, CM-18-008)."""

    def test_true_when_signatory(self):
        status = ParticipantStatus(
            context=_CONTEXT,
            consent=PecDimension(state=PEC.SIGNATORY),
        )
        assert status.embargo_adherence is True

    @pytest.mark.parametrize(
        "pec_state",
        [PEC.NO_EMBARGO, PEC.INVITED, PEC.LAPSED, PEC.DECLINED],
    )
    def test_false_when_not_signatory(self, pec_state):
        status = ParticipantStatus(
            context=_CONTEXT,
            consent=PecDimension(state=pec_state),
        )
        assert status.embargo_adherence is False

    def test_false_when_consent_is_none(self):
        status = ParticipantStatus(context=_CONTEXT, consent=None)
        assert status.embargo_adherence is False

    def test_appears_in_model_dump(self):
        status = ParticipantStatus(
            context=_CONTEXT,
            consent=PecDimension(state=PEC.SIGNATORY),
        )
        dumped = status.model_dump()
        assert "embargo_adherence" in dumped
        assert dumped["embargo_adherence"] is True

    def test_cannot_be_set_directly(self):
        """embargo_adherence is read-only; direct assignment must raise."""
        status = ParticipantStatus(context=_CONTEXT, consent=None)
        with pytest.raises((AttributeError, ValueError)):
            status.embargo_adherence = True  # type: ignore[misc]
