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

``ParticipantStatus`` **used to exist** in two incompatible shapes:

- **core** (``vultron/core/models/participant_status.py``) — nested
  ``rm: RmDimension``, read as ``status.rm.state``.
- **wire** (``vultron/wire/as2/vocab/objects/case_status.py``) — flat
  ``rm_state: RM``, and no ``rm`` attribute at all.

ARCH-25-003 (ADR-0099) collapsed the pair, so there is one shape: the dimension
serializes as its bare state under ``rmState`` (ARCH-25-005), and
``as_ParticipantStatus`` is the core class.  The flat ``rm_state`` spelling was
an input alias for a while, and is now refused (SDO-03-003, #4377).  The tests
below are kept because the *failure modes* they document were real and their
fixes still have to hold — but read them knowing the second shape no longer
exists.

Two silent-failure modes followed from the split, both reproduced here:

1. Core ``CaseParticipant`` had no ``alias_generator``, so a wire-spelled
   (camelCase) ``participantStatuses`` key was an unknown key, silently
   dropped, and ``_init_participant_status_if_empty`` re-seeded a single
   status at ``RM.START`` — losing the whole RM ladder.
2. Reading ``rm`` off a wire-shaped status yielded ``None``, so every core
   reader degraded instead of failing (ARCH-15-001, ARCH-15-002).

Both were made to *raise*, which stopped the loss without fixing its cause.
ADR-0099 fixes the cause: core carries the AS2 spelling (ARCH-25-002), so the key is
read into the right field and the ladder survives; and the second shape is gone,
so there is no mismatch left to raise about. The tests assert the values *arrive*,
which is stronger than asserting a refusal — a refusal is also consistent with the
data being unusable.

The old prohibition on ``alias_generator`` in core-branch types is what
ADR-0099 overturns (ARCH-12-013 now requires it): with the paired class
deleted, there is nowhere else for the spelling to live. The helper guards in
failure mode 2 still hold for an object that genuinely cannot supply a
dimension.  Related: #2264 (RM.START substitution sites).
"""

import pytest
from pydantic import ValidationError

from test.support.participant_status import advance_participant_rm
from vultron.core.models.case_participant import CaseParticipant
from vultron.core.models.dimensions import (
    DDimension,
    RmDimension,
    VfDimension,
)
from vultron.core.models.participant_status import (
    ParticipantStatus,
    participant_status_d_state,
    participant_status_rm_state,
    participant_status_vf_state,
)
from vultron.core.states.cs import CS_d, CS_vf
from vultron.core.states.rm import RM
from vultron.enums.roles import CVDRole
from vultron.errors import VultronValidationError

_ACTOR = "https://example.org/actors/alice"
_CONTEXT = "https://example.org/cases/case-2232"


def _core_participant_with_ladder() -> CaseParticipant:
    """Return a core participant whose RM ladder is START → RECEIVED."""
    participant = CaseParticipant(attributed_to=_ACTOR, context=_CONTEXT)
    advance_participant_rm(
        participant, RM.RECEIVED, actor=_ACTOR, context=_CONTEXT
    )
    assert [s.rm.state.name for s in participant.participant_statuses] == [
        "START",
        "RECEIVED",
    ]
    return participant


# ---------------------------------------------------------------------------
# Failure mode 1 — wire-spelled keys must not be silently dropped
# ---------------------------------------------------------------------------


class TestCaseParticipantReadsWireSpelledKeys:
    """Core ``CaseParticipant`` must read camelCase keys, not drop them."""

    def test_camel_case_participant_statuses_preserves_the_ladder(self):
        """``participantStatuses`` must arrive intact, not reset the ladder.

        Three behaviours in sequence. Originally this validated cleanly and
        returned a participant with a single re-seeded ``RM.START`` status — a
        two-entry ladder silently became one (#2232). The fix made it *raise*,
        which stopped the loss by refusing the payload. ADR-0099 goes the rest of
        the way: the core class carries the AS2 spelling, so the ladder is read.

        Asserting the ladder survives is what both earlier forms were reaching
        for. A rejection test passes equally well when the data is unusable; this
        one does not.
        """
        data = _core_participant_with_ladder().model_dump(mode="json")
        data["participantStatuses"] = data.pop("participant_statuses")

        rebuilt = CaseParticipant.model_validate(data)
        assert [s.rm.state.name for s in rebuilt.participant_statuses] == [
            "START",
            "RECEIVED",
        ], "the RM ladder was truncated (#2232)"

    def test_camel_case_case_roles_is_read(self):
        """The same applies to every other camelCase-spelled core field."""
        participant = _core_participant_with_ladder()
        participant.case_roles = [CVDRole.VENDOR]
        data = participant.model_dump(mode="json")
        data["caseRoles"] = data.pop("case_roles")

        rebuilt = CaseParticipant.model_validate(data)
        assert rebuilt.case_roles == [CVDRole.VENDOR]

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

    def test_wire_class_status_reads_through_the_dimension(self):
        """The wire-layer name reads its RM state through ``rm``.

        This asserted the opposite: that ``as_ParticipantStatus(rm_state=...)``
        had **no** ``rm`` attribute at all, and that reading it had to raise.
        That was true while ``as_ParticipantStatus`` was a separate wire class
        holding a flat field. ARCH-25-003 (ADR-0099) collapsed the pair, so there
        is no shape mismatch left to raise about — the value is simply read.
        The flat ``rm_state`` spelling itself is retired (SDO-03-003, #4377):
        see ``TestParticipantStatusCarriesNoFlatShim``.

        The guard itself is still covered, by
        ``test_raises_on_object_without_rm`` below: an object that genuinely has
        no usable ``rm`` must still raise rather than degrade to ``None``
        (ARCH-15-001, ARCH-15-002). Only the way of *producing* such an object
        changed, because a wire-shaped status is no longer one of them.
        """
        from vultron.wire.as2.vocab.objects.case_status import (
            as_ParticipantStatus,
        )

        status = as_ParticipantStatus(
            context=_CONTEXT, rm=RmDimension(state=RM.RECEIVED)
        )
        assert status.rm.state is RM.RECEIVED
        assert participant_status_rm_state(status) is RM.RECEIVED

    def test_raises_on_object_without_rm(self):
        """An object with no ``rm`` at all must raise, not return None."""

        class _NoRm:
            """Stands in for any object that cannot supply an RM dimension."""

        with pytest.raises(VultronValidationError, match="rm"):
            participant_status_rm_state(_NoRm())

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


class TestRoleDimensionInvariant:
    """Where the VFD role-dimension invariant (ADR-0075) is enforced (#2860).

    ADR-0075 and ``notes/case-state-model.md`` once described a
    ``model_validator`` on ``ParticipantStatus`` that *raises* at construction
    when ``vf`` is set without ``CVDRole.VENDOR`` (or ``d`` without
    ``CVDRole.DEPLOYER``).  That raise was never implemented, and it must not
    be: the receive path builds a core ``ParticipantStatus`` at the wire→core
    boundary (``vultron/wire/as2/extractor/_builders.py``) from the sender's
    *untrusted, self-reported* ``cvd_role``.  A hard raise there would refuse
    the activity at parse, judged by the sender's claimed roles rather than the
    roles the receiver records for it.

    So the model does exactly one thing: it *auto-seeds* the applicable
    dimension for VENDOR/DEPLOYER roles (``_enforce_role_dimension_invariant``).
    It deliberately does **not** reject a stray dimension.  Role authorization
    is enforced where the acting participant's *authoritative* roles are known:

    * trigger/emit path — ``ValidateTriggerTransitionsNode._check_vf_role`` plus
      ``CheckVendorRoleNode`` / ``CheckDeployerRoleNode`` /
      ``CheckNotSoleObserverVfdNode`` in the add-participant-status trigger tree
      (fail-closed; see ``test_vfd_role_guards.py``).
    * receive path — ``participant_status_refusals`` in
      ``participant_status_acceptance.py`` refuses the whole status using the
      participant's authoritative ``case_roles`` (RSH-09-003; see
      ``test_a_vf_value_needs_the_vendor_role`` in
      ``test_participant_status_acceptance.py``).
    """

    def test_vendor_role_auto_seeds_vf_dimension(self):
        """VENDOR role seeds a non-None vf dimension at its initial state."""
        status = ParticipantStatus(context=_CONTEXT, cvd_role=[CVDRole.VENDOR])
        assert status.vf is not None
        assert status.d is None

    def test_deployer_role_auto_seeds_d_dimension(self):
        """DEPLOYER role seeds a non-None d dimension at its initial state."""
        status = ParticipantStatus(
            context=_CONTEXT, cvd_role=[CVDRole.DEPLOYER]
        )
        assert status.d is not None
        assert status.vf is None

    def test_vendor_and_deployer_roles_seed_both_dimensions(self):
        status = ParticipantStatus(
            context=_CONTEXT,
            cvd_role=[CVDRole.VENDOR, CVDRole.DEPLOYER],
        )
        assert status.vf is not None
        assert status.d is not None

    def test_observer_default_seeds_neither_dimension(self):
        """The default OBSERVER role seeds no vf/d dimension."""
        status = ParticipantStatus(context=_CONTEXT)
        assert status.cvd_role == [CVDRole.OBSERVER]
        assert status.vf is None
        assert status.d is None

    @pytest.mark.spec("CSB-15-005")
    def test_stray_vf_on_non_vendor_is_not_rejected_by_the_model(self):
        """A non-VENDOR status carrying vf constructs — the model does not raise.

        Enforcement is delegated to the trigger and receive guards (see class
        docstring). This pins the #2860 decision: a construction-time raise
        here would judge the sender by its claimed roles, not its recorded ones.
        """
        status = ParticipantStatus(
            context=_CONTEXT,
            cvd_role=[CVDRole.OBSERVER],
            vf=VfDimension(state=CS_vf.VF),
        )
        assert status.vf is not None
        assert status.vf.state is CS_vf.VF

    @pytest.mark.spec("CSB-15-006")
    def test_stray_d_on_non_deployer_is_not_rejected_by_the_model(self):
        status = ParticipantStatus(
            context=_CONTEXT,
            cvd_role=[CVDRole.OBSERVER],
            d=DDimension(state=CS_d.D),
        )
        assert status.d is not None
        assert status.d.state is CS_d.D


# ---------------------------------------------------------------------------
# Status carries no consent (ADR-0122)
# ---------------------------------------------------------------------------


class TestStatusCarriesNoConsent:
    """Consent is per embargo on the participant, never on a status."""

    def test_no_consent_or_adherence_attribute(self):
        status = ParticipantStatus(context=_CONTEXT)
        assert not hasattr(status, "consent")
        assert not hasattr(status, "embargo_adherence")

    def test_dump_has_no_consent_keys(self):
        dumped = ParticipantStatus(context=_CONTEXT).model_dump(by_alias=True)
        assert not {
            "consent",
            "embargo_adherence",
            "embargoAdherence",
            "emConsentState",
        } & set(dumped)

    @pytest.mark.parametrize(
        "key",
        ["consent", "embargo_adherence", "em_consent_state", "emConsentState"],
    )
    def test_retired_keys_are_refused(self, key):
        with pytest.raises(ValidationError):
            ParticipantStatus.model_validate({"context": _CONTEXT, key: "X"})


# ---------------------------------------------------------------------------
# The flat rm_state / vf_state / d_state shims are retired (SDO-03-003, #4377)
# ---------------------------------------------------------------------------

_FLAT_SHIMS = [
    ("rm_state", "RECEIVED"),
    ("vf_state", "Vf"),
    ("d_state", "D"),
]


class TestParticipantStatusCarriesNoFlatShim:
    """SDO-03-003 / SDO-03-005: the flat ``*_state`` spellings are gone."""

    @pytest.mark.spec("SDO-03-003")
    @pytest.mark.parametrize("flat", [flat for flat, _ in _FLAT_SHIMS])
    def test_participant_status_defines_no_flat_property(self, flat):
        """No getter, setter or field survives under the flat name (SDO-03-003)."""
        assert not hasattr(ParticipantStatus, flat)
        assert flat not in ParticipantStatus.model_fields
        assert not hasattr(ParticipantStatus(context=_CONTEXT), flat)

    @pytest.mark.spec("SDO-03-003")
    @pytest.mark.spec("SDO-03-005")
    @pytest.mark.parametrize("flat, value", _FLAT_SHIMS)
    def test_flat_input_key_is_refused_by_extra_forbid(self, flat, value):
        """A flat key raises through ``extra="forbid"`` (SDO-03-005)."""
        with pytest.raises(ValidationError) as excinfo:
            ParticipantStatus.model_validate(
                {"context": _CONTEXT, flat: value}
            )
        assert [e["type"] for e in excinfo.value.errors()] == [
            "extra_forbidden"
        ]
        assert [e["loc"] for e in excinfo.value.errors()] == [(flat,)]

    @pytest.mark.parametrize(
        "key, value, read",
        [
            ("rmState", "RECEIVED", lambda s: s.rm.state),
            ("rm", "RECEIVED", lambda s: s.rm.state),
            ("vfState", "Vf", lambda s: s.vf.state),
            ("vf", "Vf", lambda s: s.vf.state),
            ("dState", "D", lambda s: s.d.state),
            ("d", "D", lambda s: s.d.state),
        ],
    )
    def test_wire_and_field_spellings_are_accepted(self, key, value, read):
        """The wire key and the field name stay accepted for each dimension."""
        status = ParticipantStatus.model_validate(
            {"context": _CONTEXT, key: value}
        )
        assert read(status).name == value

    @pytest.mark.spec("SDO-03-005")
    def test_no_reject_guard_validator(self):
        """The refusal is ``extra="forbid"``, not a before-validator (SDO-03-005).

        The one own before-validator is the role/dimension invariant (ADR-0075),
        which seeds a missing ``vf``/``d`` and refuses nothing.
        """
        validators = ParticipantStatus.__pydantic_decorators__.model_validators
        own_before = [
            name
            for name, v in validators.items()
            if v.info.mode == "before"
            and getattr(v.func, "__qualname__", "").startswith(
                "ParticipantStatus."
            )
        ]
        assert own_before == ["_enforce_role_dimension_invariant"]


class TestParticipantStatusBackwardRMValidator:
    """AC-1 (ISSUE-3199): construction-time backward RM step is refused.

    The validator fires only when ``previous_rm_state`` is supplied.  When
    it is absent, construction proceeds as before — no change for existing
    callers.
    """

    def test_no_previous_rm_state_always_passes(self):
        """Without previous_rm_state the validator is a no-op."""
        status = ParticipantStatus(
            context=_CONTEXT,
            rm=RmDimension(state=RM.START),
        )
        assert status.rm.state is RM.START

    def test_valid_forward_step_passes(self):
        """START → RECEIVED is a valid adjacent forward step."""
        status = ParticipantStatus(
            context=_CONTEXT,
            rm=RmDimension(state=RM.RECEIVED),
            previous_rm_state=RM.START,
        )
        assert status.rm.state is RM.RECEIVED

    def test_backward_step_raises(self):
        """RECEIVED → START is backward; construction must raise."""
        with pytest.raises(ValueError, match="Invalid RM transition"):
            ParticipantStatus(
                context=_CONTEXT,
                rm=RmDimension(state=RM.START),
                previous_rm_state=RM.RECEIVED,
            )

    def test_non_adjacent_backward_raises(self):
        """CLOSED → RECEIVED is a backward regression; must be refused."""
        with pytest.raises(ValueError, match="Invalid RM transition"):
            ParticipantStatus(
                context=_CONTEXT,
                rm=RmDimension(state=RM.RECEIVED),
                previous_rm_state=RM.CLOSED,
            )

    def test_force_rm_state_bypasses_check(self):
        """force_rm_state=True suppresses the validator (sanctioned override)."""
        status = ParticipantStatus(
            context=_CONTEXT,
            rm=RmDimension(state=RM.START),
            previous_rm_state=RM.RECEIVED,
            force_rm_state=True,
        )
        assert status.rm.state is RM.START

    def test_excluded_from_serialization(self):
        """previous_rm_state and force_rm_state must not appear in model_dump."""
        status = ParticipantStatus(
            context=_CONTEXT,
            rm=RmDimension(state=RM.RECEIVED),
            previous_rm_state=RM.START,
            force_rm_state=False,
        )
        dumped = status.model_dump()
        assert "previous_rm_state" not in dumped
        assert "force_rm_state" not in dumped

    def test_same_state_passes(self):
        """Asserting the same RM state is not a backward step."""
        status = ParticipantStatus(
            context=_CONTEXT,
            rm=RmDimension(state=RM.RECEIVED),
            previous_rm_state=RM.RECEIVED,
        )
        assert status.rm.state is RM.RECEIVED

    def test_non_adjacent_forward_raises(self):
        """A non-adjacent forward jump (e.g. START → ACCEPTED) must be refused."""
        with pytest.raises(ValueError, match="Invalid RM transition"):
            ParticipantStatus(
                context=_CONTEXT,
                rm=RmDimension(state=RM.ACCEPTED),
                previous_rm_state=RM.START,
            )
