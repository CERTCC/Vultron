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

"""AS2 key lookup for core code that has to key a wire-shaped mapping.

ADR-0099 detail 2: core field names follow Python convention and the AS2
spelling lives in a Pydantic alias.  **Core code MUST NOT type an AS2
spelling** — it names ``in_reply_to``, never ``inReplyTo``.

A handful of core code nevertheless has to *key* an AS2-spelled mapping.  The
ledger payload snapshot is the case that matters: CLP-07-001 requires it to be
the AS2 serialization of the inbound activity as it arrived, so its keys are
AS2-spelled by definition, and RSH-05-009 requires an adjudication patch to
leave that shape byte-for-byte identical to an unadjudicated entry's.  Such code
names the *core* field and asks here for the AS2 spelling, so the camelCase
never appears in core logic.

Two sources answer, in order:

1. the field's declared ``serialization_alias`` on the core model — the single
   source of truth wherever the model declares one (ADR-0099 detail 2);
2. :func:`pydantic.alias_generators.to_camel`, the same generator the core
   models' ``alias_generator`` config uses, for the models that carry no
   explicit alias yet (``VulnerabilityCase``, ``VultronOfferRecord``).

Source 2 is what lets core address a wire spelling that no core model declares
— the snapshot keys produced by the wire layer's ``as_*`` classes — without
hand-writing it.  It is a derivation, not a translation table: there is nothing
to keep in sync.

Spec: ARCH-20-001 (core MUST NOT produce a wire shape for a core object);
CLP-07-001; RSH-05-009; ADR-0099 details 2 and 5.
"""

from collections.abc import Iterable

from pydantic import AliasChoices, BaseModel
from pydantic.alias_generators import to_camel


def wire_key(field_name: str, model: type[BaseModel] | None = None) -> str:
    """Return the AS2 spelling of the core field *field_name*.

    Args:
        field_name: The core (snake_case) field name.
        model: The core model that declares the field.  When given and the
            field declares a string ``serialization_alias``, that alias is
            authoritative.

    Returns:
        The AS2 key, e.g. ``"caseParticipants"`` for ``"case_participants"``
        and ``"rmState"`` for ``ParticipantStatus.rm``.

    Raises:
        KeyError: If *model* is given and does not declare *field_name*.  Falling
            back to ``to_camel`` there would invent a plausible-looking key for a
            field that does not exist, which is worse than failing: the callers
            build patch-key and twin tables from string field names
            (:mod:`vultron.core.behaviors.ledger_patch`) and filter a rendered
            snapshot with ``if key in rendered``, so a wrong key silently drops
            the dimension it was supposed to carry.  A core field rename must
            break loudly here rather than quietly downstream.
    """
    if model is not None:
        field = model.model_fields.get(field_name)
        if field is None:
            raise KeyError(
                f"{model.__name__} declares no field '{field_name}', so its AS2"
                " spelling cannot be derived. Pass model=None to camel-case a"
                " bare name."
            )
        alias = field.serialization_alias
        if isinstance(alias, str) and alias:
            return alias
    return to_camel(field_name)


def wire_keys(
    field_names: Iterable[str], model: type[BaseModel] | None = None
) -> tuple[str, ...]:
    """Return :func:`wire_key` for each of *field_names*, in order."""
    return tuple(wire_key(name, model) for name in field_names)


def input_keys(model: type[BaseModel], field_name: str) -> tuple[str, ...]:
    """Return every spelling *field_name* is accepted under on input.

    The field's ``validation_alias`` comes first, in its declared order, and the
    Python field name last.  For a ``mode="before"`` validator that has to look
    at raw input keys, this is how it asks the field which keys are its own
    instead of listing them again (ADR-0099 detail 2).

    Note the ordering is significant to callers that take the *first* key
    present: the AS2 spelling wins over the Python field name.  That is
    deliberate — these keys are read off wire-shaped input, where the AS2
    spelling is the authoritative one.

    Raises:
        KeyError: If *model* does not declare *field_name*.  See :func:`wire_key`
            for why a silent fallback is the wrong behaviour here.
    """
    keys: list[str] = []
    field = model.model_fields.get(field_name)
    if field is None:
        raise KeyError(
            f"{model.__name__} declares no field '{field_name}', so its input"
            " spellings cannot be derived."
        )
    declared = field.validation_alias
    if isinstance(declared, str):
        keys.append(declared)
    elif isinstance(declared, AliasChoices):
        keys.extend(c for c in declared.choices if isinstance(c, str))
    if field_name not in keys:
        keys.append(field_name)
    return tuple(keys)
