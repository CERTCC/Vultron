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
from datetime import datetime, timezone

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

    def test_context_none_accepted(self):
        """context=None is valid (optional field)."""
        cs = as_CaseStatus(context=None)
        self.assertIsNone(cs.context)

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


class TestFromCorePreservesPublished(unittest.TestCase):
    """from_core must not regenerate published (regression: issue #2511)."""

    _FIXED_TIME = datetime(2020, 1, 1, 0, 0, 0, tzinfo=timezone.utc)

    def test_as_case_status_from_core_preserves_published(self):
        core = CoreCaseStatus(context=CASE_ID, published=self._FIXED_TIME)
        wire = as_CaseStatus.from_core(core)
        self.assertEqual(self._FIXED_TIME, wire.published)

    def test_as_participant_status_from_core_preserves_published(self):
        core = CoreParticipantStatus(
            context=CASE_ID,
            attributed_to=ACTOR_ID,
            published=self._FIXED_TIME,
        )
        wire = as_ParticipantStatus.from_core(core)
        self.assertEqual(self._FIXED_TIME, wire.published)

    def test_as_participant_status_from_core_preserves_cvd_role(self):
        """model_dump() produces cvd_role (snake_case); verify it round-trips."""
        expected_roles = [CVDRole.FINDER, CVDRole.REPORTER]
        core = CoreParticipantStatus(
            context=CASE_ID,
            attributed_to=ACTOR_ID,
            cvd_role=expected_roles,
        )
        wire = as_ParticipantStatus.from_core(core)
        self.assertEqual(expected_roles, wire.cvd_role)


class TestRetiredVfdKeyRejection(unittest.TestCase):
    """_reject_retired_vfd_keys must raise ValidationError, not a raw
    VultronProtocolViolationError that escapes Pydantic (issue #2905).

    Pydantic only absorbs ValueError/TypeError/AssertionError from validators.
    When the validator raised VultronProtocolViolationError (a plain VultronError
    subclass) the exception escaped model_validate() entirely, crashing the
    inbox-processing loop rather than being treated as a validation failure.
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
