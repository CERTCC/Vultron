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

A case-scoped ``payloadSnapshot`` names the case URI in ``context``
(CLP-07-007), and the snapshot is the exact blob the factory produced
(VM-08-003): nothing writes a ``context`` in afterwards, and the commit
boundary refuses one naming another case.  So the factory, not the emitting
node, is where ``context`` has to be complete.  Every factory whose activity is
*about* a case calls :func:`with_case_context` so that a caller who named the
case but not the context gets the case URI filled in, while an explicit
``context`` is left alone.
"""

from typing import Any, TypeVar

# Defined beside the parse-edge check that reads it too (HP-08-015), which
# the parser imports and so cannot import this package.
from vultron.core.models.preview_object import PreviewObject
from vultron.wire.as2.context_agreement import case_uri_of

_Target = TypeVar("_Target")


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
    """Reduce a full case in a ``target`` slot to its URI (MV-10-009, AKM-02-002).

    A recipient addressed about a case already holds it, so the case travels as
    its URI; any other object (no case at all) is kept as it is.  Nothing downstream
    collapses a reference any more —
    the sealed body is delivered as built (VM-08-003) — so the factory is the
    one place a full case can be stopped from going on the wire whole.
    """
    if target is None or isinstance(target, str):
        return target
    if isinstance(target, PreviewObject) or not hasattr(
        target, "case_participants"
    ):
        # Not a case at all: a case's preview carries the case's field names
        # (ADR-0217) but is not the case.
        return target
    case_uri = case_uri_of(target)
    return case_uri if case_uri is not None else target
