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
"""A sender inlines every object its activity introduces (AKM-02-004).

A receiver never has to reconstruct an object the sender already held, so first
delivery does not depend on a fetch.  Two ratchets hold this:

- every public activity factory is classified.  One that introduces an object
  refuses that object as a bare id and carries it inline; one that builds the
  object it introduces from its arguments carries it inline; every other
  factory names why it introduces nothing.  A new factory with no entry fails,
  so it cannot be added unexamined.
- every example activity an implementer copies carries what it introduces
  inline, including the reports and participants of a case it creates or
  announces (CBT-01-012).

References to objects the receiver already holds may stay bare: a case in
``target``, the participant a status is added to, an actor named by URI
(AKM-05-001).
"""

import importlib
import inspect
import pkgutil
import types
import typing
from collections.abc import Callable, Hashable, Sequence
from dataclasses import dataclass
from typing import Any, cast

import pytest

from test.architecture._vocab_example_corpus import (
    activity_examples,
    wire_body,
)
from vultron.core.states.participant_embargo_consent import (
    EmbargoConsentState,
)
from vultron.enums.roles import CVDRole
from vultron.wire.as2 import factories as factories_package
from vultron.wire.as2.factories import (
    VultronActivityConstructionError,
    add_note_to_case_activity,
    add_participant_to_case_activity,
    add_report_to_case_activity,
    add_status_to_case_activity,
    add_status_to_participant_activity,
    announce_log_entry_activity,
    announce_vulnerability_case_activity,
    create_case_activity,
    create_embargo_consent_activity,
    create_participant_activity,
    create_processing_fault_activity,
    em_propose_embargo_activity,
    offer_case_participant_activity,
    offer_case_participant_role_activity,
    rm_create_report_activity,
    rm_invite_to_case_activity,
    rm_submit_report_activity,
)
from vultron.wire.as2.factories.case import create_case_proposal_activity
from vultron.wire.as2.vocab.base.objects.activities.base import as_Activity
from vultron.wire.as2.vocab.base.objects.actors import as_Actor
from vultron.wire.as2.vocab.examples import vocab_examples
from vultron.wire.as2.vocab.examples.case_proposal import vendor_profile
from vultron.wire.as2.vocab.objects.embargo_consent import as_EmbargoConsent

_ACTOR = "https://example.org/actors/coordinator"
_PEER = "https://example.org/actors/vendor"
_CASE = "https://example.org/cases/c1"
_PARTICIPANT = f"{_CASE}/participants/vendor"
_BARE = "https://example.org/objects/introduced-by-id"


def _example_object(example: str) -> Callable[[], Any]:
    """The inline object a committed example activity carries."""
    return lambda: getattr(vocab_examples, example)().object_


def _consent_row() -> as_EmbargoConsent:
    return as_EmbargoConsent(
        embargo_id=f"{_CASE}/embargoes/e1",
        state=EmbargoConsentState.UNINVITED,
        attributed_to=_PEER,
    )


#: Factories whose activity introduces an object: ``(build, inline object)``.
#: ``build`` takes the introduced object, inline or as a bare id.
INTRODUCES: dict[
    str, tuple[Callable[[Any], as_Activity], Callable[[], Any]]
] = {
    "create_case_activity": (
        lambda o: create_case_activity(o, actor=_ACTOR),
        _example_object("create_case"),
    ),
    "create_participant_activity": (
        lambda o: create_participant_activity(o, target=_CASE, actor=_ACTOR),
        _example_object("create_participant"),
    ),
    "create_embargo_consent_activity": (
        lambda o: create_embargo_consent_activity(o, actor=_ACTOR),
        _consent_row,
    ),
    "rm_create_report_activity": (
        lambda o: rm_create_report_activity(o, actor=_ACTOR),
        _example_object("create_report"),
    ),
    "create_case_proposal_activity": (
        lambda o: create_case_proposal_activity(
            actor=vendor_profile(), proposal=o, to=[_PEER]
        ),
        _example_object("create_case_proposal"),
    ),
    "create_processing_fault_activity": (
        lambda o: create_processing_fault_activity(
            actor=_ACTOR, fault=o, to=[_PEER]
        ),
        _example_object("create_processing_fault"),
    ),
    "add_note_to_case_activity": (
        lambda o: add_note_to_case_activity(o, target=_CASE, actor=_ACTOR),
        _example_object("add_note_to_case"),
    ),
    "add_report_to_case_activity": (
        lambda o: add_report_to_case_activity(o, target=_CASE, actor=_ACTOR),
        _example_object("add_report_to_case"),
    ),
    "add_status_to_case_activity": (
        lambda o: add_status_to_case_activity(o, target=_CASE, actor=_ACTOR),
        _example_object("add_status_to_case"),
    ),
    "add_status_to_participant_activity": (
        lambda o: add_status_to_participant_activity(
            o, target=_PARTICIPANT, actor=_ACTOR
        ),
        _example_object("add_status_to_participant"),
    ),
    "add_participant_to_case_activity": (
        lambda o: add_participant_to_case_activity(
            o, target=_CASE, actor=_ACTOR
        ),
        _example_object("add_vendor_participant_to_case"),
    ),
    # First delivery of the object to its receiver, though not a Create/Add.
    "rm_submit_report_activity": (
        lambda o: rm_submit_report_activity(o, to=_PEER, actor=_ACTOR),
        _example_object("submit_report"),
    ),
    "em_propose_embargo_activity": (
        lambda o: em_propose_embargo_activity(
            o, context=_CASE, actor=_ACTOR, to=[_PEER]
        ),
        _example_object("propose_embargo"),
    ),
    "announce_vulnerability_case_activity": (
        lambda o: announce_vulnerability_case_activity(
            o, actor=_ACTOR, to=[_PEER]
        ),
        _example_object("announce_case"),
    ),
    "announce_log_entry_activity": (
        lambda o: announce_log_entry_activity(o, actor=_ACTOR, to=[_PEER]),
        _example_object("announce_case_ledger_entry"),
    ),
}

