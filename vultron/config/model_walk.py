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

"""Walking a configuration model: its sections, its leaf fields, their types.

A field whose type is itself a model is a *section*, and its fields sit under
the section's key; every other field is a *leaf*.  The secret-setting rule
(:mod:`vultron.config.secrets`) and the configuration reference page
(:mod:`vultron.metadata.docs.config_reference`) both walk ``AppConfig`` this
way, so they agree on which key paths exist.
"""

from __future__ import annotations

import types
from collections.abc import Callable, Iterator
from typing import Annotated, Any, Union, get_args, get_origin

from pydantic import BaseModel
from pydantic.fields import FieldInfo

#: Called with ``(owner model, field name, field, section model)`` for each
#: section the walk enters.
SectionHook = Callable[
    [type[BaseModel], str, FieldInfo, type[BaseModel]], None
]


def annotation_members(annotation: Any) -> tuple[Any, ...]:
    """Return the members of a union annotation, or the annotation alone.

    ``Annotated[X, ...]`` is read as ``X``.
    """
    if get_origin(annotation) is Annotated:
        annotation = get_args(annotation)[0]
    origin = get_origin(annotation)
    if origin is Union or origin is types.UnionType:
        return get_args(annotation)
    return (annotation,)


def section_model(annotation: Any) -> type[BaseModel] | None:
    """Return the model a section field holds, or ``None`` for a leaf."""
    if isinstance(annotation, type) and issubclass(annotation, BaseModel):
        return annotation
    return None


def iter_leaf_fields(
    model: type[BaseModel],
    prefix: tuple[str, ...] = (),
    on_section: SectionHook | None = None,
) -> Iterator[tuple[tuple[str, ...], type[BaseModel], str, FieldInfo]]:
    """Yield ``(path, owner model, name, field)`` for every leaf, in order.

    *on_section* is called before the walk enters each section, so a caller
    can refuse one.
    """
    for name, field in model.model_fields.items():
        path = (*prefix, name)
        section = section_model(field.annotation)
        if section is not None:
            if on_section is not None:
                on_section(model, name, field, section)
            yield from iter_leaf_fields(section, path, on_section)
        else:
            yield path, model, name, field
