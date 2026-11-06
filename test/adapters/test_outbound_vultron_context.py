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

"""Outbound activities cite the Vultron JSON-LD context (VM-10-001, #5168).

The body the outbox seals and delivers is ``dump_outbound_body``'s text, so
that is what these tests read.  Each verb a ``SEMANTIC_REGISTRY`` pattern
matches is rendered from the vocab examples, which build every outbound
activity shape the protocol uses.
"""

import json
from typing import Any

import pytest

from vultron.adapters.outbox_sealed_body import dump_outbound_body
from vultron.semantic_registry import SEMANTIC_REGISTRY
from vultron.wire.as2.parser import parse_activity
from vultron.wire.as2.vocab.base.base import (
    ACTIVITY_STREAMS_NS,
    VULTRON_CONTEXT_URI,
)
from vultron.wire.as2.vocab.base.objects.activities.base import as_Activity
from vultron.wire.as2.vocab.examples.vocab_examples import EXAMPLES


def _outbound_activity_bodies() -> dict[str, dict[str, Any]]:
    """One sealed body per activity verb the examples build."""
    bodies: dict[str, dict[str, Any]] = {}
    for build, _filename in EXAMPLES:
        obj = build()
        if isinstance(obj, as_Activity):
            bodies.setdefault(
                str(obj.type_), json.loads(dump_outbound_body(obj))
            )
    return bodies


_BODIES = _outbound_activity_bodies()
_REGISTRY_VERBS = sorted(
    {
        str(e.pattern.activity_)
        for e in SEMANTIC_REGISTRY
        if e.pattern is not None
    }
)


def test_examples_cover_every_registry_verb():
    """Every verb a registry pattern matches has an example to render."""
    assert set(_REGISTRY_VERBS) <= set(_BODIES)


@pytest.mark.spec("VM-10-001")
@pytest.mark.parametrize("verb", _REGISTRY_VERBS)
def test_outbound_activity_sets_the_vultron_context(verb: str):
    """The top-level ``@context`` of each outbound verb is the Vultron one."""
    assert _BODIES[verb]["@context"] == VULTRON_CONTEXT_URI


def _nested_contexts(value: Any) -> list[Any]:
    found: list[Any] = []
    if isinstance(value, dict):
        for key, item in value.items():
            if key == "@context":
                continue
            if isinstance(item, dict) and "@context" in item:
                found.append(item["@context"])
            found.extend(_nested_contexts(item))
    elif isinstance(value, list):
        for item in value:
            if isinstance(item, dict) and "@context" in item:
                found.append(item["@context"])
            found.extend(_nested_contexts(item))
    return found


@pytest.mark.spec("VM-10-001")
@pytest.mark.parametrize("verb", _REGISTRY_VERBS)
def test_nested_objects_repeat_only_the_enclosing_context(verb: str):
    """A nested object's ``@context``, when present, is the activity's own.

    Nested objects keep the ``@context`` they carry as stand-alone documents,
    so an inline object restates its activity's context.  Restating the
    identical context is a JSON-LD no-op, so it never changes how a term in
    the nested object expands.
    """
    body = _BODIES[verb]
    assert all(ctx == body["@context"] for ctx in _nested_contexts(body))


def test_inbound_activity_with_the_as2_namespace_still_parses():
    """Receive stays permissive: an AS2-namespace activity parses (AC-3)."""
    body = dict(_BODIES["Offer"])
    body["@context"] = ACTIVITY_STREAMS_NS

    parsed = parse_activity(body)

    assert parsed.type_ == "Offer"
    assert parsed.context_ == ACTIVITY_STREAMS_NS
