#!/usr/bin/env python
"""
Tests for CaseStatus and ParticipantStatus empty-string field validation
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

import pytest
from pydantic import ValidationError

from vultron.wire.as2.vocab.objects.case_status import (
    CaseStatus,
    ParticipantStatus,
)

CASE_ID = "https://example.org/cases/case-001"
ACTOR_ID = "https://example.org/actors/alice"


class TestCaseStatusContextField(unittest.TestCase):
    """Tests for CaseStatus.context empty-string validation (CS-08-001)."""

    def test_context_none_accepted(self):
        """context=None is valid (optional field)."""
        cs = CaseStatus(context=None)
        self.assertIsNone(cs.context)

    def test_context_non_empty_accepted(self):
        """context with a non-empty string (case ID) is valid."""
        cs = CaseStatus(context=CASE_ID)
        self.assertEqual(CASE_ID, cs.context)

    def test_context_empty_string_rejected(self):
        """context must not be an empty string (CS-08-001)."""
        with pytest.raises(ValidationError) as exc_info:
            CaseStatus(context="")
        assert "must be a non-empty string" in str(exc_info.value)

    def test_context_whitespace_only_rejected(self):
        """context must not be whitespace-only (CS-08-001)."""
        with pytest.raises(ValidationError) as exc_info:
            CaseStatus(context="   ")
        assert "must be a non-empty string" in str(exc_info.value)


class TestParticipantStatusTrackingIdField(unittest.TestCase):
    """Tests for ParticipantStatus.tracking_id empty-string validation (CS-08-001)."""

    def test_tracking_id_none_accepted(self):
        """tracking_id=None is valid (optional field)."""
        ps = ParticipantStatus(
            attributed_to=ACTOR_ID, context=CASE_ID, tracking_id=None
        )
        self.assertIsNone(ps.tracking_id)

    def test_tracking_id_non_empty_accepted(self):
        """tracking_id with a non-empty string is valid."""
        ps = ParticipantStatus(
            attributed_to=ACTOR_ID, context=CASE_ID, tracking_id="TICKET-123"
        )
        self.assertEqual("TICKET-123", ps.tracking_id)

    def test_tracking_id_empty_string_rejected(self):
        """tracking_id must not be an empty string (CS-08-001)."""
        with pytest.raises(ValidationError) as exc_info:
            ParticipantStatus(
                attributed_to=ACTOR_ID, context=CASE_ID, tracking_id=""
            )
        assert "must be a non-empty string" in str(exc_info.value)

    def test_tracking_id_whitespace_only_rejected(self):
        """tracking_id must not be whitespace-only (CS-08-001)."""
        with pytest.raises(ValidationError) as exc_info:
            ParticipantStatus(
                attributed_to=ACTOR_ID, context=CASE_ID, tracking_id="   "
            )
        assert "must be a non-empty string" in str(exc_info.value)


if __name__ == "__main__":
    unittest.main()