#: Factories that build the object they introduce from their arguments, so
#: there is no object to pass as an id: ``(build, the slot it travels in)``.
BUILDS_WHAT_IT_INTRODUCES: dict[str, tuple[Callable[[], as_Activity], str]] = {
    "offer_case_participant_activity": (
        lambda: offer_case_participant_activity(
            _PEER, target=_CASE, actor=_ACTOR, to=[_ACTOR]
        ),
        "object",
    ),
    "offer_case_participant_role_activity": (
        lambda: offer_case_participant_role_activity(
            role=CVDRole.CASE_MANAGER,
            target_actor=as_Actor(id_=_PEER),
            case=_CASE,
            actor=_ACTOR,
            to=[_PEER],
        ),
        "object",
    ),
    # The invitee does not hold the case yet, so the stub Invite introduces
    # it: the stub, built from a case given only by URI, goes in ``target``
    # (CM-17-002, MV-10-001).
    "rm_invite_to_case_activity": (
        lambda: rm_invite_to_case_activity(
            _PEER, target=_CASE, actor=_ACTOR, to=[_PEER]
        ),
        "target",
    ),
}


@dataclass(frozen=True)
class NoIntroduction:
    """Why a factory introduces no object, and the parameter its ``object`` is.

    ``object_parameter`` names the argument that becomes the activity's
    ``object`` when that object is an activity it answers or an object the
    receiver holds; it is ``None`` when the factory carries neither.
    """

    reason: str
    object_parameter: str | None = None


_ANSWERS = "answers an activity, which it embeds inline"
_HELD = "acts on an object the receiver already holds (AKM-02-004)"


def _answers(object_parameter: str) -> NoIntroduction:
    return NoIntroduction(_ANSWERS, object_parameter)


def _held(object_parameter: str) -> NoIntroduction:
    return NoIntroduction(_HELD, object_parameter)


_ACTOR_REF = NoIntroduction(
    "names an actor, which exists apart from the case and is addressed by"
    " its URI (AKM-05-001)"
)

#: Factories that introduce no object, and why.
INTRODUCES_NOTHING: dict[str, NoIntroduction] = {
    "accept_actor_recommendation_activity": _answers("offer"),
    "reject_actor_recommendation_activity": _answers("offer"),
    "accept_case_participant_offer_activity": _answers("offer"),
    "reject_case_participant_offer_activity": _answers("offer"),
    "accept_case_participant_role_activity": _answers("offer"),
    "reject_case_participant_role_activity": _answers("offer"),
    "accept_case_ownership_transfer_activity": _answers("offer"),
    "reject_case_ownership_transfer_activity": _answers("offer"),
    "undo_case_ownership_transfer_activity": _answers("proposal"),
    "accept_case_proposal_activity": _answers("proposal"),
    "reject_case_proposal_activity": _answers("proposal"),
    "reject_close_case_activity": _answers("leave"),
    "rm_accept_invite_to_case_activity": _answers("invite"),
    "rm_reject_invite_to_case_activity": _answers("invite"),
    "rm_accept_full_case_invite_activity": _answers("invite"),
    "rm_tentative_reject_full_case_invite_activity": _answers("invite"),
    "rm_reject_full_case_invite_activity": _answers("invite"),
    "em_accept_embargo_activity": _answers("proposal"),
    "em_reject_embargo_activity": _answers("proposal"),
    "rm_read_report_activity": _answers("offer"),
    "rm_validate_report_activity": _answers("offer"),
    "rm_invalidate_report_activity": _answers("offer"),
    "rm_close_report_activity": _answers("offer"),
    # The entry it refuses is one the CASE_MANAGER holds.
    "reject_log_entry_activity": _held("entry"),
    "refusal_notice_activity": _answers("refused"),
    "update_case_activity": _held("case"),
    "update_participant_activity": _held("participant"),
    "update_embargo_consent_activity": _held("row"),
    "rm_engage_case_activity": _held("case"),
    "rm_defer_case_activity": _held("case"),
    "rm_close_case_activity": _held("case"),
    "offer_case_ownership_transfer_activity": _held("case"),
    # The inner Offer it nests names the held case (ADR-0148).
    "propose_case_ownership_transfer_activity": _held("case"),
    "remove_participant_from_case_activity": _held("participant"),
    "remove_embargo_from_case_activity": _held("embargo"),
    "withdraw_from_embargo_activity": _held("embargo"),
    "activate_embargo_activity": _held("embargo"),
    "reject_embargo_proposal_activity": _held("embargo"),
    "announce_embargo_activity": _held("embargo"),
    "recommend_actor_activity": _ACTOR_REF,
    # The invitee already holds the case from the Announce (AKM-02-003).
    "rm_invite_to_full_case_activity": _ACTOR_REF,
    "bootstrap_replay_question_activity": NoIntroduction(
        "a Question, which carries no object"
    ),
}


