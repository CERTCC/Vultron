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
from typing import Any

import pytest
from pydantic import ValidationError

from vultron.core.models.use_case_result import (
    ActivityResult,
    CaseResult,
    HandlerDisposition,
    HandlerResult,
    NoteResult,
    OfferResult,
    RoleOfferResult,
    StatusResult,
    SyncLogEntryResult,
    TriggerResult,
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


@pytest.mark.parametrize(
    ("result", "took_effect"),
    [
        (HandlerResult.applied(), True),
        (HandlerResult.skipped("already present"), True),
        (HandlerResult.deferred("awaiting predecessor"), False),
        (HandlerResult.refused("not a participant"), False),
    ],
)
def test_took_effect_is_true_only_for_applied_and_skipped(
    result: HandlerResult, took_effect: bool
) -> None:
    assert result.took_effect is took_effect


# ---------------------------------------------------------------------------
# Trigger-side hierarchy (UCORG-05-005, UCORG-05-007, UCORG-05-008, ADR-0110)
# ---------------------------------------------------------------------------

_ACTOR = "https://example.org/actors/vendor"
_ACTIVITY = {"type": "Join", "id": "urn:uuid:1", "actor": _ACTOR}

#: Every trigger result subtype with a valid construction and the exact key
#: set its verb's response body carries (the verb-to-subtype table in
#: ADR-0110 § "Result hierarchy").
_TRIGGER_RESULTS: list[
    tuple[type[TriggerResult], dict[str, Any], set[str]]
] = [
    (
        ActivityResult,
        {"activity": _ACTIVITY, "emitting_actor_id": _ACTOR},
        {"activity", "emitting_actor_id"},
    ),
    (
        NoteResult,
        {
            "activity": _ACTIVITY,
            "emitting_actor_id": _ACTOR,
            "note": {"type": "Note", "id": "urn:uuid:2"},
        },
        {"activity", "emitting_actor_id", "note"},
    ),
    (
        CaseResult,
        {
            "activity": _ACTIVITY,
            "emitting_actor_id": _ACTOR,
            "case_id": "urn:uuid:3",
        },
        {"activity", "emitting_actor_id", "case_id"},
    ),
    (
        StatusResult,
        {"activity_id": "urn:uuid:4", "status_id": "urn:uuid:5"},
        {"activity_id", "status_id"},
    ),
    (
        OfferResult,
        {"offer": {"type": "Offer", "id": "urn:uuid:6"}},
        {"offer"},
    ),
    (
        RoleOfferResult,
        {"activity_id": "urn:uuid:7", "activity": _ACTIVITY},
        {"activity_id", "activity"},
    ),
    (
        SyncLogEntryResult,
        {
            "log_entry_id": "urn:uuid:8",
            "entry_hash": "ab" * 32,
            "log_index": 0,
            "emitting_actor_id": _ACTOR,
        },
        {"log_entry_id", "entry_hash", "log_index", "emitting_actor_id"},
    ),
]


def test_trigger_result_is_a_fieldless_use_case_result() -> None:
    """UCORG-05-005, UCORG-05-008: the root carries no fields of its own."""
    assert issubclass(TriggerResult, UseCaseResult)
    assert TriggerResult.model_fields == {}


def test_trigger_result_root_rejects_any_key() -> None:
    """A fieldless root with ``extra="forbid"`` refuses every key."""
    with pytest.raises(ValidationError, match="extra_forbidden|Extra inputs"):
        TriggerResult(activity=_ACTIVITY)  # type: ignore[call-arg]


@pytest.mark.parametrize(
    ("result_cls", "payload", "expected_keys"),
    _TRIGGER_RESULTS,
    ids=[cls.__name__ for cls, _, _ in _TRIGGER_RESULTS],
)
def test_trigger_result_subtype_declares_exactly_its_body_keys(
    result_cls: type[TriggerResult],
    payload: dict[str, Any],
    expected_keys: set[str],
) -> None:
    """UCORG-05-005: each subtype's field set is its verb's response body."""
    assert issubclass(result_cls, TriggerResult)
    result = result_cls.model_validate(payload)
    assert set(result_cls.model_fields) == expected_keys
    assert set(result.model_dump()) == expected_keys
    assert result.model_dump() == payload


@pytest.mark.parametrize(
    ("result_cls", "payload", "expected_keys"),
    _TRIGGER_RESULTS,
    ids=[cls.__name__ for cls, _, _ in _TRIGGER_RESULTS],
)
def test_trigger_result_subtype_rejects_an_unknown_key(
    result_cls: type[TriggerResult],
    payload: dict[str, Any],
    expected_keys: set[str],
) -> None:
    """UCORG-05-005: a use case that grows a return key fails loudly."""
    with pytest.raises(ValidationError, match="extra_forbidden|Extra inputs"):
        result_cls.model_validate({**payload, "surprise": 1})


@pytest.mark.parametrize(
    ("result_cls", "payload", "expected_keys"),
    _TRIGGER_RESULTS,
    ids=[cls.__name__ for cls, _, _ in _TRIGGER_RESULTS],
)
def test_trigger_result_is_frozen(
    result_cls: type[TriggerResult],
    payload: dict[str, Any],
    expected_keys: set[str],
) -> None:
    result = result_cls.model_validate(payload)
    field = next(iter(expected_keys))
    with pytest.raises(ValidationError, match="frozen"):
        setattr(result, field, None)


@pytest.mark.parametrize(
    ("result_cls", "payload"),
    [
        (ActivityResult, {"emitting_actor_id": _ACTOR}),
        (NoteResult, {"emitting_actor_id": _ACTOR}),
        (CaseResult, {"emitting_actor_id": _ACTOR}),
        (StatusResult, {}),
        (OfferResult, {}),
    ],
    ids=["activity", "note", "case", "status", "offer"],
)
def test_optional_payload_keys_are_emitted_when_none(
    result_cls: type[TriggerResult], payload: dict[str, Any]
) -> None:
    """TRIG-12-002: a key the BT left empty is still in the body, as ``null``.

    The router serialises the result with ``model_dump()`` and never with
    ``exclude_none``, so the response body's key set is the subtype's field
    set even when a payload was not captured.
    """
    dumped = result_cls.model_validate(payload).model_dump()
    assert set(dumped) == set(result_cls.model_fields)
    for key in set(result_cls.model_fields) - set(payload):
        assert dumped[key] is None


def test_activity_result_requires_an_emitting_actor() -> None:
    """``_prepare()`` must have resolved the actor; a blank one is a bug."""
    with pytest.raises(ValidationError):
        ActivityResult(activity=_ACTIVITY)  # type: ignore[call-arg]
    with pytest.raises(ValidationError):
        ActivityResult(activity=_ACTIVITY, emitting_actor_id="")


def test_role_offer_result_requires_both_keys() -> None:
    """The one non-BT verb always has an activity and its id (ADR-0110)."""
    with pytest.raises(ValidationError):
        RoleOfferResult(activity_id="urn:uuid:7")  # type: ignore[call-arg]
    with pytest.raises(ValidationError):
        RoleOfferResult(activity=_ACTIVITY)  # type: ignore[call-arg]


def test_activity_result_subtypes_share_the_activity_body() -> None:
    """``NoteResult`` and ``CaseResult`` extend the activity body, not the root."""
    assert issubclass(NoteResult, ActivityResult)
    assert issubclass(CaseResult, ActivityResult)
    for other in (StatusResult, OfferResult, RoleOfferResult):
        assert not issubclass(other, ActivityResult)
