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
"""A typed reference that carries a preview is read as received (ADR-0205).

The case's preview is the case stub (MV-10-012).  A case reference carrying
it is never expanded into the case the receiver holds, at any depth, never
reduced to a bare id for the inbox to fetch, and satisfies only a pattern
that asks for that form, so no other pattern reads it as the case
(MV-10-011, SE-01-009).  Each test feeds raw JSON through ``parse_activity``,
the real inbound edge.
"""

from typing import Any, get_args

import pytest
from pydantic import ValidationError

from test.support.case_manager import (
    CASE_MANAGER_ID,
    make_case_with_case_manager,
)
from vultron.adapters.driven.datalayer_sqlite import SqliteDataLayer
from vultron.adapters.driven.db_record import (
    object_to_record,
    record_to_object,
)
from vultron.core.models.case import VulnerabilityCase
from vultron.core.models.enums import VultronObjectType as VOtype
from vultron.core.models.events import MessageSemantics
from vultron.semantic_registry import (
    SEMANTIC_REGISTRY,
    find_matching_semantics,
)
from vultron.wire.as2.enums import as_TransitiveActivityType as TAtype
from vultron.wire.as2.errors import VultronParseError
from vultron.wire.as2.extractor import ActivityPattern, ObjectForm
from vultron.wire.as2.extractor._pattern import bare_object_id
from vultron.wire.as2.parser import parse_activity
from vultron.wire.as2.rehydration import rehydrate
from vultron.wire.as2.typed_reference import (
    DEFINED_PREVIEWS,
    as_TypedReference,
    is_previewed_reference,
)
from vultron.wire.as2.vocab.base.objects.activities.base import as_Activity
from vultron.wire.as2.vocab.objects.case_preview import as_CasePreview

_PUBLISHED = "2026-11-16T12:00:00Z"
_INVITEE = "https://example.org/actors/bob"
_RECEIVER = CASE_MANAGER_ID


def _stub(case_id: str) -> dict[str, Any]:
    """The case's preview: its own id, which names nothing (ADR-0205)."""
    return {
        "type": "CasePreview",
        "attributedTo": "https://example.org/actors/vendor",
        "id": f"urn:uuid:preview-of-{case_id.rsplit('/', 1)[-1]}",
        "summary": "A remote code execution vulnerability in widget.",
    }


def _previewed(case_id: str) -> dict[str, Any]:
    """A case reference carrying the case's preview (ADR-0205)."""
    return {
        "id": case_id,
        "type": "VulnerabilityCase",
        "preview": _stub(case_id),
    }


def _invite(obj: dict[str, Any] | str, n: int = 1) -> dict[str, Any]:
    return {
        "type": "Invite",
        "id": f"https://example.org/activities/invite-{n}",
        "published": _PUBLISHED,
        "actor": CASE_MANAGER_ID,
        "object": obj,
        "target": _INVITEE,
    }


def _accept(obj: dict[str, Any] | str) -> dict[str, Any]:
    return {
        "type": "Accept",
        "id": "https://example.org/activities/accept-1",
        "published": _PUBLISHED,
        "actor": _INVITEE,
        "object": obj,
    }


def _whole(case: VulnerabilityCase) -> dict[str, Any]:
    return case.model_dump(mode="json", by_alias=True, exclude_none=True)


def _object_chain_end(activity: object) -> object:
    obj = getattr(activity, "object_", None)
    while isinstance(obj, as_Activity):
        obj = getattr(obj, "object_", None)
    return obj


@pytest.fixture
def held() -> tuple[SqliteDataLayer, VulnerabilityCase]:
    """A CASE_MANAGER's store, holding the case a preview names."""
    dl = SqliteDataLayer("sqlite:///:memory:", actor_id=_RECEIVER)
    return dl, make_case_with_case_manager(dl)


# ---------------------------------------------------------------------------
# The parse edge: the case defines its preview (MV-10-012, MV-10-002)
# ---------------------------------------------------------------------------


