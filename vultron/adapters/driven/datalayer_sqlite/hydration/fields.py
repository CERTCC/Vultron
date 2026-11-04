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

"""Field-admission introspection for row hydration.

Which model classes a declared field admits, so the hydration pipeline can
tell whether a referenced object may be expanded into that slot.
"""

from typing import Any, get_args

from pydantic import BaseModel


def field_admits_object(obj: Any, field_name: str) -> bool:
    """True when *field_name* on *obj* can legitimately hold a nested object.

    :func:`object_ref_fields` names fields that are *usually* references, but the
    same name can be declared as a plain URI on a particular model (for instance
    ``as_CaseProposal.target``, required by CP-01-005 to be the case-actor's URI).
    Expanding such a field yields a model that violates its own annotation —
    ``model_copy`` does not validate, so the breach surfaces later and elsewhere.

    Unknown fields are treated as expandable, preserving the previous behaviour
    for models that do not declare the field at all.
    """
    return class_field_admits_object(type(obj), field_name)


def class_field_admits_object(cls: type, field_name: str) -> bool:
    """:func:`field_admits_object` for a class rather than an instance.

    :func:`coerce_to_semantic_class` asks it of the semantic class it is
    about to validate into, which may declare a field a plain URI that the
    stored base class declared a reference (#5513).
    """
    models = _field_model_classes(cls, field_name)
    return models is None or bool(models)


def _field_model_classes(cls: type, field_name: str) -> list[type] | None:
    """The model classes *cls*'s annotation of *field_name* names.

    ``None`` when *cls* does not declare the field, or declares it with no
    annotation; an empty list when the field holds no model at all (a plain
    URI).
    """
    # ``PersistableModel`` is a Protocol, so ``model_fields`` is reached
    # defensively rather than assumed.
    model_fields = getattr(cls, "model_fields", None)
    field = model_fields.get(field_name) if model_fields else None
    if field is None or field.annotation is None:
        return None
    models: list[type] = []
    for candidate in get_args(field.annotation) or (field.annotation,):
        # Unwrap one more level for containers such as ``Ref[as_Foo]``.
        for part in get_args(candidate) or (candidate,):
            if isinstance(part, type) and issubclass(part, BaseModel):
                models.append(part)
    return models


def _declared_model_class(cls: type, field_name: str) -> type | None:
    """The one model class *cls* declares *field_name* as, else ``None``."""
    models = _field_model_classes(cls, field_name)
    return models[0] if models is not None and len(models) == 1 else None
