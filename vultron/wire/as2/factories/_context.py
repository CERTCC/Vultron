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

"""Case ``context`` defaulting shared by the case-scoped factories.

A canonical ledger entry requires ``payloadSnapshot.context`` to be the case
URI (CLP-07-007), and the snapshot is the exact blob the factory produced
(VM-08-003) — so the factory, not the emitting node, is where ``context`` has
to be complete.  Every factory whose activity is *about* a case calls
:func:`with_case_context` so that a caller who named the case but not the
context gets the case URI filled in, while an explicit ``context`` is left
alone.
"""

from typing import Any, TypeVar

_Target = TypeVar("_Target")


def case_uri_of(case_ref: object) -> str | None:
    """Return the URI a case reference names: the string itself, or its id."""
    if isinstance(case_ref, str):
        return case_ref or None
    case_id = getattr(case_ref, "id_", None)
    return case_id if isinstance(case_id, str) and case_id else None


def with_case_context(
    kwargs: dict[str, Any], case_ref: object
) -> dict[str, Any]:
    """Default ``kwargs["context"]`` to the URI *case_ref* names.

    Leaves an explicit ``context`` untouched and adds nothing when
    *case_ref* names no case, so a factory that has no case to speak of
    emits no ``context`` at all.
    """
    if kwargs.get("context") is None:
        case_uri = case_uri_of(case_ref)
        if case_uri is not None:
            kwargs["context"] = case_uri
    return kwargs


def case_target_ref(target: _Target) -> _Target | str:
    """Reduce a full case in a ``target`` slot to its URI (MV-10-001, AKM-02-002).

    A recipient addressed about a case already holds it, so the case travels as
    its URI; only the selective-disclosure stub an ``Invite`` builds
    (``as_VulnerabilityCaseStub``, which carries no participants or reports) is
    kept as an object.  Nothing downstream collapses a reference any more —
    the sealed body is delivered as built (VM-08-003) — so the factory is the
    one place a full case can be stopped from going on the wire whole.
    """
    if target is None or isinstance(target, str):
        return target
    if not hasattr(target, "case_participants"):
        return target  # a stub, or not a case at all
    case_uri = case_uri_of(target)
    return case_uri if case_uri is not None else target
