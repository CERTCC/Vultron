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
"""Architecture ratchet: received evidence and trigger payloads (VM-08-002, VM-08-003).

VM-08-002 used to be held by ``frozen=True`` on ``as_Object``, and the gate
checked exactly that flag.  Pydantic's ``frozen`` does not reach into nested
models, though, and ADR-0099 detail 3 made every paired nested object a mutable
core class, so the flag vouched for the envelope while the case, report,
participant and status inside it stayed writable.  The evidence is now the
received body itself, sealed as JSON text at ``parse_activity`` before anything
expands or validates it (ISSUE-3584).

The gate is therefore per class rather than per flag.  For every class reachable
in a parsed example tree it tampers with each instance of that class, bypassing
``frozen`` the way any in-process writer can, and asserts the evidence still
equals the body the sender delivered.  A class added to the vocabulary joins the
check the first time an example carries it.

``test_trigger_activity_port_returns_wire_blob_not_dict`` covers VM-08-003 (#2653).
"""

import typing
from collections.abc import Iterator
from typing import Any

import pytest
from pydantic import BaseModel

from test.architecture._vocab_example_corpus import (
    activity_examples,
    wire_body,
)
from vultron.core.models.base import CoreObject
from vultron.wire.as2.errors import VultronParseError
from vultron.wire.as2.parser import parse_activity
from vultron.wire.as2.vocab.base.objects.activities.base import as_Activity

# Examples no receiver can parse, so they carry no received evidence to check.
# Each entry names the decision or issue that owns it; the collection check below
# keeps an entry from outliving the example it names.
_UNPARSEABLE = {
    "choose_preferred_embargo": "ADR-0100 — the multi-candidate embargo poll is retired, so this example is emit-only by decision; its as_Question does not validate inbound. Removed with the class by #3469",
}

_TAMPERED = "urn:vultron:test:tampered"


#: Example name → parse error, for examples that should parse and do not.
_PARSE_FAILURES: dict[str, str] = {}


def _parsed_corpus() -> dict[str, tuple[dict[str, Any], as_Activity]]:
    corpus: dict[str, tuple[dict[str, Any], as_Activity]] = {}
    for name, example in activity_examples().items():
        if name in _UNPARSEABLE:
            continue
        body = wire_body(example)
        try:
            corpus[name] = (body, parse_activity(body))
        except VultronParseError as exc:
            _PARSE_FAILURES[name] = str(exc)
    return corpus


def _walk(value: object) -> Iterator[BaseModel]:
    """Every model instance reachable from *value*, depth first."""
    if isinstance(value, BaseModel):
        yield value
        for field_name in type(value).model_fields:
            yield from _walk(value.__dict__.get(field_name))
    elif isinstance(value, (list, tuple, set, frozenset)):
        for item in value:
            yield from _walk(item)
    elif isinstance(value, dict):
        for item in value.values():
            yield from _walk(item)


def _tamper(instance: BaseModel) -> None:
    """Overwrite every set field on *instance*, the way any in-process writer can.

    Writing the instance ``__dict__`` bypasses ``frozen``, ``validate_assignment`` and every
    validator, so this is the strongest mutation a holder of the object can make,
    and it is the one a class config cannot stop.
    """
    for field_name in instance.model_fields_set:
        vars(instance)[field_name] = _TAMPERED


_CORPUS = _parsed_corpus()

#: Class name → names of the examples whose parsed tree carries that class.
_REACHABLE: dict[str, list[str]] = {}
_CLASSES: dict[str, type[BaseModel]] = {}
for _name, (_body, _activity) in _CORPUS.items():
    for _instance in _walk(_activity):
        _cls = type(_instance)
        _key = f"{_cls.__module__}.{_cls.__qualname__}"
        _CLASSES[_key] = _cls
        if _name not in _REACHABLE.setdefault(_key, []):
            _REACHABLE[_key].append(_name)


def test_corpus_parses_and_reaches_mutable_classes():
    """The gate must cover the classes ``frozen`` never protected (DF-09-009).

    A corpus that parses nothing, or reaches only frozen wire classes, passes the
    per-class test below vacuously, and those are exactly the classes the old
    ``frozen`` gate already vouched for.
    """
    assert _CORPUS, "no example activity parsed; the corpus is empty"
    mutable = sorted(
        key
        for key, cls in _CLASSES.items()
        if issubclass(cls, CoreObject) and not cls.model_config.get("frozen")
    )
    assert mutable, (
        "no mutable core class is reachable in any parsed example, so the "
        "per-class tamper test is not exercising what VM-08-002 guards"
    )


def test_every_example_parses_as_delivered():
    """An example a receiver refuses documents a wire form that does not work.

    Each body is dumped the way ``outbox_delivery`` sends it.  The three
    ``CaseProposal`` examples failed here until the docs generator dumped the
    same way (#3745).
    """
    assert not _PARSE_FAILURES, "\n".join(
        f"{name}: {error}" for name, error in sorted(_PARSE_FAILURES.items())
    )


def test_unparseable_exemptions_are_collected():
    """An exemption for an example nobody collects hides nothing and must go."""
    missing = sorted(set(_UNPARSEABLE) - set(activity_examples()))
    assert not missing, f"_UNPARSEABLE names uncollected examples: {missing}"


@pytest.mark.spec("VM-08-002")
@pytest.mark.parametrize("example_name", sorted(_CORPUS))
def test_evidence_is_the_delivered_body(example_name: str):
    """What the parser seals is the sender's body, not a re-serialization."""
    body, activity = _CORPUS[example_name]

    assert activity.received_evidence == body


@pytest.mark.spec("VM-08-002")
@pytest.mark.parametrize("class_key", sorted(_REACHABLE))
def test_tampering_with_a_reachable_class_leaves_the_evidence(class_key: str):
    """No object parsed from the body can reach the evidence taken from it.

    Parsed afresh per class so one class's tampering cannot mask another's.
    """
    for example_name in _REACHABLE[class_key]:
        body = _CORPUS[example_name][0]
        activity = parse_activity(body)
        targets = [
            i
            for i in _walk(activity)
            if f"{type(i).__module__}.{type(i).__qualname__}" == class_key
        ]
        assert targets, f"{example_name} no longer carries {class_key}"
        assert any(
            i.model_fields_set for i in targets
        ), f"no {class_key} in {example_name} has a field to tamper with"

        for instance in targets:
            _tamper(instance)

        assert activity.received_evidence == body, (
            f"tampering with a parsed {class_key} in {example_name} changed the "
            "received evidence (VM-08-002)"
        )


@pytest.mark.spec("VM-08-003")
def test_trigger_activity_port_returns_wire_blob_not_dict():
    """TriggerActivityPort activity methods must return frozen wire blobs, not dicts (VM-08-003)."""
    from vultron.core.ports.trigger_activity import TriggerActivityPort

    hints = typing.get_type_hints(TriggerActivityPort.submit_report)
    return_type = hints.get("return")
    assert (
        return_type is not None
    ), "submit_report must have a return type annotation"
    type_args = typing.get_args(return_type)
    assert (
        len(type_args) == 2
    ), "return type must be a 2-tuple (activity_id, payload)"
    payload_type = type_args[1]
    # Currently dict[str, Any]: get_origin returns dict → assertion fails (xfail).
    # After #2653, payload_type is a frozen wire object: get_origin returns None → passes.
    assert typing.get_origin(payload_type) is not dict
