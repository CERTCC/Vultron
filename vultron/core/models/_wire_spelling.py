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
#  (“Third Party Software”). See LICENSE.md for more details.
#  Carnegie Mellon®, CERT® and CERT Coordination Center® are registered in the
#  U.S. Patent and Trademark Office by Carnegie Mellon University

# Copyright

"""Detection of wire-spelled (camelCase) keys in core-type input.

A core type validated against a wire-shaped payload drops every key whose only
spelling is snake_case, because Pydantic v2 ignores unknown keys.  That is how a
whole RM ladder disappeared without a trace in issue #2232.  This module
computes, per model class, the set of camelCase spellings that would be dropped,
so a ``model_validator(mode="before")`` can reject them loudly instead
(ARCH-15-001, ARCH-15-002).

Kept out of ``vultron/core/models/_helpers.py`` deliberately: that module cannot
import from ``vultron.core.states`` (circular import through
``states/__init__.py``), and while this module happens not to need those imports
today, colocating shape guards with the helpers that do need them would
re-create the cycle the first time one of them grew a state reference.
"""

from typing import Any

from pydantic import BaseModel
from pydantic.alias_generators import to_camel

from vultron.errors import VultronValidationError

#: Per-class cache for :func:`wire_spelled_keys`.  Keyed by the exact class, so
#: a subclass that adds a field gets its own mapping rather than inheriting a
#: map computed from its base — the silent-drop hole that a single shared
#: module-level map would leave open.
_CACHE: dict[type[BaseModel], dict[str, str]] = {}


def wire_spelled_keys(model: type[BaseModel]) -> dict[str, str]:
    """Map each field's forbidden camelCase spelling to its canonical name.

    A field's camelCase form is *sanctioned* — and therefore excluded — when the
    field declares it as an explicit ``validation_alias`` (``in_reply_to`` →
    ``inReplyTo``).  Names ending in ``_`` (``id_``, ``type_``, ``context_``)
    are skipped: they carry their own aliases and have no camelCase form.
    Fields whose camelCase form equals their snake_case form (``name``,
    ``context``) cannot collide and are skipped too.

    Results are cached per exact class; call :func:`clear_cache` if a test
    defines model classes dynamically and needs the cache reset.
    """
    cached = _CACHE.get(model)
    if cached is not None:
        return cached
    mapping: dict[str, str] = {}
    for name, field in model.model_fields.items():
        if name.endswith("_"):
            continue
        camel = to_camel(name)
        if camel == name:
            continue
        if isinstance(field.validation_alias, str) and (
            field.validation_alias == camel
        ):
            continue
        mapping[camel] = name
    _CACHE[model] = mapping
    return mapping


def clear_cache() -> None:
    """Drop the per-class cache.  Intended for tests only."""
    _CACHE.clear()


def reject_wire_spelled_keys(
    model: type[BaseModel], data: Any, boundary_hint: str
) -> Any:
    """Return *data* unchanged, or raise if it carries wire-spelled keys.

    Args:
        model: The class being validated.  Its own ``model_fields`` decide
            which spellings are forbidden, so a subclass that adds a field is
            covered without any registration step.
        data: The raw ``model_validator(mode="before")`` input.  Non-dict
            input is passed through untouched.
        boundary_hint: The wire→core projection the caller should have used
            instead, quoted back in the error message
            (e.g. ``"as_CaseParticipant.to_core()"``).

    Raises:
        VultronValidationError: when at least one forbidden spelling is present.
    """
    if not isinstance(data, dict):
        return data
    forbidden = wire_spelled_keys(model)
    offenders = sorted(key for key in forbidden if key in data)
    if not offenders:
        return data
    canonical = ", ".join(f"{key} -> {forbidden[key]}" for key in offenders)
    raise VultronValidationError(
        f"{model.__name__} received wire-spelled (camelCase) key(s)"
        f" {offenders}, which this core type does not accept and Pydantic would"
        f" silently discard: {canonical}. Convert at the wire→core boundary"
        f" ({boundary_hint}) instead of validating a wire-shaped payload"
        " against a core type. See issue #2232."
    )
