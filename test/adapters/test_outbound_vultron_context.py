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

"""Outbound documents cite AS2 and the Vultron JSON-LD context (VM-10-001).

The body the outbox seals and delivers is ``dump_outbound_body``'s text, so
that is what these tests read.  Every activity the vocab examples build is
rendered; they cover each verb a ``SEMANTIC_REGISTRY`` pattern matches and
every outbound activity shape the protocol uses (#5168, #6006).
"""

import json
from typing import Any

import pytest

from vultron.adapters.outbox_sealed_body import dump_outbound_body
from vultron.core.models.base.context import DEFAULT_JSONLD_CONTEXT
from vultron.core.models.report import VulnerabilityReport
from vultron.semantic_registry import SEMANTIC_REGISTRY
from vultron.wire.as2 import signing
from vultron.wire.as2.parser import parse_activity
from vultron.wire.as2.vocab.base.base import (
    ACTIVITY_STREAMS_NS,
    VULTRON_CONTEXT_URI,
)
from vultron.wire.as2.vocab.base.objects.activities.base import as_Activity
from vultron.wire.as2.vocab.examples.vocab_examples import EXAMPLES

_DEFAULT_CONTEXT = [ACTIVITY_STREAMS_NS, VULTRON_CONTEXT_URI]


def _outbound_activity_bodies() -> dict[str, dict[str, Any]]:
    """The sealed body of every activity the examples build, by builder name."""
    bodies: dict[str, dict[str, Any]] = {}
    for build, _filename in EXAMPLES:
        obj = build()
        if isinstance(obj, as_Activity):
            bodies[build.__name__] = json.loads(dump_outbound_body(obj))
    return bodies


_BODIES = _outbound_activity_bodies()
_EXAMPLE_NAMES = sorted(_BODIES)
_REGISTRY_VERBS = sorted(
    {
        str(e.pattern.activity_)
        for e in SEMANTIC_REGISTRY
        if e.pattern is not None
    }
)


def _nested_objects(value: Any, *, top: bool = True) -> list[dict[str, Any]]:
    """Every object (a dict with a ``type``) below the top level of ``value``."""
    found: list[dict[str, Any]] = []
    if isinstance(value, dict):
        if not top and "type" in value:
            found.append(value)
        for key, item in value.items():
            if key != "@context":
                found.extend(_nested_objects(item, top=False))
    elif isinstance(value, list):
        for item in value:
            found.extend(_nested_objects(item, top=False))
    return found


def _offer_body() -> dict[str, Any]:
    return dict(next(b for b in _BODIES.values() if b["type"] == "Offer"))


def _report() -> VulnerabilityReport:
    return VulnerabilityReport(
        id_="https://example.org/reports/1", name="FDR-1", content="x"
    )


def test_the_default_context_constant_is_as2_then_vultron():
    """The shared default both layers emit is the VM-10-001 list."""
    assert list(DEFAULT_JSONLD_CONTEXT) == _DEFAULT_CONTEXT


def test_examples_cover_every_registry_verb():
    """Every verb a registry pattern matches has an example to render."""
    rendered = {str(body["type"]) for body in _BODIES.values()}
    assert set(_REGISTRY_VERBS) <= rendered


def test_examples_include_nested_objects():
    """The nested check below has objects to inspect, so it cannot pass empty."""
    assert any(_nested_objects(body) for body in _BODIES.values())


@pytest.mark.spec("VM-10-001")
@pytest.mark.parametrize("example", _EXAMPLE_NAMES)
def test_outbound_activity_cites_as2_then_the_vultron_context(example: str):
    """Each outbound activity's top-level ``@context`` is the two-entry list."""
    assert _BODIES[example]["@context"] == _DEFAULT_CONTEXT


#: Examples that embed a document received from a peer, by the key holding it.
#: That document is carried as received, so it keeps the ``@context`` it
#: arrived with (a refusal carries the refused activity, CLP-05-001).
_RECEIVED_EMBEDS: dict[str, str] = {"refusal_notice": "object"}


