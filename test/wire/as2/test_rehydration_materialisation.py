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

"""ID-to-object materialisation: `rehydrate()` owns it (VM-06-007, #3486).

ADR-0099 detail 9 says an object slot holds the whole object, not an ID, and
that reading resolves an IRI reference to the referenced object, with an
unresolvable reference deferred or refused.  These tests pin the owner of that
resolution and the split between deferring and refusing.

They also pin the deliberate *absence* of the behaviour they replace.
``as_VulnerabilityCase.from_core`` fabricated a stub ``as_Activity`` around a
bare ID with a **synthesized** actor (``core_obj.attributed_to or
core_obj.id_``).  ``test_materialised_activity_carries_its_own_actor`` is the
regression guard: the materialised activity must carry the actor it was
recorded with, not the case owner and not the case's own URI.
"""

from typing import Any, cast

import pytest
from pydantic import ValidationError

from vultron.core.ports.datalayer import DataLayer
from vultron.enums.roles import CVDRole
from vultron.wire.as2.rehydration import (
    materialise,
    materialise_object_slots,
    rehydrate,
)
from vultron.wire.as2.vocab.base.objects.activities.base import as_Activity
from vultron.wire.as2.vocab.base.objects.base import as_Object
from vultron.wire.as2.vocab.objects.case_participant import as_CaseParticipant
from vultron.wire.as2.vocab.objects.case_status import (
    as_CaseStatus,
    as_ParticipantStatus,
)
from vultron.wire.as2.vocab.objects.vulnerability_case import (
    as_VulnerabilityCase,
)

CASE_ID = "https://example.org/cases/case-1"
CASE_OWNER = "https://example.org/actors/vendor"
OTHER_PARTICIPANT = "https://example.org/actors/finder"
MISSING_ID = "https://example.org/activities/not-in-the-store"


class FakeDataLayer:
    """Minimal stand-in for the `DataLayer` read port.

    ``rehydrate`` only ever calls ``read``, and takes the port via its ``dl``
    parameter precisely so the wire layer needs no concrete adapter
    (VM-06-002).  Recording the calls lets the collection-endpoint test assert
    that no lookup was attempted at all.
    """

    def __init__(self, objects: dict[str, Any] | None = None) -> None:
        self._objects: dict[str, Any] = dict(objects or {})
        self.reads: list[str] = []

    def add(self, obj: Any) -> Any:
        self._objects[obj.id_] = obj
        return obj

    def read(self, obj_id: str) -> Any:
        self.reads.append(obj_id)
        return self._objects.get(obj_id)

    def as_port(self) -> DataLayer:
        """Narrow the fake to the port these functions declare.

        Cast rather than implement: the `DataLayer` Protocol is wide (create,
        update, delete, queues, diagnostics) and none of it is reachable from
        here, so satisfying it structurally would be noise that hid which one
        method is actually exercised.
        """
        return cast(DataLayer, self)


class LooselyTypedStoredCase(as_Object):
    """A stored case whose `case_activity` is still a list of bare IDs.

    Stands in for what a store hands back before rehydration: the activity log
    is a list of URIs, which is how the core model records it
    (``VulnerabilityCase.case_activity: list[str]``).  Deliberately declares no
    ``type_`` of its own, so it is not auto-registered in ``VOCABULARY``
    (VM-01-001) and cannot leak into the registry-completeness tests.
    """

    case_activity: list[str] = []


@pytest.fixture
def recorded_activity() -> as_Activity:
    """An activity performed by someone other than the case owner."""
    return as_Activity(
        id_="https://example.org/activities/act-1",
        actor=OTHER_PARTICIPANT,
        type_="Activity",
    )


@pytest.fixture
def dl(recorded_activity: as_Activity) -> FakeDataLayer:
    layer = FakeDataLayer()
    layer.add(recorded_activity)
    return layer


# ---------------------------------------------------------------------------
# AC-3, first half: a slot given a bare ID ends up holding the resolved object
# ---------------------------------------------------------------------------


def test_bare_id_in_list_object_slot_is_resolved(
    dl: FakeDataLayer, recorded_activity: as_Activity
) -> None:
    data = {"id": CASE_ID, "case_activity": [recorded_activity.id_]}
    out = materialise_object_slots(as_VulnerabilityCase, data, dl.as_port())
    assert out["case_activity"] == [recorded_activity]
    assert dl.reads == [recorded_activity.id_]


