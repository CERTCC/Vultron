"""Tests for the shared ``as_Base`` timestamp validator (ISSUE-3217).

``start_time``, ``end_time``, ``published`` and ``updated`` share one
``mode="before"`` validator, so the "if present, then non-empty" invariant
(CS-08-001) is expressed there once rather than as four per-field stubs
(CS-08-002).
"""

from datetime import datetime, timezone

import pytest

from vultron.wire.as2.vocab.base.objects.base import as_Object

_TIMESTAMP_FIELDS = ("start_time", "end_time", "published", "updated")

#: Every spelling of "the sender supplied no value".  Whitespace-only is
#: blank by the project's canonical predicate (``not v.strip()``, see
#: ``vultron.core.models.base._non_empty``), so a guard that catches ``""``
#: but not ``"   "`` has the same blind spot one character over.
_BLANK = ("", " ", "   ", "\t", "\n", " \t\n ")


@pytest.mark.spec("CS-08-001")
@pytest.mark.parametrize("field", _TIMESTAMP_FIELDS)
@pytest.mark.parametrize("blank", _BLANK)
def test_blank_timestamp_is_read_as_absent(field: str, blank: str):
    """A blank timestamp string carries no time, so it is absence, not garbage.

    Rejecting it outright is not an option for a *nested* object: a nested
    validation failure is refused by the parser, which would turn a cosmetic
    blank into a rejected message.  Reading it as absent keeps the object's
    own type intact.

    Absence here means ``None``, **not** the field default — see
    ``test_blank_timestamp_is_not_the_same_as_an_omitted_key``.
    """
    obj = as_Object.model_validate({"type": "Object", **{field: blank}})

    assert getattr(obj, field) is None


@pytest.mark.spec("CS-08-001")
@pytest.mark.parametrize("field", _TIMESTAMP_FIELDS)
def test_unparseable_timestamp_is_still_rejected(field: str):
    """Blank is absence; garbage is malformed, and stays an error.

    Pins the boundary the blank check must not cross.  A guard broad enough to
    absorb ``"not-a-date"`` would report a corrupt timestamp as a missing one.
    """
    with pytest.raises(ValueError):
        as_Object.model_validate({"type": "Object", **{field: "not-a-date"}})


@pytest.mark.spec("CS-08-001")
@pytest.mark.parametrize("field", _TIMESTAMP_FIELDS)
def test_supplied_timestamp_survives_verbatim(field: str):
    """Non-vacuity: the blank handling must not disturb a real value."""
    obj = as_Object.model_validate(
        {"type": "Object", **{field: "2026-03-04T05:06:07+00:00"}}
    )

    assert getattr(obj, field) == datetime(
        2026, 3, 4, 5, 6, 7, tzinfo=timezone.utc
    )


@pytest.mark.spec("CS-08-001")
@pytest.mark.spec("CLP-15-006")
def test_blank_timestamp_is_not_the_same_as_an_omitted_key():
    """Blank reads as an explicit ``null``, not as omission — the two differ.

    ``published`` and ``updated`` carry ``default_factory=now_utc``, so an
    omitted key yields the *receiver's* clock while a blank yields ``None``.
    Pinning the difference matters because ``None`` is the honest answer: it
    records that the sender supplied no time, where the default fabricates one
    and presents it as the sender's claim.  ``start_time`` and ``end_time``
    default to ``None``, so for those two the spellings do coincide.
    """
    omitted = as_Object.model_validate({"type": "Object"})
    blank = as_Object.model_validate(
        {"type": "Object", "published": "", "updated": ""}
    )

    # Defaulted fields: omission fabricates, blank does not.
    assert isinstance(omitted.published, datetime)
    assert isinstance(omitted.updated, datetime)
    assert blank.published is None
    assert blank.updated is None

    # None-defaulted fields: the two spellings genuinely coincide.
    assert omitted.start_time is None
    assert omitted.end_time is None
