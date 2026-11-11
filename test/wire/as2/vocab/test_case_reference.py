#  Copyright (c) 2023-2025 Carnegie Mellon University and Contributors.
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

"""A case reference on the wire: an Object whose ``url`` is an AS2 Link (#6249)."""

import logging
from typing import Any

import pytest

import vultron.wire.as2.vocab.objects.case_reference as cr
from test.support.objects import make
from vultron.core.models.case_reference import (
    CASE_REFERENCE_REL_NAMESPACE,
    CaseReference,
)
from vultron.core.models.enums import VultronObjectType as VO_type
from vultron.wire.as2.errors import VultronParseValidationError
from vultron.wire.as2.parser import parse_activity
from vultron.wire.as2.vocab.base.links import as_Link

_HREF = "https://example.org/advisory/"
_PATCH = f"{CASE_REFERENCE_REL_NAMESPACE}patch"
_PUBLISHED = "2026-01-01T00:00:00Z"


def _create(reference: dict[str, Any]) -> dict[str, Any]:
    """A ``Create`` activity body carrying *reference* inline."""
    return {
        "@context": "https://www.w3.org/ns/activitystreams",
        "type": "Create",
        "id": "urn:test:create:1",
        "actor": "https://example.org/actor/alice",
        "published": _PUBLISHED,
        "object": reference,
    }


def _reference(url: object, **extra: object) -> dict[str, Any]:
    return {
        "type": "CaseReference",
        "id": "urn:test:reference:1",
        "published": _PUBLISHED,
        "url": url,
        **extra,
    }


def _parsed(body: dict[str, Any]) -> CaseReference:
    reference = getattr(parse_activity(body), "object_", None)
    assert isinstance(reference, CaseReference)
    return reference


def test_wire_alias_is_the_core_class():
    assert cr.as_CaseReference is CaseReference


def test_reference_renders_its_url_as_a_link():
    ref = make(
        cr.as_CaseReference,
        url={
            "href": _HREF,
            "name": "Vendor bulletin",
            "media_type": "text/html",
            "rel": [_PATCH, "related"],
        },
        name="Example Security Advisory",
    )
    dumped = ref.model_dump(by_alias=True, mode="json", exclude_none=True)
    assert dumped["type"] == VO_type.CASE_REFERENCE
    assert dumped["name"] == "Example Security Advisory"
    assert dumped["url"] == {
        "type": "Link",
        "href": _HREF,
        "name": "Vendor bulletin",
        "mediaType": "text/html",
        "rel": [_PATCH, "related"],
    }
    assert "tags" not in dumped


def test_rendered_reference_parses_back_unchanged():
    ref = make(
        cr.as_CaseReference,
        url={"href": _HREF, "media_type": "text/html", "rel": [_PATCH]},
        name="Advisory",
    )
    body = _create(
        ref.model_dump(by_alias=True, mode="json", exclude_none=True)
    )
    assert _parsed(body) == ref


def test_a_single_rel_string_parses_as_a_list():
    link = {"type": "Link", "href": _HREF, "rel": "related"}
    assert _parsed(_create(_reference(link))).url.rel == ["related"]


def test_an_untyped_link_dict_parses():
    reference = _parsed(_create(_reference({"href": _HREF})))
    assert reference.url.href == _HREF
    assert reference.url.type_ == "Link"


@pytest.mark.parametrize(
    "url, fault",
    [
        pytest.param(
            {"type": "Link", "href": _HREF, "rel": ["patch"]},
            "Invalid rel",
            id="bare-cve-tag",
        ),
        pytest.param({"type": "Link", "name": "x"}, "href", id="no-href"),
        pytest.param(_HREF, "url", id="bare-string-url"),
    ],
)
def test_a_malformed_link_refuses_the_activity(url: object, fault: str):
    with pytest.raises(VultronParseValidationError, match=r"(?s)" + fault):
        parse_activity(_create(_reference(url)))


def _set_aside_records(caplog: pytest.LogCaptureFixture) -> list[str]:
    return [
        record.getMessage()
        for record in caplog.records
        if record.levelno == logging.INFO
        and "Set aside unknown key" in record.getMessage()
    ]


@pytest.mark.parametrize(
    "key, value",
    [
        pytest.param("hreflang", "en", id="an-as2-link-property"),
        pytest.param("id", "urn:test:link:1", id="an-id-a-link-does-not-hold"),
    ],
)
def test_a_link_key_a_reference_does_not_hold_is_set_aside_and_reported(
    caplog: pytest.LogCaptureFixture, key: str, value: str
):
    """The walk decides a typed Link's keys against ``CaseReferenceLink``,
    the slot's own class, so it reports them with the activity's ids and
    the key's location (MV-11-003, SL-02-001)."""
    link = {"type": "Link", "href": _HREF, key: value, "rel": [_PATCH]}
    with caplog.at_level(logging.INFO):
        reference = _parsed(_create(_reference(link)))
    assert reference.url.href == _HREF
    assert reference.url.rel == [_PATCH]
    [record] = _set_aside_records(caplog)
    assert repr(key) in record
    assert "'object.url'" in record
    assert "urn:test:create:1" in record


def test_a_link_with_its_own_context_parses_with_nothing_set_aside(
    caplog: pytest.LogCaptureFixture,
):
    link = {
        "@context": "https://www.w3.org/ns/activitystreams",
        "type": "Link",
        "href": _HREF,
    }
    with caplog.at_level(logging.INFO):
        reference = _parsed(_create(_reference(link)))
    assert reference.url.href == _HREF
    assert _set_aside_records(caplog) == []


def test_a_url_holding_another_object_type_is_refused():
    with pytest.raises(VultronParseValidationError, match="url"):
        parse_activity(
            _create(_reference({"type": "Note", "content": "not a link"}))
        )


def test_a_tags_key_is_not_read(caplog: pytest.LogCaptureFixture):
    """``tags`` is gone with no alias: an arriving one is set aside and
    reported, and fills nothing (ADR-0175, MV-11-003)."""
    body = _create(_reference({"type": "Link", "href": _HREF}, tags=["patch"]))
    with caplog.at_level(logging.INFO):
        reference = _parsed(body)
    assert reference.url.rel == []
    [record] = _set_aside_records(caplog)
    assert "'tags'" in record


def test_wire_link_rel_is_not_functional():
    """AS2 ``rel`` takes one value or several (VOC ``rel``)."""
    assert as_Link.model_validate({"rel": "related"}).rel == "related"
    assert as_Link.model_validate({"rel": ["related", _PATCH]}).rel == [
        "related",
        _PATCH,
    ]
