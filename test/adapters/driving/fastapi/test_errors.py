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

"""Tests for the FastAPI domain-error translation layer.

Focus: the EH-05-002 ``details`` array.  A caller that wants the individual
violations of a multi-violation rejection reads ``details``; a caller that wants
a human-readable summary keeps reading ``message``.  ISSUE-2112 named the old
alternative — parsing ``message`` — as silently order-dependent.

Closes #3050 AC-8, AC-10.
"""

from typing import Any, cast

import pytest
from fastapi import HTTPException, status

from vultron.adapters.driving.fastapi.errors import translate_domain_errors
from vultron.errors import (
    Violation,
    VultronError,
    VultronInvalidStateTransitionError,
    VultronNotFoundError,
    VultronValidationError,
)


def _as_body(exc: HTTPException) -> dict[str, Any]:
    """Return the error body ``exc`` carries.

    ``HTTPException.detail`` is declared ``str | None`` upstream, but this
    translation layer always passes a dict, so the cast is the honest read.
    """
    assert isinstance(exc.detail, dict), exc.detail
    return cast(dict[str, Any], exc.detail)


def _multi_violation_error() -> VultronValidationError:
    return VultronValidationError(
        "Refused ParticipantStatus write",
        violations=[
            Violation("Invalid RM transition START → CLOSED", ("rm",)),
            Violation(
                "Cross-machine entailment violated",
                ("rm", "vf"),
                derived=True,
            ),
        ],
    )


class TestValidationErrorDetails:
    """EH-05-002: one ``details`` entry per violation."""

    @staticmethod
    def _detail() -> dict:
        exc = translate_domain_errors(_multi_violation_error())
        assert isinstance(exc, HTTPException)
        assert exc.status_code == status.HTTP_422_UNPROCESSABLE_CONTENT
        return _as_body(exc)

    def test_details_has_one_entry_per_violation(self):
        assert len(self._detail()["details"]) == 2

    def test_each_entry_carries_its_message(self):
        messages = [e["message"] for e in self._detail()["details"]]
        assert messages == [
            "Invalid RM transition START → CLOSED",
            "Cross-machine entailment violated",
        ]

    def test_each_entry_identifies_root_or_derived(self):
        """The classification is what keeps thoroughness readable (EH-07-002)."""
        classifications = [
            e["classification"] for e in self._detail()["details"]
        ]
        assert classifications == ["root", "derived"]

    def test_each_entry_names_the_dimensions_the_rule_reads(self):
        dimensions = [e["dimensions"] for e in self._detail()["details"]]
        assert dimensions == [["rm"], ["rm", "vf"]]

    def test_message_still_renders_the_whole_set(self):
        """A text-only consumer must not be made worse off by adding details."""
        message = self._detail()["message"]
        assert "Invalid RM transition START → CLOSED" in message
        assert "Cross-machine entailment violated" in message

    def test_details_is_json_serialisable(self):
        """The body is returned through FastAPI, so it must be plain data."""
        import json

        json.dumps(self._detail())


class TestValidationErrorWithoutViolations:
    """A single-error rejection keeps the pre-existing body shape."""

    @staticmethod
    def _detail() -> dict:
        exc = translate_domain_errors(VultronValidationError("plain problem"))
        assert isinstance(exc, HTTPException)
        return _as_body(exc)

    def test_no_details_key_is_added(self):
        assert "details" not in self._detail()

    def test_message_is_unchanged(self):
        assert self._detail()["message"] == "plain problem"

    def test_activity_id_is_carried(self):
        exc = translate_domain_errors(
            VultronValidationError("problem", "urn:uuid:activity-1")
        )
        assert isinstance(exc, HTTPException)
        assert _as_body(exc)["activity_id"] == "urn:uuid:activity-1"


class TestOtherDomainErrorsUnaffected:
    """``details`` is scoped to the 422 branch."""

    def test_not_found_maps_to_404(self):
        exc = translate_domain_errors(VultronNotFoundError("Case", "urn:x"))
        assert isinstance(exc, HTTPException)
        assert exc.status_code == status.HTTP_404_NOT_FOUND
        assert "details" not in _as_body(exc)

    def test_invalid_state_transition_maps_to_409(self):
        exc = translate_domain_errors(
            VultronInvalidStateTransitionError("conflict")
        )
        assert isinstance(exc, HTTPException)
        assert exc.status_code == status.HTTP_409_CONFLICT
        assert "details" not in _as_body(exc)

    def test_untranslatable_error_is_re_raised(self):
        """An unmapped VultronError must not be silently turned into a 422."""
        with pytest.raises(VultronError):
            translate_domain_errors(VultronError("unmapped"))
