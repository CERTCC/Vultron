"""Tests for the core ``CaseStatus`` time requirement (CM-29-001, CLP-15-008)."""

from datetime import UTC, datetime

import pytest
from pydantic import ValidationError

from test.support.blank_strings import BLANKS
from vultron.core.models._helpers import (
    INBOUND_CONTEXT_KEY,
    MissingClaimedTimeError,
)
from vultron.core.models.case_status import CaseStatus

CASE_ID = "https://example.org/cases/1"
_INBOUND = {INBOUND_CONTEXT_KEY: True}


def _cause(exc: ValidationError) -> object:
    return exc.errors()[0].get("ctx", {}).get("error")


@pytest.mark.spec("CM-29-001")
@pytest.mark.spec("ARCH-10-001")
def test_case_status_requires_published():
    """A status built without a time fails at construction, not at sorting."""
    with pytest.raises(ValidationError):
        CaseStatus(context=CASE_ID, published=None)  # type: ignore[arg-type]


@pytest.mark.spec("CM-29-001")
def test_authored_case_status_takes_the_local_clock():
    before = datetime.now(tz=UTC)
    status = CaseStatus(context=CASE_ID)
    assert before <= status.published <= datetime.now(tz=UTC)


@pytest.mark.spec("ARCH-21-001")
def test_case_status_published_cannot_be_cleared_by_assignment():
    status = CaseStatus(context=CASE_ID)
    with pytest.raises(ValidationError):
        status.published = None  # type: ignore[assignment]


@pytest.mark.spec("CLP-15-008")
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


@pytest.mark.spec("CLP-15-008")
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


def test_authored_case_status_outside_inbound_path_is_not_refused():
    """The refusal is the inbound path's: in-process data takes the default."""
    status = CaseStatus.model_validate(
        {"type": "CaseStatus", "context": CASE_ID}
    )
    assert status.published is not None
