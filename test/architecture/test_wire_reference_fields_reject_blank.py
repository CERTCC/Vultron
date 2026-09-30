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
"""Ratchet: every wire reference field refuses a blank IRI (CS-08-001).

Spec: CS-08-001, CS-08-002, ARCH-23-004

A reference field is one whose declared type admits ``as_Link`` — the AS2
"object or IRI" shape — or admits both a model and a string, which is the
same shape spelled by hand.  The set is *derived* from the vocabulary classes'
annotations (ARCH-23-004), never listed, so a new field or a new class is
covered the moment it is declared.

For each such field the check is behavioural, not textual: the field's declared
type is handed to a ``TypeAdapter`` and asked to validate ``""`` and ``"   "``
in every shape the field can carry a string (bare, ``[blank]`` for lists).  It
must refuse both.  That is what closes the gap #3855 found — inbound, a blank
reference validated; outbound, VM-07-001 dropped it silently — and it holds
regardless of whether the field spells its IRI branch through the shared alias
or by hand.
"""

import pytest
from pydantic import BaseModel

import vultron.wire.as2.vocab.activities  # noqa: F401 — trigger dynamic discovery
import vultron.wire.as2.vocab.objects  # noqa: F401
from test.support.blank_strings import (
    declared_type,
    leaf_types,
    rejects_blank,
)
from vultron.core.models._helpers import strip_annotated
from vultron.wire.as2.vocab.base.base import as_Base
from vultron.wire.as2.vocab.base.links import as_Link
from vultron.wire.as2.vocab.base.objects.base import as_Object


def wire_classes() -> dict[str, type[as_Base]]:
    """Every ``as_Base`` subclass the wire package defines, by qualified name.

    Walks the class tree rather than ``VOCABULARY``: the case-scoped activity
    classes in ``vocab/activities/case.py`` are private (``_RmInviteToCase…``)
    and never register, yet they are exactly where the hand-spelled unions
    #3876 AC-2 names live.  Iterating the registry examined none of them.
    """
    found: dict[str, type[as_Base]] = {}

    def descend(cls: type[as_Base]) -> None:
        for sub in cls.__subclasses__():
            if sub.__module__.startswith("vultron.wire"):
                found[sub.__qualname__] = sub
            descend(sub)

    descend(as_Base)
    return dict(sorted(found.items()))


def is_reference_field(annotation: object) -> bool:
    """True when *annotation* is an AS2 "object or IRI" slot.

    Either it admits ``as_Link`` (every ``ActivityStreamRef[T]`` does), or it
    admits both a model and a string — the hand-spelled form
    ``as_VulnerabilityCase | NonEmptyString`` on ``case.py`` activities.
    """
    leaves = list(leaf_types(annotation))
    if as_Link in leaves:
        return True
    admits_model = any(
        isinstance(leaf, type) and issubclass(leaf, BaseModel)
        for leaf in leaves
    )
    admits_string = any(strip_annotated(leaf) is str for leaf in leaves)
    return admits_model and admits_string


def blank_admitting_reference_fields(cls: type[BaseModel]) -> list[str]:
    """Names of *cls*'s reference fields that accept a blank IRI."""
    return [
        name
        for name, field in cls.model_fields.items()
        if is_reference_field(declared_type(field))
        and not rejects_blank(declared_type(field))
    ]


def _reference_fields_examined() -> dict[str, list[str]]:
    """``{class name: [reference field names]}`` over every wire class."""
    return {
        name: [
            field_name
            for field_name, field in cls.model_fields.items()
            if is_reference_field(declared_type(field))
        ]
        for name, cls in wire_classes().items()
    }


@pytest.mark.spec("CS-08-001")
@pytest.mark.spec("CS-08-002")
@pytest.mark.spec("ARCH-23-004")
def test_every_wire_reference_field_rejects_a_blank_iri() -> None:
    """No wire vocabulary field carries ``""`` or ``"   "`` as a reference."""
    offenders: list[str] = []
    examined = 0
    for name, cls in wire_classes().items():
        for field_name, field in cls.model_fields.items():
            annotation = declared_type(field)
            if not is_reference_field(annotation):
                continue
            examined += 1
            if not rejects_blank(annotation):
                offenders.append(f"{name}.{field_name}: {annotation}")

    assert examined, "no reference fields were examined — the test is vacuous"
    assert not offenders, (
        "these wire reference fields accept a blank IRI (CS-08-001). Route the "
        "string branch through ActivityStreamRef / ActivityStreamRequiredRef, "
        "or spell it NonEmptyString:\n"
        + "\n".join(f"  {o}" for o in offenders)
    )


def test_the_derived_reference_set_covers_the_activity_slots() -> None:
    """The derivation sees the fields #3876 named, so the ratchet is not vacuous.

    ``as_Activity``'s five slots, the collection ``items``, ``as_Question.closed``
    and the hand-spelled unions on the private ``case.py`` activities are the
    shapes the issue enumerated; a derivation that missed any of them would pass
    the ratchet by examining less.
    """
    examined = _reference_fields_examined()
    assert {
        "actor",
        "object_",
        "target",
        "origin",
        "instrument",
        "result",
    } <= set(examined["as_Offer"])
    assert "items" in examined["as_OrderedCollection"]
    assert "closed" in examined["as_Question"]
    # The hand-spelled ``as_VulnerabilityCase | NonEmptyString`` and
    # ``as_VulnerabilityCaseStub | NonEmptyString | None`` unions.
    assert "context" in examined["_OfferCaseParticipantRoleActivity"]
    assert "target" in examined["_RmInviteToCaseActivity"]


def test_ratchet_flags_a_bare_str_reference_branch() -> None:
    """A deliberately bad field proves the check can fail.

    The class is a plain ``BaseModel`` rather than an ``as_Base`` subclass so
    it is never walked by :func:`wire_classes` and cannot leak into other tests.
    """

    class _Bad(BaseModel):
        good: as_Object | as_Link | None = None
        slot: as_Object | as_Link | str | None = None
        many: list[as_Object | as_Link | str] | None = None

    assert blank_admitting_reference_fields(_Bad) == ["slot", "many"]
