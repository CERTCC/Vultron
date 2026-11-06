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
that is what these tests read.  Every activity the vocab examples build is
rendered; they cover each verb a ``SEMANTIC_REGISTRY`` pattern matches and
every outbound activity shape the protocol uses.
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


def _nested_contexts(value: Any, *, top: bool = True) -> list[Any]:
    """Every ``@context`` below the top level of ``value``."""
    found: list[Any] = []
    if isinstance(value, dict):
        if not top and "@context" in value:
            found.append(value["@context"])
        for key, item in value.items():
            if key != "@context":
                found.extend(_nested_contexts(item, top=False))
    elif isinstance(value, list):
        for item in value:
            found.extend(_nested_contexts(item, top=False))
    return found


def test_examples_cover_every_registry_verb():
    """Every verb a registry pattern matches has an example to render."""
    rendered = {str(body["type"]) for body in _BODIES.values()}
    assert set(_REGISTRY_VERBS) <= rendered


def test_examples_include_nested_contexts():
    """The nested check below has objects to inspect, so it cannot pass empty."""
    assert any(_nested_contexts(body) for body in _BODIES.values())


@pytest.mark.spec("VM-10-001")
@pytest.mark.parametrize("example", _EXAMPLE_NAMES)
def test_outbound_activity_sets_the_vultron_context(example: str):
    """The top-level ``@context`` of each outbound activity is the Vultron one."""
    assert _BODIES[example]["@context"] == VULTRON_CONTEXT_URI


@pytest.mark.spec("VM-10-001")
@pytest.mark.parametrize("example", _EXAMPLE_NAMES)
def test_nested_objects_repeat_only_the_enclosing_context(example: str):
    """A nested object the implementation builds restates the activity's context.

    Each object it builds keeps the ``@context`` it carries as a stand-alone
    document, so an inline object restates its activity's context.  Restating
    the identical context is a JSON-LD no-op, so it never changes how a term
    in the nested object expands.  (An embedded object received from a peer
    keeps the context it arrived with; these examples build every object.)
    """
    body = _BODIES[example]
    assert all(ctx == body["@context"] for ctx in _nested_contexts(body))


def test_inbound_activity_with_the_as2_namespace_still_parses():
    """Receive stays permissive: an AS2-namespace activity parses (AC-3)."""
    body = dict(next(b for b in _BODIES.values() if b["type"] == "Offer"))
    body["@context"] = ACTIVITY_STREAMS_NS

    parsed = parse_activity(body)

    assert parsed.type_ == "Offer"
    assert parsed.context_ == ACTIVITY_STREAMS_NS