@pytest.mark.spec("MV-10-011")
@pytest.mark.spec("MV-10-012")
@pytest.mark.parametrize("wrap", [False, True], ids=["invite", "accept"])
def test_a_case_reference_carrying_the_stub_parses_as_a_previewed_reference(
    wrap: bool,
) -> None:
    case_id = "https://example.org/cases/c1"
    invite = _invite(_previewed(case_id))

    parsed = parse_activity(_accept(invite) if wrap else invite)

    reference = _object_chain_end(parsed)
    assert isinstance(reference, as_TypedReference)
    assert is_previewed_reference(reference)
    assert reference.id_ == case_id
    assert isinstance(reference.preview, as_CasePreview)
    assert reference.preview.summary


@pytest.mark.spec("MV-10-012")
@pytest.mark.parametrize(
    "preview",
    [
        pytest.param("https://example.org/cases/c1/stub", id="uri"),
        pytest.param(
            {"type": "Note", "content": "a vul", "published": _PUBLISHED},
            id="another-type",
        ),
        pytest.param(
            {"type": "NoSuchType", "summary": "a vul"}, id="unknown-type"
        ),
    ],
)
def test_a_case_reference_whose_preview_is_not_the_stub_is_refused(
    preview: object,
) -> None:
    """Only an inline stub is the case's preview, and the refusal names
    the reference's position."""
    reference = {
        "id": "https://example.org/cases/c1",
        "type": "VulnerabilityCase",
        "preview": preview,
    }

    with pytest.raises(VultronParseError, match="MV-10-012") as raised:
        parse_activity(_accept(_invite(reference)))

    assert "'object.object'" in str(raised.value)


@pytest.mark.spec("MV-10-002")
@pytest.mark.parametrize("verb", ["Announce", "Create", "Offer"])
def test_a_previewed_case_reference_outside_an_invite_is_refused(
    verb: str,
) -> None:
    """The stub a preview carries sits only where an ``Invite`` names the
    case, so a previewed reference anywhere else carries a misplaced stub."""
    body = _invite(_previewed("https://example.org/cases/c1"))
    body["type"] = verb

    with pytest.raises(VultronParseError, match="MV-10-002") as raised:
        parse_activity(body)

    assert "object.preview" in str(raised.value)


# ---------------------------------------------------------------------------
# The pattern's object form (SE-01-009)
# ---------------------------------------------------------------------------


def _invite_pattern(form: ObjectForm | None) -> ActivityPattern:
    return ActivityPattern(
        activity_=TAtype.INVITE,
        object_=VOtype.VULNERABILITY_CASE,
        object_form=form,
    )


@pytest.mark.spec("SE-01-009")
def test_patterns_differing_only_in_form_each_match_only_their_own(
    held: tuple[SqliteDataLayer, VulnerabilityCase],
) -> None:
    _, case = held
    previewed = parse_activity(_invite(_previewed(case.id_)))
    whole = parse_activity(_invite(_whole(case), n=2))
    preview_pattern = _invite_pattern(ObjectForm.PREVIEWED_REFERENCE)
    whole_pattern = _invite_pattern(ObjectForm.WHOLE_OBJECT)

    assert preview_pattern.match(previewed)
    assert not preview_pattern.match(whole)
    assert whole_pattern.match(whole)
    assert not whole_pattern.match(previewed)


@pytest.mark.spec("SE-01-009")
def test_a_pattern_naming_no_form_does_not_read_a_preview_as_the_object(
    held: tuple[SqliteDataLayer, VulnerabilityCase],
) -> None:
    _, case = held
    pattern = _invite_pattern(None)

    assert pattern.match(parse_activity(_invite(_whole(case))))
    assert not pattern.match(parse_activity(_invite(_previewed(case.id_))))


@pytest.mark.spec("SE-01-009")
def test_a_whole_object_pattern_refuses_every_reference_form() -> None:
    pattern = _invite_pattern(ObjectForm.WHOLE_OBJECT)
    case_id = "https://example.org/cases/c1"
    as_uri = parse_activity(_invite(case_id))
    # A case reference without a preview, which the parse edge admits only
    # where a participant names its case (AKM-03-004), set in place.
    as_reference = parse_activity(_invite(_previewed(case_id)))
    object.__setattr__(
        as_reference,
        "object_",
        as_TypedReference(id_=case_id, type_="VulnerabilityCase"),
    )

    as_link = parse_activity(_invite({"type": "Link", "href": case_id}, n=3))

    assert not pattern.match(as_uri)
    assert not pattern.match(as_reference)
    assert not pattern.match(as_link)


