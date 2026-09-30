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
"""Shared probes for the CS-08-001 ratchets ("if present, then non-empty").

The wire ratchet (``test_wire_reference_fields_reject_blank``) and the core
ratchet (``test_core_reference_fields_reject_blank``) ask the same two
questions of a Pydantic field — which string leaves does its declared type
admit, and does the field refuse a blank in each shape it can arrive in — so
the answers live here once (CS-08-002).
"""

import inspect
from collections.abc import Iterator
from typing import Annotated, Any, get_args, get_origin

from pydantic import TypeAdapter, ValidationError
from pydantic.fields import FieldInfo

from vultron.core.models._helpers import strip_annotated

#: Every spelling of "the sender supplied no value".  Whitespace-only is blank
#: by the project's canonical predicate (``not v.strip()``, see
#: ``vultron.primitives._non_empty``): a guard that catches ``""`` but not
#: ``"   "`` has the same blind spot one character over.
BLANKS: tuple[str, ...] = ("", " ", "   ", "\t", "\n", " \t\n ")


def declared_type(field: FieldInfo) -> Any:
    """*field*'s annotation as declared, with a top-level ``Annotated`` restored.

    Pydantic strips a top-level ``Annotated[str, AfterValidator(...)]`` into
    ``field.metadata`` and reports ``annotation`` as bare ``str``, so a probe
    reading only ``annotation`` judges every ``NonEmptyString`` field to accept
    blanks.  Inside a union the wrapper is kept and ``metadata`` stays empty.
    """
    if field.metadata:
        return Annotated[(field.annotation, *field.metadata)]
    return field.annotation


def leaf_types(annotation: Any) -> Iterator[Any]:
    """Yield the leaf types *annotation* admits, with containers transparent.

    An ``Annotated[...]`` is a leaf — its validators are the point.  Both
    ``dict`` positions are walked: the index fields on ``VulnerabilityCase``
    key on actor and activity IRIs, so a key is as much a reference as a value.
    """
    if get_origin(annotation) is Annotated:
        yield annotation
        return
    args = get_args(annotation)
    if not args:
        yield annotation
        return
    for arg in args:
        if arg is type(None):
            continue
        yield from leaf_types(arg)


def string_leaves(annotation: Any) -> list[Any]:
    """The leaves of *annotation* whose bare type is ``str``."""
    return [
        leaf for leaf in leaf_types(annotation) if strip_annotated(leaf) is str
    ]


def _union_members(annotation: Any) -> list[Any]:
    """The non-``None`` members of a top-level union, else ``[annotation]``.

    A container's own parameters (``list[X]``) and an ``Annotated`` wrapper are
    not union members, so they come back whole.
    """
    if get_origin(annotation) in (Annotated, list, dict, set, tuple):
        return [annotation]
    args = [a for a in get_args(annotation) if a is not type(None)]
    return args or [annotation]


def blank_probes(annotation: Any, blank: str) -> Iterator[Any]:
    """Yield *blank* shaped for each way *annotation* can carry a string.

    A bare ``str`` field takes the blank itself; a ``list[...]`` member takes
    ``[blank]``; a ``dict[..., ...]`` member takes it once as a value and once
    as a key.  Probing a container with a bare string would be refused for the
    wrong reason (not a list) and prove nothing about the items.
    """
    seen: list[Any] = []
    for member in _union_members(annotation):
        origin = get_origin(member)
        probes: list[Any]
        if origin in (list, set, tuple):
            probes = [[blank]]
        elif origin is dict:
            # Probe only the positions that hold a string: a ``dict[NonEmptyString,
            # Any]`` payload legitimately carries a blank *value*.
            key_type, value_type = get_args(member)
            probes = []
            if string_leaves(key_type):
                probes.append({blank: "value"})
            if string_leaves(value_type):
                probes.append({"key": blank})
        else:
            probes = [blank]
        for probe in probes:
            if probe not in seen:
                seen.append(probe)
                yield probe


def rejects_blank(annotation: Any) -> bool:
    """True when every shaped blank probe fails validation against *annotation*."""
    adapter = TypeAdapter(annotation)
    for blank in BLANKS:
        for probe in blank_probes(annotation, blank):
            try:
                adapter.validate_python(probe)
            except ValidationError:
                continue
            return False
    return True


def owner_of(cls: type, field_name: str) -> type:
    """The class in *cls*'s MRO that declares *field_name*.

    Reads each class's own annotations (``inspect.get_annotations``, which
    also covers lazily evaluated ones) rather than ``model_fields``, which
    reports inherited fields as if the subclass declared them.
    """
    for base in cls.__mro__:
        if field_name in inspect.get_annotations(base):
            return base
    return cls