def test_materialise_builds_a_valid_object_from_bare_ids(
    dl: FakeDataLayer, recorded_activity: as_Activity
) -> None:
    """The whole point: `list[as_Activity]` rejects a bare string outright."""
    data = {
        "id": CASE_ID,
        "attributedTo": CASE_OWNER,
        "case_activity": [recorded_activity.id_],
    }
    with pytest.raises(ValidationError):
        as_VulnerabilityCase.model_validate(data)

    case = materialise(as_VulnerabilityCase, data, dl.as_port())
    assert isinstance(case.case_activity[0], as_Activity)
    assert case.case_activity[0].id_ == recorded_activity.id_


def test_bare_id_in_scalar_object_slot_is_resolved() -> None:
    """`as_ParticipantStatus.case_status` is scalar and admits no URI."""
    status = as_CaseStatus(id_="https://example.org/case-statuses/cs-1")
    dl = FakeDataLayer({status.id_: status})
    out = materialise_object_slots(
        as_ParticipantStatus,
        {"id": "https://example.org/pstatus/ps-1", "case_status": status.id_},
        dl.as_port(),
    )
    assert out["case_status"] is status


def test_rehydrate_materialises_object_slots(
    dl: FakeDataLayer, recorded_activity: as_Activity
) -> None:
    """End-to-end through the named owner, not just the helper."""
    stored = LooselyTypedStoredCase(
        id_=CASE_ID,
        type_="VulnerabilityCase",
        case_activity=[recorded_activity.id_],
    )
    dl.add(stored)

    result = rehydrate(stored, dl=dl.as_port())

    assert isinstance(result, as_VulnerabilityCase)
    assert [a.id_ for a in result.case_activity] == [recorded_activity.id_]


def test_rehydrate_materialises_from_a_bare_case_id(
    dl: FakeDataLayer, recorded_activity: as_Activity
) -> None:
    """`rehydrate(id)` resolves the case *and* the references inside it."""
    dl.add(
        LooselyTypedStoredCase(
            id_=CASE_ID,
            type_="VulnerabilityCase",
            case_activity=[recorded_activity.id_],
        )
    )

    result = rehydrate(CASE_ID, dl=dl.as_port())

    assert isinstance(result, as_VulnerabilityCase)
    assert result.case_activity[0].actor == OTHER_PARTICIPANT


# ---------------------------------------------------------------------------
# AC-2: the synthesized actor is NOT reproduced
# ---------------------------------------------------------------------------


def test_materialised_activity_carries_its_own_actor(
    dl: FakeDataLayer, recorded_activity: as_Activity
) -> None:
    """Regression guard for the behaviour `from_core` used to fabricate.

    ``as_VulnerabilityCase.from_core`` built ``as_Activity(id_=activity_id,
    actor=core_obj.attributed_to or core_obj.id_)`` — the case owner, or the
    case's own URI.  ``record_activity`` records activity by *any* participant,
    so that misattributes every activity the owner did not perform.  The owner
    of materialisation resolves the reference instead, so the actor is the real
    one.
    """
    case = materialise(
        as_VulnerabilityCase,
        {
            "id": CASE_ID,
            "attributedTo": CASE_OWNER,
            "case_activity": [recorded_activity.id_],
        },
        dl.as_port(),
    )
    actor = case.case_activity[0].actor
    assert actor == OTHER_PARTICIPANT
    assert actor != CASE_OWNER, "synthesized the case owner as the actor"
    assert actor != CASE_ID, "synthesized the case's own URI as the actor"


# ---------------------------------------------------------------------------
# AC-3, second half: an unresolvable reference is refused, never left bare
# ---------------------------------------------------------------------------


def test_unresolvable_reference_in_object_slot_is_refused(
    dl: FakeDataLayer,
) -> None:
    with pytest.raises(ValueError) as excinfo:
        materialise_object_slots(
            as_VulnerabilityCase,
            {"id": CASE_ID, "case_activity": [MISSING_ID]},
            dl.as_port(),
        )
    message = str(excinfo.value)
    assert MISSING_ID in message
    assert "case_activity" in message