@pytest.mark.spec("SE-01-009")
def test_no_registered_pattern_reads_a_preview_as_the_case(
    held: tuple[SqliteDataLayer, VulnerabilityCase],
) -> None:
    """Only the stub Invite and its answers ask for a previewed reference
    (ADR-0205), so an ``Invite`` of a preview is the stub Invite, and an
    activity no such pattern routes is unknown: never
    ``ANNOUNCE_VULNERABILITY_CASE`` or any other semantics that would read
    the preview as the case."""
    _, case = held
    asking = [
        entry.semantics.name
        for entry in SEMANTIC_REGISTRY
        if entry.pattern is not None
        and entry.pattern.object_form is ObjectForm.PREVIEWED_REFERENCE
    ]
    invite = parse_activity(_invite(_previewed(case.id_)))
    # The parse edge refuses an Announce of a preview (MV-10-002), so the
    # preview is set in place: the matcher must refuse it on its own.
    announce = parse_activity(
        {**_invite(_whole(case), n=2), "type": "Announce"}
    )
    object.__setattr__(announce, "object_", _object_chain_end(invite))

    assert asking == [MessageSemantics.INVITE_ACTOR_TO_CASE.name]
    assert find_matching_semantics(invite) is (
        MessageSemantics.INVITE_ACTOR_TO_CASE
    )
    assert find_matching_semantics(announce) is MessageSemantics.UNKNOWN


@pytest.mark.spec("SE-01-009")
@pytest.mark.parametrize(
    "kwargs",
    [
        pytest.param(
            {"object_": ActivityPattern(activity_=TAtype.INVITE)},
            id="nested-activity",
        ),
        pytest.param(
            {
                "object_": VOtype.VULNERABILITY_CASE,
                "accepts_bare_object": True,
            },
            id="bare-object",
        ),
    ],
)
def test_an_object_form_no_object_can_have_is_refused(
    kwargs: dict[str, Any],
) -> None:
    with pytest.raises(ValueError, match="SE-01-009"):
        ActivityPattern(
            activity_=TAtype.ACCEPT,
            object_form=ObjectForm.PREVIEWED_REFERENCE,
            **kwargs,
        )


# ---------------------------------------------------------------------------
# Rehydration and lookup leave it as received (MV-10-011, ADR-0205)
# ---------------------------------------------------------------------------


@pytest.mark.spec("MV-10-013")
@pytest.mark.spec("MV-10-011")
@pytest.mark.spec("AKM-05-007")
@pytest.mark.parametrize("wrap", [False, True], ids=["invite", "accept"])
def test_rehydration_keeps_a_previewed_reference_to_a_held_case(
    held: tuple[SqliteDataLayer, VulnerabilityCase], wrap: bool
) -> None:
    """The receiver holds the case, and the reference stays a reference, so
    the receiver still sees the stub Invite it was sent."""
    dl, case = held
    invite = _invite(_previewed(case.id_))
    activity = parse_activity(_accept(invite) if wrap else invite)

    rehydrated = rehydrate(activity, dl=dl)

    reference = _object_chain_end(rehydrated)
    assert is_previewed_reference(reference)
    assert not isinstance(reference, VulnerabilityCase)
    assert isinstance(rehydrated, as_Activity)
    assert bare_object_id(rehydrated) is None


@pytest.mark.spec("MV-10-013")
@pytest.mark.spec("MV-10-011")
def test_rehydrating_the_reference_alone_returns_it(
    held: tuple[SqliteDataLayer, VulnerabilityCase],
) -> None:
    dl, case = held
    reference = _object_chain_end(
        parse_activity(_invite(_previewed(case.id_)))
    )
    assert isinstance(reference, as_TypedReference)

    assert rehydrate(reference, dl=dl) is reference


