#!/usr/bin/env python
"""
Tests for as_CaseStatus and as_ParticipantStatus empty-string field validation
(CS-08-001).
"""

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

import unittest
from datetime import UTC, datetime

import pytest
from pydantic import ValidationError

from vultron.core.models.case_status import CaseStatus as CoreCaseStatus
from vultron.core.models.participant_status import (
    ParticipantStatus as CoreParticipantStatus,
)
from vultron.enums.roles import CVDRole
from vultron.wire.as2.vocab.objects.case_status import (
    as_CaseStatus,
    as_ParticipantStatus,
)

CASE_ID = "https://example.org/cases/case-001"
ACTOR_ID = "https://example.org/actors/alice"


class TestCaseStatusContextField(unittest.TestCase):
    """Tests for as_CaseStatus.context empty-string validation (CS-08-001)."""

    def test_context_is_required(self):
        """context is required: a status with no case is not a protocol object.

        This asserted the opposite — that ``context=None`` was valid — because the
        deleted wire class was deliberately lenient (ARCH-12-002 made the wire
        branch accept anything so a malformed peer message could still be parsed
        and reported). ADR-0099 detail 3 leaves only the core class, which is
        fail-fast (ARCH-10-001): ``context`` names the case the status belongs to,
        and a status belonging to no case cannot be acted on.
        """
        with pytest.raises(ValidationError):
            as_CaseStatus(context=None)  # type: ignore[arg-type]

    def test_context_non_empty_accepted(self):
        """context with a non-empty string (case ID) is valid."""
        cs = as_CaseStatus(context=CASE_ID)
        self.assertEqual(CASE_ID, cs.context)

    def test_context_empty_string_rejected(self):
        """context must not be an empty string (CS-08-001)."""
        with pytest.raises(ValidationError) as exc_info:
            as_CaseStatus(context="")
        assert "must be a non-empty string" in str(exc_info.value)

    def test_context_whitespace_only_rejected(self):
        """context must not be whitespace-only (CS-08-001)."""
        with pytest.raises(ValidationError) as exc_info:
            as_CaseStatus(context="   ")
        assert "must be a non-empty string" in str(exc_info.value)


class TestParticipantStatusTrackingIdField(unittest.TestCase):
    """Tests for as_ParticipantStatus.tracking_id empty-string validation (CS-08-001)."""

    def test_tracking_id_none_accepted(self):
        """tracking_id=None is valid (optional field)."""
        ps = as_ParticipantStatus(
            attributed_to=ACTOR_ID, context=CASE_ID, tracking_id=None
        )
        self.assertIsNone(ps.tracking_id)

    def test_tracking_id_non_empty_accepted(self):
        """tracking_id with a non-empty string is valid."""
        ps = as_ParticipantStatus(
            attributed_to=ACTOR_ID, context=CASE_ID, tracking_id="TICKET-123"
        )
        self.assertEqual("TICKET-123", ps.tracking_id)

    def test_tracking_id_empty_string_rejected(self):
        """tracking_id must not be an empty string (CS-08-001)."""
        with pytest.raises(ValidationError) as exc_info:
            as_ParticipantStatus(
                attributed_to=ACTOR_ID, context=CASE_ID, tracking_id=""
            )
        assert "must be a non-empty string" in str(exc_info.value)

    def test_tracking_id_whitespace_only_rejected(self):
        """tracking_id must not be whitespace-only (CS-08-001)."""
        with pytest.raises(ValidationError) as exc_info:
            as_ParticipantStatus(
                attributed_to=ACTOR_ID, context=CASE_ID, tracking_id="   "
            )
        assert "must be a non-empty string" in str(exc_info.value)


class TestAs2RoundTripPreservesPublished(unittest.TestCase):
    """An AS2 round-trip must not regenerate published (regression: #2511).

    This tested ``as_CaseStatus.from_core(core)``. There is no ``from_core`` after
    ADR-0099 detail 3 — the wire class *is* the core class — so the projection this
    guarded cannot regenerate anything.

    The risk #2511 describes survives the collapse in a different place: a
    ``published`` timestamp has a ``default_factory``, so any path that rebuilds an
    object from a payload can quietly stamp "now" over the original. Serialising to
    AS2 and reading it back is that path now, so that is what is asserted.
    """

    _FIXED_TIME = datetime(2020, 1, 1, 0, 0, 0, tzinfo=UTC)

    def test_as2_round_trip_preserves_published(self):
        core = CoreCaseStatus(context=CASE_ID, published=self._FIXED_TIME)
        rebuilt = as_CaseStatus.model_validate(
            core.model_dump(by_alias=True, mode="json")
        )
        self.assertEqual(self._FIXED_TIME, rebuilt.published)