def _factory_modules() -> list[types.ModuleType]:
    """Every public module of the factories package, found, not listed."""
    return [
        importlib.import_module(f"{factories_package.__name__}.{info.name}")
        for info in pkgutil.iter_modules(factories_package.__path__)
        if not info.name.startswith("_") and info.name != "errors"
    ]


def _factory_names() -> set[str]:
    """Every public ``*_activity`` function the factory modules define."""
    names: set[str] = set()
    for module in _factory_modules():
        for name, value in inspect.getmembers(module, inspect.isfunction):
            if (
                value.__module__ == module.__name__
                and not name.startswith("_")
                and name.endswith("_activity")
            ):
                names.add(name)
    return names


def test_every_factory_is_classified():
    """Ratchet: a new factory must say whether it introduces an object."""
    tables = (INTRODUCES, BUILDS_WHAT_IT_INTRODUCES, INTRODUCES_NOTHING)
    classified = [name for table in tables for name in table]
    assert len(classified) == len(set(classified)), (
        "a factory is classified twice"
    )
    assert set(classified) == _factory_names()


@pytest.mark.spec("AKM-02-004", "AKM-03-003")
@pytest.mark.parametrize("factory", sorted(INTRODUCES))
def test_an_introducing_factory_refuses_a_bare_id(factory):
    build, _ = INTRODUCES[factory]
    with pytest.raises(VultronActivityConstructionError):
        build(_BARE)


def _is_inline(value: object) -> bool:
    """An inline object names its ``type`` and its ``id``; a bare id does not."""
    return (
        isinstance(value, dict)
        and bool(value.get("type"))
        and bool(value.get("id"))
    )


def _carried_inline(
    body: dict[str, Any], slot: str = "object"
) -> dict[str, Any]:
    value = body.get(slot)
    assert _is_inline(value), (
        f"{body.get('type')} carries {value!r} in {slot}, not an inline object"
    )
    return cast(dict[str, Any], value)


@pytest.mark.spec("AKM-02-004", "AKM-03-003")
@pytest.mark.parametrize("factory", sorted(INTRODUCES))
def test_an_introducing_factory_carries_the_object_inline(factory):
    build, inline = INTRODUCES[factory]
    introduced = inline()
    obj = _carried_inline(wire_body(build(introduced)))
    assert obj["id"] == introduced.id_


@pytest.mark.spec("AKM-02-004", "AKM-03-003")
@pytest.mark.parametrize("factory", sorted(BUILDS_WHAT_IT_INTRODUCES))
def test_a_factory_that_builds_its_object_carries_it_inline(factory):
    build, slot = BUILDS_WHAT_IT_INTRODUCES[factory]
    _carried_inline(wire_body(build()), slot)


def _admits_a_bare_string(annotation: object) -> bool:
    """Whether a parameter annotated *annotation* would take a bare ``str`` id.

    Sees through the forms that hide a ``str``: ``type`` aliases, ``NewType``,
    ``str`` subclasses, ``Literal`` strings, type variables, and the abstract
    collections a ``str`` satisfies (``Sequence``, ``Hashable``, ...).
    ``typing.get_type_hints`` has already stripped ``Annotated``.
    """
    if isinstance(annotation, typing.TypeAliasType):
        return _admits_a_bare_string(annotation.__value__)
    supertype = getattr(annotation, "__supertype__", None)
    if supertype is not None:
        return _admits_a_bare_string(supertype)
    if isinstance(annotation, typing.TypeVar):
        if annotation.__constraints__:
            return any(
                _admits_a_bare_string(c) for c in annotation.__constraints__
            )
        bound = annotation.__bound__
        return bound is None or _admits_a_bare_string(bound)
    if annotation in (Any, object, typing.LiteralString):
        return True
    origin = typing.get_origin(annotation)
    if origin in (typing.Union, types.UnionType):
        return any(
            _admits_a_bare_string(a) for a in typing.get_args(annotation)
        )
    if origin is typing.Literal:
        return any(isinstance(a, str) for a in typing.get_args(annotation))
    cls = origin if origin is not None else annotation
    return isinstance(cls, type) and (
        issubclass(cls, str) or isinstance("bare-id", cls)
    )