@pytest.mark.spec("MV-10-013")
@pytest.mark.spec("MV-10-011")
@pytest.mark.parametrize("wrap", [False, True], ids=["invite", "accept"])
def test_a_stored_previewed_reference_reads_back_as_received(
    held: tuple[SqliteDataLayer, VulnerabilityCase], wrap: bool
) -> None:
    """A stored activity keeps the reference and its preview: a lookup never
    reads back the id of the case it names, which rehydration expands."""
    dl, case = held
    invite = _invite(_previewed(case.id_))
    activity = parse_activity(_accept(invite) if wrap else invite)
    dl.create(activity)

    for read_back in (
        record_to_object(object_to_record(activity)),
        dl.read(activity.id_),
    ):
        reference = _object_chain_end(read_back)
        assert is_previewed_reference(reference), type(reference)
        assert isinstance(reference, as_TypedReference)
        assert isinstance(reference.preview, as_CasePreview)
        assert reference.id_ == case.id_


@pytest.mark.spec("MV-10-013")
@pytest.mark.spec("MV-10-011")
@pytest.mark.spec("AKM-05-007")
def test_an_accept_naming_a_held_stub_invite_by_id_keeps_its_preview(
    held: tuple[SqliteDataLayer, VulnerabilityCase],
) -> None:
    """The CASE_MANAGER looks the Invite it sent up by id, and its object is
    the previewed reference it sent, not the case it holds (ADR-0205)."""
    dl, case = held
    invite = parse_activity(_invite(_previewed(case.id_)))
    dl.create(invite)

    rehydrated = rehydrate(parse_activity(_accept(invite.id_)), dl=dl)

    assert is_previewed_reference(_object_chain_end(rehydrated))
    assert isinstance(rehydrated, as_Activity)
    assert bare_object_id(rehydrated) is None


@pytest.mark.spec("MV-10-012")
def test_the_preview_field_holds_exactly_the_defined_previews() -> None:
    """Adding a type to ``DEFINED_PREVIEWS`` without widening the field would
    refuse its preview with a generic error instead of MV-10-012."""
    annotation = as_TypedReference.model_fields["preview"].annotation
    held = set(get_args(annotation)) - {type(None)}

    assert held == set(DEFINED_PREVIEWS.values())


@pytest.mark.spec("SE-01-009")
@pytest.mark.parametrize(
    ("obj", "whole"),
    [
        pytest.param(
            {"id": "https://example.org/actors/carol", "type": "Person"},
            False,
            id="actor-reference",
        ),
        pytest.param(
            {
                "id": "https://example.org/actors/carol/inbox",
                "type": "Collection",
            },
            False,
            id="collection-address",
        ),
        pytest.param(
            {
                "id": "https://example.org/actors/carol",
                "type": "Person",
                "name": "Carol",
            },
            True,
            id="actor-profile",
        ),
    ],
)
def test_a_whole_object_pattern_reads_an_identity_alone_as_a_reference(
    obj: dict[str, Any], whole: bool
) -> None:
    pattern = ActivityPattern(
        activity_=TAtype.INVITE, object_form=ObjectForm.WHOLE_OBJECT
    )

    assert pattern.match(parse_activity(_invite(obj))) is whole


@pytest.mark.spec("MV-10-013")
def test_a_malformed_stored_preview_fails_its_read() -> None:
    """A stored preview that is no stub is refused on read, never read back
    as a reference without one or as the case."""
    activity = parse_activity(
        _invite(_previewed("https://example.org/cases/c1"))
    )
    record = object_to_record(activity)
    record.data_["object_"]["preview"] = "https://example.org/cases/c1/stub"

    with pytest.raises(ValidationError):
        record_to_object(record)


@pytest.mark.spec("MV-10-012")
def test_a_stored_preview_on_a_type_without_one_fails_its_read() -> None:
    """The stored read skips the parse edge, so the reference class refuses
    a preview its type does not define on its own."""
    activity = parse_activity(
        _invite(_previewed("https://example.org/cases/c1"))
    )
    record = object_to_record(activity)
    record.data_["object_"]["type"] = "Note"

    with pytest.raises(ValidationError, match="MV-10-012"):
        record_to_object(record)
