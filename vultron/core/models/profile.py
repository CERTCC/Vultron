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

"""A model profile: a declared, checked subset of another model (ADR-0186).

A **profile** is its own model class whose every field has the name and type
of a field of the model it profiles (its :attr:`ModelProfile.profile_of`).  A
field may narrow the profiled field's type (``NonEmptyString`` where the
model allows ``NonEmptyString | None``), and a field that holds a nested
object holds that object's own profile, checked the same way.

A profile fails closed.  It is not a subclass of the model it profiles, so a
field added to that model later reaches the profile only when someone
declares it there, and code that takes the model never takes a profile.
:func:`profile_violations` is the check that the fields stay a subset, at
every nesting level (BT-24-009); every profile in ``vultron/`` is held to it
by a ratchet test that finds each one by its source.

The suggestion context the participant-suggestion port takes is the first
profile (:mod:`vultron.core.models.participant_suggestion`); a CSAF adapter
or a Sentinel's view of a case may declare their own the same way.
"""

from __future__ import annotations

import types
import typing
from collections.abc import Mapping
from typing import ClassVar, Self, get_args, get_origin

from pydantic import BaseModel, ConfigDict, ValidationError

from vultron.core.models.base import ValidatedAssignmentMixin
from vultron.errors import VultronValidationError


class ModelProfile(ValidatedAssignmentMixin):
    """The base of every model profile; see the module docstring.

    Class attributes:
        profile_of: The model class this profile is a subset of.  Every
            concrete profile sets it.
    """

    model_config = ConfigDict(extra="forbid", frozen=True)

    profile_of: ClassVar[type[BaseModel]]

    @classmethod
    def from_model(cls, source: BaseModel) -> Self:
        """Build this profile by copying each of its fields from *source*.

        For a profile whose fields hold no nested profile.  A profile that
        holds one builds it field by field instead.

        Raises:
            TypeError: *source* is not an instance of :attr:`profile_of`.
            VultronValidationError: A value of *source* does not fit the
                profile's narrower type, such as a missing value on a field
                the profile requires.
        """
        if not isinstance(source, cls.profile_of):
            raise TypeError(
                f"{cls.__name__} profiles {cls.profile_of.__name__}, not "
                f"{type(source).__name__}."
            )
        return cls._build(
            {name: getattr(source, name) for name in cls.model_fields},
            source,
        )

    @classmethod
    def _build(
        cls,
        values: dict[str, object],
        source: BaseModel,
        context: Mapping[str, object] | None = None,
    ) -> Self:
        """Validate *values* as this profile, naming *source* on a refusal.

        *context* is passed to validation, for a profile whose validator
        admits only its own constructor.
        """
        try:
            return cls.model_validate(values, context=context)
        except ValidationError as exc:
            source_id = getattr(source, "id_", None) or "<no id>"
            raise VultronValidationError(
                f"{type(source).__name__} '{source_id}' does not fit "
                f"{cls.__name__}: {exc}"
            ) from exc


def _members(annotation: object) -> tuple[object, ...]:
    """The members of a union annotation, or the annotation alone."""
    if get_origin(annotation) in (typing.Union, types.UnionType):
        return get_args(annotation)
    return (annotation,)


def _admits(source: object, narrowed: object) -> bool:
    """Whether the annotation *source* admits every value of *narrowed*.

    A union admits a member that one of its own members admits.  A nested
    profile stands for the model it profiles.  A parameterised generic
    (``list[X]``) admits one of the same origin whose arguments it admits.
    Any other annotation admits only itself, so ``str`` never stands in for
    ``NonEmptyString``.
    """
    return all(
        any(_admits_member(s, n) for s in _members(source))
        for n in _members(narrowed)
    )


def _admits_member(source: object, narrowed: object) -> bool:
    if isinstance(narrowed, type) and issubclass(narrowed, ModelProfile):
        return narrowed.profile_of is source
    if source == narrowed:
        return True
    origin = get_origin(narrowed)
    if origin is None or origin is typing.Annotated:
        return False
    if get_origin(source) is not origin:
        return False
    source_args, narrowed_args = get_args(source), get_args(narrowed)
    return len(source_args) == len(narrowed_args) and all(
        _admits(s, n) for s, n in zip(source_args, narrowed_args, strict=True)
    )


def _nested_profiles(annotation: object) -> set[type[ModelProfile]]:
    """Every profile class *annotation* names, at any depth."""
    if isinstance(annotation, type) and issubclass(annotation, ModelProfile):
        return {annotation}
    found: set[type[ModelProfile]] = set()
    for arg in get_args(annotation):
        found |= _nested_profiles(arg)
    return found


def _field_hints(model: type[BaseModel]) -> dict[str, object]:
    """*model*'s field annotations, with ``Annotated`` metadata kept."""
    hints = typing.get_type_hints(model, include_extras=True)
    return {name: hints[name] for name in model.model_fields}


def profile_violations(profile: type[ModelProfile]) -> list[str]:
    """Every way *profile*'s fields are not a subset of its model's.

    Walks every nested profile too, so the subset holds at every level.  An
    empty list means the profile holds.
    """
    problems: list[str] = []
    seen: set[type[ModelProfile]] = set()
    pending = [profile]
    while pending:
        current = pending.pop()
        if current in seen:
            continue
        seen.add(current)
        source = getattr(current, "profile_of", None)
        if not (isinstance(source, type) and issubclass(source, BaseModel)):
            problems.append(f"{current.__name__} names no model it profiles")
            continue
        source_hints = _field_hints(source)
        for name, annotation in _field_hints(current).items():
            where = f"{current.__name__}.{name}"
            if name not in source_hints:
                problems.append(f"{where} is not a field of {source.__name__}")
            elif not _admits(source_hints[name], annotation):
                problems.append(
                    f"{where} is {annotation!r}, which "
                    f"{source.__name__}.{name} ({source_hints[name]!r}) "
                    "does not admit"
                )
            pending.extend(_nested_profiles(annotation))
    return problems


__all__ = ["ModelProfile", "profile_violations"]
