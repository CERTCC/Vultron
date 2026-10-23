"""The shared delegated-authorship helper (CM-24-001, CM-24-002, CM-24-005)."""

import pytest

from vultron.core.behaviors.delegated_authorship import (
    DelegatedAuthorship,
    delegated_authorship,
)
from vultron.errors import VultronValidationError

MANAGER = "https://example.org/actors/manager"
REQUESTER = "https://example.org/actors/requester"


@pytest.mark.spec("CM-24-001")
def test_actor_is_the_doing_actor() -> None:
    result = delegated_authorship(
        doing_actor_id=MANAGER, requesting_actor_id=REQUESTER
    )
    assert result.actor == MANAGER


@pytest.mark.spec("CM-24-002")
def test_attributed_to_is_the_requesting_actor() -> None:
    result = delegated_authorship(
        doing_actor_id=MANAGER, requesting_actor_id=REQUESTER
    )
    assert result == DelegatedAuthorship(
        actor=MANAGER, attributed_to=REQUESTER
    )


@pytest.mark.spec("CM-24-006")
@pytest.mark.parametrize(
    "doing, requesting", [("", REQUESTER), (MANAGER, ""), ("", "")]
)
def test_empty_identity_is_refused_not_defaulted(
    doing: str, requesting: str
) -> None:
    with pytest.raises(VultronValidationError):
        delegated_authorship(
            doing_actor_id=doing, requesting_actor_id=requesting
        )
