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
from vultron.core.models.dimensions import RmDimension, VfdDimension
from vultron.core.models.participant_status import (
    ParticipantStatus,
    participant_status_rm_state,
    participant_status_vfd_state,
)
from vultron.core.states.cs import CS_vfd
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


class TestParticipantStatusVfdStateHelper:
    """``participant_status_vfd_state`` is the canonical VFD-dimension reader.

    The VFD dimension had the identical degrade (``getattr(status, "vfd", None)``
    → substitute ``CS_vfd.vfd``) sitting a few lines from the RM one, so fixing
    only RM would have left the same defect alive one dimension over (#2232).
    """

    def test_returns_state_for_core_shaped_status(self):
        status = ParticipantStatus(
            context=_CONTEXT, vfd=VfdDimension(state=CS_vfd.Vfd)
        )
        assert participant_status_vfd_state(status) is CS_vfd.Vfd

    def test_returns_initial_state_when_unset(self):
        """A core status defaults its VFD dimension — that is not an error."""
        status = ParticipantStatus(context=_CONTEXT)
        assert participant_status_vfd_state(status) is CS_vfd.vfd

    def test_raises_on_wire_shaped_status(self):
        """A flat ``vfd_state`` status has no ``vfd`` — that must raise."""
        from vultron.wire.as2.vocab.objects.case_status import (
            as_ParticipantStatus,
        )

        wire_status = as_ParticipantStatus(
            context=_CONTEXT, vfd_state=CS_vfd.Vfd
        )
        assert getattr(wire_status, "vfd", None) is None

        with pytest.raises(VultronValidationError, match="'vfd' dimension"):
            participant_status_vfd_state(wire_status)

    def test_raises_when_vfd_carries_no_vfd_state(self):
        """A present-but-unusable ``vfd`` must raise rather than substitute."""

        class _Bogus:
            vfd = object()

        with pytest.raises(VultronValidationError, match="no valid VFD state"):
            participant_status_vfd_state(_Bogus())