class TestCoerceUnknownEnumNames(unittest.TestCase):
    """Unknown enum name strings must raise ValidationError, not KeyError (#2964).

    Pydantic v2 only catches ValueError/AssertionError from field validators.
    Using Enum[name] raises KeyError on unknown inputs, which propagates as a
    500-class error instead of a clean 422 ValidationError.
    """

    def test_vf_state_unknown_raises_validation_error(self):
        """as_ParticipantStatus with bogus vf_state raises ValidationError."""
        with pytest.raises(ValidationError):
            as_ParticipantStatus(
                attributed_to=ACTOR_ID,
                context=CASE_ID,
                vf_state="BOGUS_VF",  # type: ignore[arg-type]
            )

    def test_d_state_unknown_raises_validation_error(self):
        """as_ParticipantStatus with bogus d_state raises ValidationError."""
        with pytest.raises(ValidationError):
            as_ParticipantStatus(
                attributed_to=ACTOR_ID,
                context=CASE_ID,
                d_state="BOGUS_D",  # type: ignore[arg-type]
            )

    def test_pxa_state_unknown_raises_validation_error(self):
        """as_CaseStatus with bogus pxa_state raises ValidationError."""
        with pytest.raises(ValidationError):
            as_CaseStatus(pxa_state="BOGUS_PXA")  # type: ignore[arg-type]

    def test_rm_state_unknown_raises_validation_error(self):
        """as_ParticipantStatus with bogus rm_state raises ValidationError."""
        with pytest.raises(ValidationError):
            as_ParticipantStatus(
                attributed_to=ACTOR_ID,
                context=CASE_ID,
                rm_state="BOGUS_RM",  # type: ignore[arg-type]
            )

    def test_retired_consent_key_raises_validation_error(self):
        """A retired scalar-consent key is refused, not silently dropped (ADR-0122)."""
        for key in ("emConsentState", "em_consent_state", "embargoAdherence"):
            with self.subTest(key=key), pytest.raises(ValidationError):
                as_ParticipantStatus.model_validate(
                    {"attributed_to": ACTOR_ID, "context": CASE_ID, key: "X"}
                )


class TestAs2RoundTripPreservesFields(unittest.TestCase):
    """An AS2 round-trip must preserve published and cvd_role (#2511).

    The ``from_core`` counterpart of ``TestAs2RoundTripPreservesPublished`` — see
    that docstring for why the projection these guarded no longer exists and why
    the round-trip is the successor path.
    """

    _FIXED_TIME = datetime(2020, 1, 1, 0, 0, 0, tzinfo=UTC)

    def test_as2_round_trip_preserves_published(self):
        core = CoreParticipantStatus(
            context=CASE_ID,
            attributed_to=ACTOR_ID,
            published=self._FIXED_TIME,
        )
        rebuilt = as_ParticipantStatus.model_validate(
            core.model_dump(by_alias=True, mode="json")
        )
        self.assertEqual(self._FIXED_TIME, rebuilt.published)

    def test_as2_round_trip_preserves_cvd_role(self):
        expected_roles = [CVDRole.FINDER, CVDRole.REPORTER]
        core = CoreParticipantStatus(
            context=CASE_ID,
            attributed_to=ACTOR_ID,
            cvd_role=expected_roles,
        )
        rebuilt = as_ParticipantStatus.model_validate(
            core.model_dump(by_alias=True, mode="json")
        )
        self.assertEqual(expected_roles, rebuilt.cvd_role)


class TestRetiredVfdKeyRejection(unittest.TestCase):
    """A retired vfd key must raise ValidationError, not escape Pydantic (#2905).

    The per-class ``_reject_retired_vfd_keys`` guard these rows were written
    for is gone (#3921, SDO-03-005): ``extra="forbid"`` alone now refuses the
    key on direct validation, and the parse edge refuses it by name on inbound
    data (MV-11-002).  The rows still pin that the refusal is a Pydantic
    ``ValidationError`` rather than an exception escaping ``model_validate()``.
    """

    def test_vfd_state_snake_raises_validation_error(self):
        """vfd_state in inbound data raises ValidationError, not a raw exception."""
        with pytest.raises(ValidationError):
            as_ParticipantStatus.model_validate(
                {
                    "context": CASE_ID,
                    "attributed_to": ACTOR_ID,
                    "vfd_state": "VFD",
                }
            )

    def test_vfd_state_camel_raises_validation_error(self):
        """vfdState in inbound data raises ValidationError, not a raw exception."""
        with pytest.raises(ValidationError):
            as_ParticipantStatus.model_validate(
                {
                    "context": CASE_ID,
                    "attributed_to": ACTOR_ID,
                    "vfdState": "VFD",
                }
            )

    def test_valid_data_without_vfd_state_constructs_normally(self):
        """Sanity check: valid data without vfd_state still constructs OK."""
        ps = as_ParticipantStatus(
            context=CASE_ID,
            attributed_to=ACTOR_ID,
        )
        self.assertEqual(CASE_ID, ps.context)


if __name__ == "__main__":
    unittest.main()
