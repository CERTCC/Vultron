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

"""The JSON-LD ``@context`` Vultron emits, and the Vultron-property field marker.

These live in core rather than in the wire layer because under ADR-0099 the
core classes *are* the objects that carry them, and core MUST NOT import wire
(ARCH-01-001 — the one boundary rule ADR-0099 leaves fully in force).  Wire
imports them from here, which ARCH-25-006 permits.
"""

from collections.abc import Callable
from contextvars import ContextVar
from typing import Annotated, Any

from pydantic import Field, SerializationInfo
from pydantic.config import JsonDict

from vultron.primitives import NonEmptyString

#: The ActivityStreams 2.0 namespace.  AS2 Core §2.1 asks every producer to cite
#: it in ``@context``, and an AS2 receiver that does not process JSON-LD looks
#: for this exact string (VM-10-001).
ACTIVITY_STREAMS_NS = "https://www.w3.org/ns/activitystreams"

#: The Vultron JSON-LD context document, which declares the Vultron terms AS2
#: does not define (``VulnerabilityCase``, ``EmbargoEvent``, …).
VULTRON_CONTEXT_URI = "https://certcc.github.io/Vultron/ns/context.jsonld"

#: The ``@context`` every outbound top-level document carries: AS2 first, then
#: the Vultron context (VM-10-001).  Citing the Vultron URI alone is not
#: enough, because a receiver need not dereference it (VM-10-003) and so cannot
#: learn that it imports AS2.  A tuple, so no caller can mutate the default;
#: :func:`default_jsonld_context` gives the list form a document carries.
DEFAULT_JSONLD_CONTEXT: tuple[str, ...] = (
    ACTIVITY_STREAMS_NS,
    VULTRON_CONTEXT_URI,
)

#: The type of an object's JSON-LD ``@context``: one context IRI, or a
#: non-empty list of them in order.  A signed body's context is a list: the
#: signing module appends the data-integrity context to the activity's own
#: (FEP-8b32, ``vultron.wire.as2.signing``), so a single context becomes
#: two.  Each entry, and the list itself, is "if present, then non-empty"
#: (CS-08-002).  An inline context object (a JSON-LD term map) is not
#: accepted: nothing Vultron sends or reads defines terms inline.
JsonLdContext = (
    NonEmptyString | Annotated[list[NonEmptyString], Field(min_length=1)]
)


def default_jsonld_context() -> list[str]:
    """A fresh list holding :data:`DEFAULT_JSONLD_CONTEXT`."""
    return list(DEFAULT_JSONLD_CONTEXT)


def is_default_jsonld_context(value: object) -> bool:
    """Whether *value* is the default ``@context`` (the list, in its order)."""
    return isinstance(value, list) and tuple(value) == DEFAULT_JSONLD_CONTEXT


#: ``True`` while an AS2 (``by_alias``) dump is serializing an enclosing
#: document, so an object serialized inside it knows it is nested.
_INSIDE_AS2_DOCUMENT: ContextVar[bool] = ContextVar(
    "_inside_as2_document", default=False
)


def serialize_with_top_level_context(
    serialize: Callable[[], Any],
    info: SerializationInfo,
    explicit_context: JsonLdContext | None,
) -> Any:
    """Run *serialize* and place ``@context`` on the top-level document only.

    The top-level document of an AS2 dump carries *explicit_context*, or the
    default list when it is ``None`` (VM-10-001).  An object nested inside it
    does not restate the default: the enclosing context already applies to
    it, as JSON-LD scopes a context to the whole tree below it (VM-10-001).  A
    nested object that holds a non-default *explicit_context*, such as one
    received from a peer with its own, keeps it, because dropping it could
    change how that object's terms expand.

    ``@context`` is written first, where a reader looks for it.  The
    persistence dump (``by_alias`` false) is passed through untouched.
    """
    if not info.by_alias:
        return serialize()
    nested = _INSIDE_AS2_DOCUMENT.get()
    token = _INSIDE_AS2_DOCUMENT.set(True)
    try:
        data = serialize()
    finally:
        _INSIDE_AS2_DOCUMENT.reset(token)
    if not isinstance(data, dict):
        return data
    rest = {key: value for key, value in data.items() if key != "@context"}
    if explicit_context is not None:
        return {"@context": explicit_context, **rest}
    if nested:
        return rest
    return {"@context": default_jsonld_context(), **rest}


#: Key of the ``json_schema_extra`` marker that declares a wire field a
#: Vultron-namespace property, such as a termination ``Remove``'s
#: ``terminationCause`` (EMB-13-005) or a case's ``ledgerPosition``
#: (SYNC-16-005).  The context generator maps each marked field's wire name to
#: ``vultron:<name>``, so a receiver can resolve it.  In core for the reason
#: :data:`VULTRON_CONTEXT_URI` is: core classes carry it (ADR-0099).
VULTRON_PROPERTY_KEY = "vultron_property"

#: The marker itself: pass it as a field's ``json_schema_extra``.
VULTRON_PROPERTY_EXTRA: JsonDict = {VULTRON_PROPERTY_KEY: True}
