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
"""Architecture boundary test: wire-branch field annotations must not name CoreObject subclasses.

Spec: ARCH-23-006

``as_ObjectRef`` carried ``| CoreObject``, added in PR #730 as a migration
convenience.  It made a core-side validation guard unsafe to enforce loudly:
``VultronValidationError`` was not a ``ValueError`` subclass, so a guard firing
while Pydantic resolved that union escaped the whole operation rather than being
absorbed as a failed union branch.

That union-escape defect is the whole of the remaining justification. This test
also cited ARCH-22-001 ("wire MUST NOT import core"), which ADR-0099 repealed —
and ADR-0099 goes further and *inverts* this rule, since under one object model a
wire field annotation is supposed to name the core class. Fixing the union-escape
defect is therefore the prerequisite for inverting this test, tracked as AC-2 of
#3491. Do not invert it first.

**The prerequisite is now met**: ``VultronValidationError`` inherits
``ValueError``, so Pydantic absorbs it as a failed branch.  That was blocked
until the duplicate-row signal got its own type
(``VultronAlreadyExistsError``), because ``crud.create`` used a bare
``ValueError`` for "already stored" and callers swallow it — sharing the base
made a projection failure indistinguishable from a duplicate.
``test_core_guard_inside_wire_union_fails_the_branch`` below holds the absorption
property, and ``test_db_record`` holds the separability property.  Inverting this
rule is now unblocked; do not invert it without keeping both of those green.

This test asserts that no wire-branch class (``as_Base`` subclass registered in
``VOCABULARY``) has a field annotation that names a ``CoreObject`` subclass.
The AS2-faithful reference union (``as_Object | as_Link | str``) is permitted.
"""

import re
import typing

import pytest

import vultron.wire.as2.vocab.activities  # noqa: F401 — trigger dynamic discovery
import vultron.wire.as2.vocab.objects  # noqa: F401

from vultron.core.models.base import CoreObject
from vultron.errors import VultronValidationError
from vultron.core.models.registry import CORE_VOCABULARY


def _hint_contains_core_object(hint: typing.Any) -> bool:
    """Return True if *hint* is or transitively contains a CoreObject subclass."""
    if isinstance(hint, type) and issubclass(hint, CoreObject):
        return True
    args = getattr(hint, "__args__", None)
    if args:
        return any(_hint_contains_core_object(a) for a in args)
    return False


