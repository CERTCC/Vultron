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

"""Tests for the use-case result envelope (UCORG-05-005, -008, -009)."""

from enum import StrEnum

import pytest
from pydantic import ValidationError

from vultron.core.models.use_case_result import (
    HandlerDisposition,
    HandlerResult,
    UseCaseResult,
)


def test_handler_disposition_is_a_str_enum() -> None:
    assert issubclass(HandlerDisposition, StrEnum)


def test_handler_disposition_members_are_exactly_the_four() -> None:
    """UCORG-05-009: exactly APPLIED, SKIPPED, DEFERRED, REFUSED."""
    assert {m.name for m in HandlerDisposition} == {
        "APPLIED",
        "SKIPPED",
        "DEFERRED",
        "REFUSED",
    }


def test_handler_result_inherits_use_case_result() -> None:
    """UCORG-05-008."""
    assert issubclass(HandlerResult, UseCaseResult)


def test_handler_result_fields_are_disposition_and_reason() -> None:
    """UCORG-05-005: no raw dict payload fields."""
    assert set(HandlerResult.model_fields) == {"disposition", "reason"}


def test_refused_requires_reason() -> None:
    with pytest.raises(ValidationError, match="REFUSED"):
        HandlerResult(disposition=HandlerDisposition.REFUSED)


def test_refused_with_reason_is_valid() -> None:
    result = HandlerResult(
        disposition=HandlerDisposition.REFUSED, reason="not a participant"
    )
    assert result.reason == "not a participant"


@pytest.mark.parametrize("blank", ["", "   "])
def test_blank_reason_is_rejected(blank: str) -> None:
    """CS-08-002: an optional string, if present, is non-empty."""
    with pytest.raises(ValidationError):
        HandlerResult(disposition=HandlerDisposition.REFUSED, reason=blank)


def test_applied_rejects_reason() -> None:
    with pytest.raises(ValidationError, match="APPLIED"):
        HandlerResult(disposition=HandlerDisposition.APPLIED, reason="why")


def test_applied_without_reason_is_valid() -> None:
    result = HandlerResult(disposition=HandlerDisposition.APPLIED)
    assert result.reason is None


@pytest.mark.parametrize(
    "disposition", [HandlerDisposition.SKIPPED, HandlerDisposition.DEFERRED]
)
def test_skipped_and_deferred_permit_but_do_not_require_reason(
    disposition: HandlerDisposition,
) -> None:
    assert HandlerResult(disposition=disposition).reason is None
    assert (
        HandlerResult(
            disposition=disposition, reason="awaiting entry 3"
        ).reason
        == "awaiting entry 3"
    )


def test_handler_result_is_frozen() -> None:
    """Assignment would bypass the reason rule, so it is refused."""
    result = HandlerResult(disposition=HandlerDisposition.APPLIED)
    with pytest.raises(ValidationError):
        result.disposition = HandlerDisposition.REFUSED  # type: ignore[misc]


def test_handler_result_rejects_unknown_fields() -> None:
    with pytest.raises(ValidationError):
        HandlerResult.model_validate(
            {"disposition": "applied", "payload": {"x": 1}}
        )


@pytest.mark.parametrize(
    "result",
    [
        HandlerResult(disposition=HandlerDisposition.APPLIED),
        HandlerResult(disposition=HandlerDisposition.SKIPPED, reason="dup"),
        HandlerResult(disposition=HandlerDisposition.DEFERRED, reason="gap"),
        HandlerResult(disposition=HandlerDisposition.REFUSED, reason="no"),
    ],
)
def test_handler_result_round_trips(result: HandlerResult) -> None:
    assert HandlerResult.model_validate(result.model_dump()) == result
    assert (
        HandlerResult.model_validate_json(result.model_dump_json()) == result
    )


def test_disposition_serializes_as_its_string_value() -> None:
    dumped = HandlerResult(disposition=HandlerDisposition.SKIPPED).model_dump(
        mode="json"
    )
    assert dumped == {"disposition": "skipped", "reason": None}


def test_constructors_build_the_matching_disposition() -> None:
    assert HandlerResult.applied() == HandlerResult(
        disposition=HandlerDisposition.APPLIED
    )
    assert HandlerResult.skipped("dup") == HandlerResult(
        disposition=HandlerDisposition.SKIPPED, reason="dup"
    )
    assert HandlerResult.skipped().reason is None
    assert HandlerResult.deferred("gap") == HandlerResult(
        disposition=HandlerDisposition.DEFERRED, reason="gap"
    )
    assert HandlerResult.deferred().reason is None
    assert HandlerResult.refused("no") == HandlerResult(
        disposition=HandlerDisposition.REFUSED, reason="no"
    )


def test_refused_constructor_still_enforces_non_empty_reason() -> None:
    with pytest.raises(ValidationError):
        HandlerResult.refused("")
