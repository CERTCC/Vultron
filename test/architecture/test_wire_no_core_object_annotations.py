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
``VultronValidationError`` is not a ``ValueError`` subclass, so a guard firing
while Pydantic resolves that union escapes the whole operation rather than being
absorbed as a failed union branch.

That union-escape defect is the whole of the remaining justification. This test
also cited ARCH-22-001 ("wire MUST NOT import core"), which ADR-0099 repealed —
and ADR-0099 goes further and *inverts* this rule, since under one object model a
wire field annotation is supposed to name the core class. Fixing the union-escape
defect is therefore the prerequisite for inverting this test, tracked as AC-2 of
#3491. Do not invert it first.

This test asserts that no wire-branch class (``as_Base`` subclass registered in
``VOCABULARY``) has a field annotation that names a ``CoreObject`` subclass.
The AS2-faithful reference union (``as_Object | as_Link | str``) is permitted.
"""

import typing

import pytest

import vultron.wire.as2.vocab.activities  # noqa: F401 — trigger dynamic discovery
import vultron.wire.as2.vocab.objects  # noqa: F401

from vultron.core.models.base import CoreObject
from vultron.wire.as2.vocab.base.base import as_Base
from vultron.wire.as2.vocab.base.registry import VOCABULARY

# ---------------------------------------------------------------------------
# ADR-0099 transitional violations: wire fields that name core classes because
# the paired wire class was deleted (issue #3487, detail 3).  These are
# intentional under ADR-0099 and will be resolved when #3491 fixes the
# union-escape defect and this test is inverted.
# This set must not grow — new violations outside ADR-0099 are bugs.
# ---------------------------------------------------------------------------
_ADR0099_KNOWN_VIOLATIONS: frozenset[str] = frozenset(
    {
        # as_ObjectRequiredRef intentionally includes CoreObject so activities
        # can hold promoted core classes (VulnerabilityCase, EmbargoEvent, etc.)
        # after paired wire class deletion (issue #3487).
        "as_Accept.object_",
        "as_Add.object_",
        "as_Announce.object_",
        "as_Block.object_",
        "as_Create.object_",
        "as_Delete.object_",
        "as_Dislike.object_",
        "as_Flag.object_",
        "as_Follow.object_",
        "as_Ignore.object_",
        "as_Invite.object_",
        "as_Join.object_",
        "as_Leave.object_",
        "as_Like.object_",
        "as_Listen.object_",
        "as_Move.object_",
        "as_Offer.object_",
        "as_Profile.describes",
        "as_Read.object_",
        "as_Reject.object_",
        "as_Relationship.object",
        "as_Relationship.subject",
        "as_Remove.object_",
        "as_TentativeAccept.object_",
        "as_TentativeReject.object_",
        "as_Undo.object_",
        "as_Update.object_",
        "as_View.object_",
        # Specific fields typed with promoted core classes (issue #3487):
        "as_CaseProposal.object_",
        "as_VulnerabilityCaseStub.active_embargo",
        # actor: as_ActorRef | CoreActor so activities accept promoted core actors
        # (VultronPerson, VultronOrganization, etc.) after wire class deletion (#3487).
        "as_Accept.actor",
        "as_Activity.actor",
        "as_Add.actor",
        "as_Announce.actor",
        "as_Arrive.actor",
        "as_Block.actor",
        "as_Create.actor",
        "as_Delete.actor",
        "as_Dislike.actor",
        "as_Flag.actor",
        "as_Follow.actor",
        "as_Ignore.actor",
        "as_Invite.actor",
        "as_Join.actor",
        "as_Leave.actor",
        "as_Like.actor",
        "as_Listen.actor",
        "as_Move.actor",
        "as_Offer.actor",
        "as_Question.actor",
        "as_Read.actor",
        "as_Reject.actor",
        "as_Remove.actor",
        "as_TentativeAccept.actor",
        "as_TentativeReject.actor",
        "as_Travel.actor",
        "as_Undo.actor",
        "as_Update.actor",
        "as_View.actor",
    }
)


def _hint_contains_core_object(hint: typing.Any) -> bool:
    """Return True if *hint* is or transitively contains a CoreObject subclass."""
    if isinstance(hint, type) and issubclass(hint, CoreObject):
        return True
    args = getattr(hint, "__args__", None)
    if args:
        return any(_hint_contains_core_object(a) for a in args)
    return False


@pytest.mark.spec("ARCH-23-006")
def test_no_wire_field_annotation_names_core_object_subclass() -> None:
    """No wire-branch field annotation names a CoreObject subclass.

    Spec: ARCH-23-006

    Checks every class registered in ``VOCABULARY`` (wire-branch classes only).
    The AS2-faithful union ``as_Object | as_Link | str | None`` is permitted.
    A core type (``CoreObject`` subclass) in a wire field annotation is forbidden,
    except for the ADR-0099 transitional violations in ``_ADR0099_KNOWN_VIOLATIONS``
    (pending resolution in #3491).
    """
    violations: list[str] = []

    for _type_name, cls in VOCABULARY.items():
        if not (isinstance(cls, type) and issubclass(cls, as_Base)):
            continue
        try:
            hints = typing.get_type_hints(cls, include_extras=True)
        except Exception:
            continue
        for field_name, hint in hints.items():
            if _hint_contains_core_object(hint):
                violations.append(f"{cls.__name__}.{field_name}: {hint!r}")

    # Filter out ADR-0099 known transitional violations (pending #3491)
    new_violations = [
        v
        for v in violations
        if v.split(": ")[0] not in _ADR0099_KNOWN_VIOLATIONS
    ]

    assert not new_violations, (
        "Wire-branch field annotations name a CoreObject subclass (ARCH-23-006):\n"
        + "\n".join(f"  {v}" for v in sorted(new_violations))
        + "\n\nThe AS2-faithful reference union (as_Object | as_Link | str) is "
        "permitted. Remove CoreObject (and its subclasses) from wire field "
        "annotations — assign a wire projection instead."
    )

    # Ratchet: known violations must not silently resolve without updating this set
    found_keys = {v.split(": ")[0] for v in violations}
    resolved = _ADR0099_KNOWN_VIOLATIONS - found_keys
    assert not resolved, (
        "ADR-0099 known violations resolved — remove these from "
        f"_ADR0099_KNOWN_VIOLATIONS: {sorted(resolved)}"
    )
