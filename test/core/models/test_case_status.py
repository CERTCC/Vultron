"""Tests for the core ``CaseStatus`` times (SM-05-003, CM-29-006, CLP-15-010)."""

from datetime import datetime, timedelta

import pytest
from pydantic import ValidationError

from test.support.act_clock import ACT_AT, recorded_clock_reads
from test.support.blank_strings import BLANKS
from test.support.case_owner import CASE_OWNER_ID
from test.support.objects import make
from vultron.core.models._helpers import (
    INBOUND_CONTEXT_KEY,
    MissingClaimedTimeError,
)
from vultron.core.models.case import VulnerabilityCase
from vultron.core.models.case_status import CaseStatus
from vultron.core.states.cs import CS_pxa

CASE_ID = "https://example.org/cases/1"
_INBOUND = {INBOUND_CONTEXT_KEY: True}


def _cause(exc: ValidationError) -> object:
    return exc.errors()[0].get("ctx", {}).get("error")


@pytest.mark.spec("SM-05-003")
@pytest.mark.spec("ARCH-10-001")
def test_case_status_requires_published():
    """A status built without a time fails at construction, not at sorting."""
    with pytest.raises(ValidationError):
        make(CaseStatus, context=CASE_ID, published=None)  # type: ignore[arg-type]


@pytest.mark.spec("SM-05-003")
@pytest.mark.spec("CS-13-002")
def test_an_authored_case_status_states_its_time():
    """A status's ``published`` is required: the model reads no clock.

    Building one without a time is refused, and no clock is read in the
    attempt (ADR-0176).
    """
    with recorded_clock_reads() as reads:
        with pytest.raises(ValidationError, match="published"):
            CaseStatus.model_validate({"context": CASE_ID})
    assert reads == []
    status = make(CaseStatus, context=CASE_ID, published=ACT_AT)
    assert status.published == ACT_AT


@pytest.mark.spec("CM-29-006")
def test_authored_case_status_updated_equals_published():
    """An authored status has one time: no ``updated`` besides ``published``.

    Covers a status built directly (the snapshot node's and the case seed's
    path) and one built by ``append_case_status``, which copies the current
    status and so would otherwise carry its old ``updated`` forward.
    """
    built = make(CaseStatus, context=CASE_ID)
    case = make(VulnerabilityCase, id_=CASE_ID, attributed_to=CASE_OWNER_ID)
    seeded = case.current_status
    seeded.updated = seeded.published - timedelta(days=1)
    case.append_case_status(ACT_AT, pxa=CS_pxa.Pxa)
    appended = case.current_status
    assert appended is not seeded
    assert built.updated is None
    assert appended.updated is None


@pytest.mark.spec("ARCH-21-001")
def test_case_status_published_cannot_be_cleared_by_assignment():
    status = make(CaseStatus, context=CASE_ID)
    with pytest.raises(ValidationError):
        status.published = None  # type: ignore[assignment]


@pytest.mark.spec("CLP-15-010")
@pytest.mark.parametrize("published", [None, *BLANKS])
def test_inbound_case_status_without_published_is_refused(
    published: str | None,
):
    """Absent and blank are one omission, refused with a named cause.

    ``None`` here leaves the key out of the payload altogether.
    """
    data: dict[str, object] = {"type": "CaseStatus", "context": CASE_ID}
    if published is not None:
        data["published"] = published
    with pytest.raises(ValidationError) as caught:
        CaseStatus.model_validate(data, context=_INBOUND)
    assert isinstance(_cause(caught.value), MissingClaimedTimeError)


@pytest.mark.spec("CLP-15-010")
def test_inbound_case_status_with_explicit_null_published_is_refused():
    with pytest.raises(ValidationError) as caught:
        CaseStatus.model_validate(
            {"type": "CaseStatus", "context": CASE_ID, "published": None},
            context=_INBOUND,
        )
    assert isinstance(_cause(caught.value), MissingClaimedTimeError)


@pytest.mark.spec("CLP-15-007")
def test_inbound_case_status_keeps_the_senders_published():
    """The receiver carries the sender's time; it never reads its own clock."""
    sent = "2020-02-03T04:05:06+00:00"
    status = CaseStatus.model_validate(
        {"type": "CaseStatus", "context": CASE_ID, "published": sent},
        context=_INBOUND,
    )
    assert status.published == datetime.fromisoformat(sent)
    assert status.updated is None


def test_authored_case_status_outside_inbound_path_is_refused_as_required():
    """Outside the inbound path a missing time is a required field left out,
    not a sender's missing claim, and nothing supplies it (ADR-0176)."""
    with pytest.raises(ValidationError) as info:
        CaseStatus.model_validate({"type": "CaseStatus", "context": CASE_ID})
    assert [e["type"] for e in info.value.errors()] == ["missing"]