@pytest.mark.spec("VM-10-004")
@pytest.mark.spec("VM-10-005")
@pytest.mark.parametrize("example", _EXAMPLE_NAMES)
def test_nested_objects_do_not_restate_the_context(example: str):
    """An object the implementation nests in an activity carries no ``@context``.

    The activity's context already applies to every object inside it.  An
    embedded document received from a peer is not built here, so it is left
    out (:data:`_RECEIVED_EMBEDS`).
    """
    body = dict(_BODIES[example])
    body.pop(_RECEIVED_EMBEDS.get(example, ""), None)
    nested = _nested_objects(body)
    assert [obj for obj in nested if "@context" in obj] == []


@pytest.mark.spec("VM-10-004")
@pytest.mark.parametrize("example", sorted(_RECEIVED_EMBEDS))
def test_an_embedded_received_document_keeps_its_context(example: str):
    """A received document carried inline keeps the context it arrived with."""
    embedded = _BODIES[example][_RECEIVED_EMBEDS[example]]

    assert embedded["@context"] == _DEFAULT_CONTEXT


@pytest.mark.spec("VM-10-001")
def test_a_stand_alone_core_object_carries_the_context():
    """A core object dumped on its own is a top-level document."""
    dumped = _report().model_dump(by_alias=True, exclude_none=True)

    assert dumped["@context"] == _DEFAULT_CONTEXT


@pytest.mark.spec("VM-10-001")
def test_a_stand_alone_wire_object_carries_the_context():
    """A wire object dumped on its own is a top-level document."""
    activity = parse_activity(_offer_body())

    assert activity.to_dict()["@context"] == _DEFAULT_CONTEXT


@pytest.mark.parametrize(
    "context",
    [
        VULTRON_CONTEXT_URI,
        [ACTIVITY_STREAMS_NS, VULTRON_CONTEXT_URI],
        [VULTRON_CONTEXT_URI, ACTIVITY_STREAMS_NS],
    ],
    ids=["vultron-string", "default-list", "reordered-list"],
)
def test_inbound_activity_parses_any_context_form(context: Any):
    """Receive stays permissive: a string or a list ``@context`` parses.

    The activity keeps the context it arrived with, so it dumps that context
    again rather than being relabelled.  The AS2 string alone, a signed body's
    list and the refused forms are pinned in
    ``test/wire/as2/test_signed_body_context.py``.
    """
    body = _offer_body()
    body["@context"] = context

    parsed = parse_activity(body)

    assert parsed.type_ == "Offer"
    assert parsed.to_dict()["@context"] == context


@pytest.mark.spec("VM-10-005")
def test_inbound_nested_object_keeps_its_own_context():
    """A received nested object with a context of its own keeps it."""
    body = _offer_body()
    body["object"] = {**body["object"], "@context": VULTRON_CONTEXT_URI}

    parsed = parse_activity(body)

    assert parsed.to_dict()["object"]["@context"] == VULTRON_CONTEXT_URI


def test_the_default_context_round_trips_as_absent():
    """A core object read back from its AS2 dump equals the original (ARCH-23-005)."""
    report = _report()

    again = VulnerabilityReport.model_validate(
        report.model_dump(by_alias=True)
    )

    assert again.context_ is None
    assert again == report


def test_a_signed_outbound_body_lists_every_context_and_parses():
    """Signing appends the data-integrity context to the default list."""
    body = _offer_body()
    key = signing.seeded_signing_key(body["actor"])

    signed = signing.sign(body, key)

    assert signed["@context"] == [
        *_DEFAULT_CONTEXT,
        signing.DATA_INTEGRITY_CONTEXT,
    ]
    signing.verify(signed, key.public_key_multibase)
    assert parse_activity(signed).context_ == signed["@context"]
