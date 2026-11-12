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

"""The computed-field contract of ``CoreObject`` (ARCH-23-005).

A ``@computed_field`` is published on the AS2 path but never settable: a
supplied value must match the derived one, and a computed field may not
declare a field serializer.  ``CoreObject``'s hooks delegate here.
"""

from functools import cache
from typing import TYPE_CHECKING, Any

from pydantic import BaseModel, TypeAdapter
from pydantic.alias_generators import to_camel
from pydantic.functional_validators import ModelWrapValidatorHandler

from vultron.errors import Violation, VultronProtocolViolationError

if TYPE_CHECKING:
    from vultron.core.models.base.core_object import CoreObject


@cache
def _type_adapter(return_type: Any) -> TypeAdapter[Any]:
    """One ``TypeAdapter`` per computed-field return type, built once."""
    return TypeAdapter(return_type)


def _json_form(return_type: Any, value: Any) -> Any:
    """Return *value*'s ``mode="json"`` form under its declared *return_type*.

    Exact only while the computed field declares no ``@field_serializer``,
    which :meth:`CoreObject.__pydantic_init_subclass__` enforces.
    """
    return _type_adapter(return_type).dump_python(value, mode="json")


def computed_field_spellings(cls: type[BaseModel]) -> dict[str, str]:
    """Map every key spelling a computed field of *cls* can arrive under to its name."""
    spellings: dict[str, str] = {}
    for name, info in cls.model_computed_fields.items():
        spellings[name] = name
        # CoreObject carries alias_generator=to_camel (ARCH-25-002, ADR-0099), so
        # dump(by_alias=True) emits `embargoAdherence`.
        spellings[to_camel(name)] = name
        alias = getattr(info, "alias", None)
        if isinstance(alias, str):
            spellings[alias] = name
    return spellings


def check_computed_field_inputs(
    cls: type[CoreObject],
    data: Any,
    handler: ModelWrapValidatorHandler[CoreObject],
) -> CoreObject:
    """Strip or refuse the computed-field values supplied in *data*.

    The body of ``CoreObject._check_computed_field_inputs``, which documents
    the rule (ARCH-23-005, EH-07-001).
    """
    computed = cls.model_computed_fields
    if not isinstance(data, dict) or not computed:
        return handler(data)

    spellings = cls._computed_field_spellings()

    # Record every supplied computed-field value under the spelling it
    # arrived with, so that disagreeing duplicate spellings are each seen.
    supplied: list[tuple[str, str, Any]] = [
        (spelling, field_name, data[spelling])
        for spelling, field_name in spellings.items()
        if spelling in data
    ]
    if not supplied:
        return handler(data)

    # Strip every spelling before passing to the wrapped handler so that
    # extra="forbid" does not reject them.
    obj = handler({k: v for k, v in data.items() if k not in spellings})

    # Each derived value's JSON form comes from its declared return type:
    # the persistence dump omits computed fields (CM-31-014), and core
    # does not render the AS2 dump itself (ARCH-20-001).  A computed field
    # may not declare a field serializer, so the two forms agree
    # (:meth:`__pydantic_init_subclass__`).
    derived_json = {
        field_name: _json_form(
            computed[field_name].return_type, getattr(obj, field_name)
        )
        for field_name in {name for _spelling, name, _value in supplied}
    }
    violations = [
        Violation(
            message=(
                f"{field_name!r} (as {spelling!r}): supplied"
                f" {supplied_val!r}, derived {getattr(obj, field_name)!r}"
            ),
            dimensions=(field_name,),
        )
        for spelling, field_name, supplied_val in supplied
        if supplied_val != getattr(obj, field_name)
        and supplied_val != derived_json[field_name]
    ]
    if violations:
        raise VultronProtocolViolationError(
            "Supplied computed-field value(s) contradict derived state"
            " (ARCH-23-005)",
            violations=violations,
        )
    return obj


def refuse_computed_field_serializers(cls: type[BaseModel]) -> None:
    """Raise ``TypeError`` when a computed field of *cls* declares a serializer.

    The body of ``CoreObject.__pydantic_init_subclass__`` (ARCH-23-005).
    """
    computed = set(cls.model_computed_fields)
    serialized = {
        field
        for decorator in cls.__pydantic_decorators__.field_serializers.values()
        for field in decorator.info.fields
    }
    if clash := sorted(computed & serialized):
        raise TypeError(
            f"{cls.__name__}: computed field(s) {clash} declare a field"
            " serializer; derive the published value in the property"
            " instead (ARCH-23-005)"
        )