@pytest.mark.spec("ARCH-23-006")
def test_promoted_core_classes_are_exactly_as2_representable() -> None:
    """Every promoted class emits AS2 property names and nothing else.

    **This replaces the rule it used to enforce**, rather than relaxing it.
    ARCH-23-006 forbade a core type appearing in a wire field annotation. Under
    ADR-0099 that is the intended shape: detail 3 says the message-shape slots
    name the core class, so the old assertion now fails on every activity by
    design. Keeping it alive behind a growing allowlist — which is what the
    as-delivered change did, at 59 entries — records violations without checking
    anything.

    Detail 3 states the invariant that takes its place, and it is a real
    constraint rather than a weaker one: a core class that can appear in a
    message slot "MUST be exactly AS2-representable. Every field it carries must
    have a valid AS2 property spelling, and it MUST NOT carry a field that cannot
    go on the wire."

    So this asserts the delivery payload of every promoted class is spelled in
    AS2: camelCase or a reserved AS2 name, never a Python field name. That is the
    check that would have caught `attributedTo` silently becoming
    `attributed_to` on four promoted types — something the old rule, and a
    filename-level examples check, both passed straight through.

    A field that genuinely cannot go on the wire is declared in
    ``local_only_fields`` and dropped from the payload; anything else leaking a
    snake_case key is a field nobody gave an AS2 spelling.
    """
    offenders: list[str] = []
    snake = re.compile(r"[a-z0-9]_[a-z0-9]")
    generator = CoreObject.model_config.get("alias_generator")
    assert callable(generator), (
        "CoreObject no longer derives AS2 spellings, so this test would pass"
        " vacuously — see test_hierarchy_invariants"
    )

    # CORE_VOCABULARY, not the wire VOCABULARY: a promoted class registers in
    # CORE_VOCABULARY and WIRE_TYPE_MAP, never in VOCABULARY (which holds
    # as_Base subclasses). Iterating VOCABULARY here examined nothing at all.
    #
    # Read the declared aliases rather than dumping an instance. Seven of these
    # classes have required fields and cannot be constructed bare, so an
    # instance-based check silently skipped exactly the ones that matter —
    # CaseStatus, ParticipantStatus and EmbargoEvent among them.
    examined = 0
    for _type_name, cls in sorted(
        CORE_VOCABULARY.items(), key=lambda kv: kv[0]
    ):
        if not (isinstance(cls, type) and issubclass(cls, CoreObject)):
            continue
        examined += 1
        local = cls.local_only_fields
        for name, field in cls.model_fields.items():
            if name in local or field.exclude:
                continue  # never reaches the wire
            alias = field.serialization_alias or generator(name)
            if snake.search(alias):
                offenders.append(f"{cls.__name__}.{name} -> {alias}")

    assert examined, "no promoted classes were examined — the test is vacuous"
    assert not offenders, (
        "these promoted classes put Python field names on the wire instead of "
        "AS2 property names (ADR-0099 detail 3):\n"
        + "\n".join(f"  {o}" for o in sorted(offenders))
        + "\n\nGive the field an AS2 spelling, or declare it in "
        "local_only_fields if it cannot go on the wire at all."
    )


def test_core_guard_inside_wire_union_fails_the_branch() -> None:
    """A core guard firing inside a union must fail that branch, not the call.

    This is ARCH-23-006's named prerequisite, and the reason the rule could not
    simply be inverted.  A core-branch validator raising
    ``VultronValidationError`` while Pydantic resolves a union must be reported
    as a failed branch inside a ``ValidationError``.  Before
    ``VultronValidationError`` inherited ``ValueError`` it escaped
    ``model_validate()`` entirely, taking the whole operation with it — so a
    single unprojectable nested object aborted an otherwise valid activity
    instead of being rejected as one bad alternative.

    Under ADR-0099 core classes sit *inside* wire unions by design, which is what
    turns this from a latent wart into a live requirement.
    """
    from typing import Any

    from pydantic import BaseModel, ValidationError, field_validator

    class _Guarded(BaseModel):
        """Stands in for a core class whose validator refuses bad input."""

        value: str

        @field_validator("value")
        @classmethod
        def _refuse(cls, v: str) -> str:
            if v == "bad":
                raise VultronValidationError("core guard refused 'bad'")
            return v

    class _Holder(BaseModel):
        """Stands in for a wire slot admitting a core class or a raw payload."""

        slot: _Guarded | dict[str, Any]

    # The discriminating case: the payload is a *mapping*, so Pydantic actually
    # attempts the guarded branch and the validator fires.  Absorbed, that branch
    # fails and the remaining alternative wins.  Unabsorbed, this call raises
    # VultronValidationError and the whole activity is lost — which is the defect
    # ARCH-23-006 names.  (A plain string payload would prove nothing: the smart
    # union matches `str` without ever entering the guarded branch.)
    resolved = _Holder.model_validate({"slot": {"value": "bad"}})
    assert resolved.slot == {
        "value": "bad"
    }, "guarded branch did not fail over — the core guard escaped the union"

    # With no surviving alternative the failure is still reported as a validation
    # error rather than raised out of model_validate().
    class _StrictHolder(BaseModel):
        slot: _Guarded

    with pytest.raises(ValidationError) as exc_info:
        _StrictHolder.model_validate({"slot": {"value": "bad"}})

    assert "core guard refused" in str(exc_info.value)