def test_refusal_does_not_leave_a_bare_string_behind(
    dl: FakeDataLayer,
) -> None:
    """Neither a stub nor a string: the object is not built at all."""
    with pytest.raises(ValueError):
        materialise(
            as_VulnerabilityCase,
            {
                "id": CASE_ID,
                "attributedTo": CASE_OWNER,
                "case_activity": [MISSING_ID],
            },
            dl.as_port(),
        )


def test_unresolvable_scalar_reference_is_refused() -> None:
    with pytest.raises(ValueError):
        materialise_object_slots(
            as_ParticipantStatus,
            {
                "id": "https://example.org/pstatus/ps-2",
                "case_status": MISSING_ID,
            },
            FakeDataLayer().as_port(),
        )


def test_rehydrate_refuses_an_unresolvable_object_slot(
    dl: FakeDataLayer,
) -> None:
    stored = LooselyTypedStoredCase(
        id_=CASE_ID, type_="VulnerabilityCase", case_activity=[MISSING_ID]
    )
    with pytest.raises(ValueError) as excinfo:
        rehydrate(stored, dl=dl.as_port())
    assert MISSING_ID in str(excinfo.value)


# ---------------------------------------------------------------------------
# The other half of detail 9: a slot that admits a URI defers instead
# ---------------------------------------------------------------------------


def test_uri_admitting_slot_is_left_for_the_defer_path(
    dl: FakeDataLayer,
) -> None:
    """`case_participants` is `ActivityStreamRef[...]`, so a URI is legal there.

    Unresolvable references in those slots are *deferred* — kept as the string
    with a WARNING — which is VM-06-004's behaviour and belongs to
    `DataLayer.hydrate`, not here.  Materialisation must not reach into them.
    """
    participant_id = "https://example.org/participants/p-1"
    out = materialise_object_slots(
        as_VulnerabilityCase,
        {"id": CASE_ID, "case_participants": [participant_id]},
        dl.as_port(),
    )
    assert out["case_participants"] == [participant_id]
    assert dl.reads == []


def test_collection_endpoint_slots_are_not_materialised() -> None:
    """An actor's `inbox` is an address, not a stored object.

    ``as_Actor`` declares ``inbox: as_OrderedCollection`` but supplies a
    ``mode="before"`` coercion for URI strings.  Materialisation must not
    pre-empt that, and must not chase a remote URL through the data layer.
    """
    from vultron.wire.as2.vocab.objects.vultron_actor import (
        as_VultronOrganization,
    )

    dl = FakeDataLayer()
    actor = materialise(
        as_VultronOrganization,
        {
            "id": "https://remote.example/actors/org",
            "name": "Remote Org",
            "inbox": "https://remote.example/actors/org/inbox",
        },
        dl.as_port(),
    )
    assert dl.reads == []
    assert actor.inbox.id_ == "https://remote.example/actors/org/inbox"


# ---------------------------------------------------------------------------
# No-op paths
# ---------------------------------------------------------------------------


def test_already_materialised_data_is_returned_unchanged(
    dl: FakeDataLayer, recorded_activity: as_Activity
) -> None:
    data: dict[str, Any] = {
        "id": CASE_ID,
        "case_activity": [recorded_activity],
    }
    out = materialise_object_slots(as_VulnerabilityCase, data, dl.as_port())
    assert out is data
    assert dl.reads == []


def test_absent_and_empty_slots_are_left_alone(dl: FakeDataLayer) -> None:
    for data in ({"id": CASE_ID}, {"id": CASE_ID, "case_activity": []}):
        out = materialise_object_slots(
            as_VulnerabilityCase, data, dl.as_port()
        )
        assert out is data
    assert dl.reads == []


def test_nested_object_list_slot_is_covered_too() -> None:
    """`as_CaseParticipant.participant_statuses` is the third such slot."""
    status = as_ParticipantStatus(
        id_="https://example.org/pstatus/ps-3",
        attributed_to=OTHER_PARTICIPANT,
        context=CASE_ID,
    )
    dl = FakeDataLayer({status.id_: status})
    participant = materialise(
        as_CaseParticipant,
        {
            "id": "https://example.org/participants/p-2",
            "attributedTo": OTHER_PARTICIPANT,
            "context": CASE_ID,
            "case_roles": [CVDRole.FINDER.value],
            "participant_statuses": [status.id_],
        },
        dl.as_port(),
    )
    assert participant.participant_statuses[0].id_ == status.id_