_StrAlias = typing.NewType("_StrAlias", str)
_Free = typing.TypeVar("_Free")
_BoundToActor = typing.TypeVar("_BoundToActor", bound=as_Actor)
type _AliasOfStr = str | as_Actor
type _AliasOfActor = as_Actor | None


class _StrSubclass(str):
    pass


@pytest.mark.parametrize(
    ("annotation", "admits"),
    [
        (str, True),
        (str | None, True),
        (Any, True),
        (object, True),
        (_AliasOfStr, True),
        (_StrAlias, True),
        (_StrSubclass, True),
        (typing.Literal["urn:x"], True),
        (typing.LiteralString, True),
        (_Free, True),
        (Sequence[Any], True),
        (Hashable, True),
        (as_Actor, False),
        (as_Actor | None, False),
        (_AliasOfActor, False),
        (_BoundToActor, False),
        (list[str], False),
        (typing.Literal[1], False),
    ],
)
def test_the_bare_string_check_sees_through_a_hidden_str(annotation, admits):
    """The typed-object check below is only as good as this predicate."""
    assert _admits_a_bare_string(annotation) is admits


def _factory(name: str) -> Callable[..., Any]:
    for module in _factory_modules():
        if hasattr(module, name):
            return cast(Callable[..., Any], getattr(module, name))
    raise LookupError(name)


@pytest.mark.spec("AKM-02-004", "AKM-03-003")
@pytest.mark.parametrize(
    "factory",
    sorted(
        name
        for name, why in INTRODUCES_NOTHING.items()
        if why.reason in (_ANSWERS, _HELD)
    ),
)
def test_an_answering_or_acting_factory_takes_its_object_typed(factory):
    """What such a factory carries is typed, so it cannot start taking an id.

    The classification says why it introduces nothing; this keeps the reason
    true, since the parameter that becomes ``object``, annotated to admit a
    ``str``, would let a bare id through unexamined.
    """
    parameter = INTRODUCES_NOTHING[factory].object_parameter
    assert parameter is not None, f"{factory} names no object parameter"
    function = _factory(factory)
    assert parameter in inspect.signature(function).parameters, (
        f"{factory} has no parameter {parameter!r}"
    )
    annotation = typing.get_type_hints(function).get(parameter, Any)
    assert not _admits_a_bare_string(annotation), (
        f"{factory} takes {parameter!r} as {annotation!r}, which admits a"
        " bare string id"
    )


#: Activity types whose example introduces its ``object``.
_INTRODUCING_TYPES = frozenset(
    {"Create", "Add", "Offer", "Invite", "Announce"}
)

#: Case fields a case put on the wire as the introduced object carries inline:
#: the receiver seeds its replica from them (CBT-01-012).
_CASE_CARRIED_FIELDS = ("caseParticipants", "vulnerabilityReports")


def _bare_ids_in_introduced_case(obj: dict[str, Any]) -> dict[str, list[str]]:
    if obj.get("type") != "VulnerabilityCase":
        return {}
    found = {
        field: [item for item in obj.get(field, []) if isinstance(item, str)]
        for field in _CASE_CARRIED_FIELDS
    }
    return {field: ids for field, ids in found.items() if ids}


#: The example activities of an introducing type, built once at collection.
_INTRODUCING_EXAMPLES: dict[str, dict[str, Any]] = {
    name: body
    for name, body in (
        (name, wire_body(activity))
        for name, activity in activity_examples().items()
    )
    if body.get("type") in _INTRODUCING_TYPES
}


def test_the_example_corpus_has_introducing_activities():
    """Guard against a vacuous pass: a zero-item parametrization runs nothing."""
    assert _INTRODUCING_EXAMPLES


@pytest.mark.spec("CBT-01-012")
@pytest.mark.parametrize("example", sorted(_INTRODUCING_EXAMPLES))
def test_an_example_carries_what_it_introduces_inline(example):
    body = _INTRODUCING_EXAMPLES[example]
    obj = _carried_inline(body)
    bare = _bare_ids_in_introduced_case(obj)
    assert not bare, (
        f"{example} introduces a case whose nested objects are bare ids: {bare}"
    )
