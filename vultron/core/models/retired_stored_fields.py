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

"""Refuse a stored record that still carries a renamed field's old key.

The project has no backwards-compatibility requirement for stored data, so a
renamed persisted field gets no read alias and no conversion.  Left alone, a
row written before the rename would not say what happened: ``CoreRecord``
ignores unknown keys, so the row reads back with an optional new field
silently ``None``, or fails with a bare "field required" for a name the
operator never wrote.  A model that renames a stored field derives from
:class:`RetiredFieldsRecord` and declares the old key in
``retired_stored_fields``; loading a row that still holds it fails with a
message naming the old shape and saying the store must be reset.  The
datalayer logs that reason when it reads the row back as absent.
"""

from collections.abc import Mapping
from typing import Any, ClassVar, NamedTuple

from pydantic import model_validator
from pydantic.alias_generators import to_camel

from vultron.core.models.base import CoreRecord
from vultron.errors import Violation, VultronValidationError


class RetiredStoredField(NamedTuple):
    """Where a retired stored key went, and the change that retired it."""

    replacement: str
    retired_by: str


class RetiredFieldsRecord(CoreRecord):
    """A ``CoreRecord`` that refuses data carrying a retired stored key.

    Both spellings of the old key are refused: the field name, and its
    camelCase form in case the row was written by an aliased dump.
    """

    retired_stored_fields: ClassVar[Mapping[str, RetiredStoredField]] = {}

    @classmethod
    def __pydantic_init_subclass__(cls, **kwargs: Any) -> None:
        """Refuse a retirement table that does not describe this model.

        Runs once the subclass's fields are complete, so ``model_fields`` is
        this class's own.  A replacement that names no declared field would
        send the operator to a field that does not exist, and an old key that
        is still declared would refuse every row the model writes.
        """
        super().__pydantic_init_subclass__(**kwargs)
        fields = cls.model_fields
        for old, field in cls.retired_stored_fields.items():
            if old in fields:
                raise TypeError(
                    f"{cls.__name__} retires {old!r} but still declares it"
                )
            if field.replacement not in fields:
                raise TypeError(
                    f"{cls.__name__} retires {old!r} in favour of"
                    f" {field.replacement!r}, which it does not declare"
                )

    @model_validator(mode="before")
    @classmethod
    def _refuse_retired_stored_fields(cls, data: Any) -> Any:
        if not isinstance(data, dict):
            return data
        violations = [
            Violation(
                f"{key!r} is the stored shape before {field.retired_by}"
                f" renamed it to {field.replacement!r}",
                (field.replacement,),
            )
            for old, field in cls.retired_stored_fields.items()
            for key in (old, to_camel(old))
            if key in data
        ]
        if violations:
            raise VultronValidationError(
                f"{cls.__name__} carries a retired stored field; no"
                " conversion is made, so a store written before the rename"
                " must be reset",
                violations=violations,
            )
        return data


__all__ = ["RetiredStoredField", "RetiredFieldsRecord"]
