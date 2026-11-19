"""The shared delegated-authorship helper (CM-24-001, CM-24-002, CM-24-012)."""

import pytest

from vultron.core.behaviors.delegated_authorship import (
    DelegatedAuthorship,
    delegated_authorship,
)
from vultron.errors import VultronValidationError, VultronWiringError

MANAGER = "https://example.org/actors/manager"
REQUESTER = "https://example.org/actors/requester"
REQUEST = "https://example.org/activities/request"


@pytest.mark.spec("CM-24-001")
@pytest.mark.spec("CM-24-012")
def test_actor_is_the_doing_actor() -> None:
    result = delegated_authorship(
        doing_actor_id=MANAGER,
        requesting_actor_id=REQUESTER,
        request_id=REQUEST,
    )
    assert result.actor == MANAGER


@pytest.mark.spec("BT-17-015")
@pytest.mark.spec("CM-24-002")
@pytest.mark.spec("CM-24-012")
def test_attributed_to_is_the_requesting_actor() -> None:
    result = delegated_authorship(
        doing_actor_id=MANAGER,
        requesting_actor_id=REQUESTER,
        request_id=REQUEST,
    )
    assert result == DelegatedAuthorship(
        actor=MANAGER, attributed_to=REQUESTER, in_reply_to=REQUEST
    )


@pytest.mark.spec("CM-24-008")
@pytest.mark.parametrize(
    "doing, requesting", [("", REQUESTER), (MANAGER, ""), ("", "")]
)
def test_empty_identity_is_refused_not_defaulted(
    doing: str, requesting: str
) -> None:
    with pytest.raises(VultronValidationError):
        delegated_authorship(
            doing_actor_id=doing,
            requesting_actor_id=requesting,
            request_id=REQUEST,
        )


@pytest.mark.spec("CM-24-012")
@pytest.mark.parametrize("requesting", [MANAGER, MANAGER + "/"])
def test_an_asker_that_is_the_doer_gets_neither_field(requesting: str) -> None:
    """The asker's own act credits no one and answers nothing (ADR-0199).

    The request is not read, so none is needed; a trailing slash does not
    make the same actor a different one (OID-01-007).
    """
    result = delegated_authorship(
        doing_actor_id=MANAGER, requesting_actor_id=requesting, request_id=None
    )
    assert result == DelegatedAuthorship(
        actor=MANAGER, attributed_to=None, in_reply_to=None
    )


@pytest.mark.spec("CM-24-012")
@pytest.mark.parametrize("request_id", [None, ""])
def test_a_distinct_asker_with_no_request_is_refused(
    request_id: str | None,
) -> None:
    """A distinct asker reaches the CASE_MANAGER only by message (ADR-0109),
    so a delegated act with no request to name is a programming error."""
    with pytest.raises(VultronWiringError, match="names no request"):
        delegated_authorship(
            doing_actor_id=MANAGER,
            requesting_actor_id=REQUESTER,
            request_id=request_id,
        )
