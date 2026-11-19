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

"""The edge's case-reference resolution (ADR-0032).

The registry-wide route behavior is pinned in
``test_trigger_routes_contract.py``; this file pins the helpers' own answers.
"""

import pytest

from test.support.objects import make
from vultron.adapters.driven.datalayer_sqlite import (
    SqliteDataLayer,
    reset_datalayer,
)
from vultron.adapters.driving.fastapi.case_reference import (
    find_case,
    require_case_id,
    with_full_case_id,
)
from vultron.core.models.case import VulnerabilityCase
from vultron.core.use_cases.triggers.requests import (
    AcceptCaseInviteTriggerRequest,
    EngageCaseTriggerRequest,
)
from vultron.errors import VultronNotFoundError
from vultron.wire.as2.vocab.base.objects.actors import as_Service
from vultron.wire.as2.vocab.base.objects.object_types import as_Note

_ACTOR = "https://example.org/actors/vendor"
_CASE = "https://example.org/cases/VU:42"
_SHORT = "VU:42"


@pytest.fixture
def dl():
    reset_datalayer(_ACTOR)
    store = SqliteDataLayer("sqlite:///:memory:", actor_id=_ACTOR)
    store.clear_all()
    store.create(make(as_Service, id_=_ACTOR, name="Vendor"))
    store.create(
        make(VulnerabilityCase, id_=_CASE, name="Case", attributed_to=_ACTOR)
    )
    yield store
    store.close()
    reset_datalayer(_ACTOR)


def test_find_case_by_full_id(dl) -> None:
    case = find_case(_CASE, dl)
    assert case is not None and case.id_ == _CASE


def test_find_case_by_short_id(dl) -> None:
    case = find_case(_SHORT, dl)
    assert case is not None and case.id_ == _CASE


def test_find_case_skips_a_non_case_object_of_that_id(dl) -> None:
    """An object that is not a case does not answer for the reference."""
    dl.create(make(as_Note, id_=_SHORT, content="not a case"))
    case = find_case(_SHORT, dl)
    assert case is not None and case.id_ == _CASE


def test_find_case_answers_nothing_for_an_unknown_reference(dl) -> None:
    assert find_case("https://example.org/cases/unknown", dl) is None


def test_find_case_answers_nothing_for_an_ambiguous_short_id(dl) -> None:
    dl.create(
        make(
            VulnerabilityCase,
            id_="https://other.example/cases/VU:42",
            name="Other",
            attributed_to=_ACTOR,
        )
    )
    assert find_case(_SHORT, dl) is None


def test_require_case_id_answers_the_full_id(dl) -> None:
    assert require_case_id(_SHORT, dl, _ACTOR) == _CASE


def test_require_case_id_names_the_reference_as_sent(dl) -> None:
    with pytest.raises(VultronNotFoundError) as raised:
        require_case_id("VU:99", dl, _ACTOR)
    assert str(raised.value) == "VulnerabilityCase 'VU:99' not found."


def test_require_case_id_names_an_unknown_actor_first(dl) -> None:
    """The trigger resolves its actor before its case, so the edge does."""
    stranger = "https://example.org/actors/stranger"
    with pytest.raises(VultronNotFoundError) as raised:
        require_case_id("VU:99", dl, stranger)
    assert str(raised.value) == f"Actor '{stranger}' not found."


def test_require_case_id_does_not_check_the_actor_of_a_held_case(dl) -> None:
    """A held case is resolved whoever asks; the use case judges the actor."""
    assert require_case_id(_CASE, dl, "https://example.org/actors/x") == _CASE


def test_with_full_case_id_promotes_a_short_id(dl) -> None:
    request = EngageCaseTriggerRequest(actor_id=_ACTOR, case_id=_SHORT)
    resolved = with_full_case_id(request, dl)
    assert type(resolved) is EngageCaseTriggerRequest
    assert resolved.case_id == _CASE
    assert resolved.actor_id == _ACTOR
    assert request.case_id == _SHORT


def test_with_full_case_id_keeps_a_full_id_request(dl) -> None:
    request = EngageCaseTriggerRequest(actor_id=_ACTOR, case_id=_CASE)
    assert with_full_case_id(request, dl) is request


def test_with_full_case_id_refuses_an_unknown_case(dl) -> None:
    request = EngageCaseTriggerRequest(
        actor_id=_ACTOR, case_id="https://example.org/cases/unknown"
    )
    with pytest.raises(VultronNotFoundError):
        with_full_case_id(request, dl)


def test_with_full_case_id_leaves_a_request_naming_no_case(dl) -> None:
    """A request that is not case-scoped reads nothing and passes as is."""
    request = AcceptCaseInviteTriggerRequest(
        actor_id=_ACTOR, invite_id="urn:uuid:invite"
    )
    assert with_full_case_id(request, dl) is request
