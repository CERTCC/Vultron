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

"""The read-only core view of a received activity (ADR-0149).

A receiver archives the body it received, and nothing derived from it
(CLP-10-017).  Core reads a received activity's facts by loading that body
through the ``ReceivedActivityLoader`` port: the adapter behind it parses the
body and runs the inbox's own extraction on it, and core gets the extracted
``VultronActivity`` wrapped in a :class:`ReceivedActivityView`.

The view is read-only all the way down.  A class-level ``frozen`` setting
would not do it: it covers the class that declares it, not the mutable core
objects nested in the activity, nor the lists and mappings they hold.  So the
view wraps the activity instead of copying it, and every attribute read
returns its value wrapped the same way: a model as another view, a list or a
tuple as a tuple of read-only values, a mapping as a read-only mapping.
Assigning to any of them raises, and the wrapped model is reachable through
no attribute of the view.  Each load parses the body afresh, so the next load
is the body's again whatever a caller did with an earlier one.

The view does not pass for the model it wraps: it is no ``BaseModel``, so a
Pydantic field refuses it and a reply cannot embed it, nor a store save it,
by mistake (DL-06-004).  A reader asks it for fields by name.
"""

from collections.abc import Mapping
from types import MappingProxyType
from typing import Any, cast

from pydantic import BaseModel

from vultron.errors import VultronReadOnlyViewError

__all__ = ["ReceivedActivityView", "read_only"]


def read_only(value: Any) -> Any:
    """*value* as a reader of a :class:`ReceivedActivityView` sees it.

    A model is wrapped in a view, a list, tuple or set becomes an immutable
    collection of read-only values, and a mapping a read-only mapping of
    them.  Anything else (a string, a number, a timestamp, an enum) is
    returned as it is: it is immutable already.
    """
    if isinstance(value, BaseModel):
        return ReceivedActivityView(value)
    if isinstance(value, (list, tuple)):
        return tuple(read_only(item) for item in value)
    if isinstance(value, (set, frozenset)):
        return frozenset(read_only(item) for item in value)
    if isinstance(value, Mapping):
        return MappingProxyType(
            {key: read_only(item) for key, item in value.items()}
        )
    return value


class ReceivedActivityView:
    """A read-only view of a model parsed from a received body.

    Reading an attribute returns its value made read-only
    (:func:`read_only`).  Assigning or deleting an attribute raises
    :class:`~vultron.errors.VultronReadOnlyViewError`.  Two views are equal
    when the models they wrap are equal.

    Args:
        model: The model to view.  The view does not copy it, so the caller
            hands over a model nobody else holds: the loader passes the one
            its parse just built.
    """

    __slots__ = ("_model",)

    def __init__(self, model: BaseModel) -> None:
        object.__setattr__(self, "_model", model)

    def __getattribute__(self, name: str) -> Any:
        # Every name but a dunder is one of the wrapped model's data
        # attributes, made read-only.  A method is refused: a bound method
        # holds the model (``__self__``) and ``model_copy`` would hand out a
        # mutable copy a reply could embed, so no attribute of the view
        # (``_model`` included) reaches the model.
        if name.startswith("__") and name.endswith("__"):
            return object.__getattribute__(self, name)
        model = _model_of(self)
        if not _is_data_attribute(model, name):
            raise AttributeError(
                f"a received activity's read-only view has no data attribute"
                f" {name!r}; a reader asks it for fields by name (ADR-0149)"
            )
        return read_only(getattr(model, name))

    def __setattr__(self, name: str, value: Any) -> None:
        raise VultronReadOnlyViewError(
            f"cannot set {name!r} on a received activity's read-only view"
            " (ADR-0149); core changes its own records, not what arrived"
        )

    def __delattr__(self, name: str) -> None:
        raise VultronReadOnlyViewError(
            f"cannot delete {name!r} from a received activity's read-only"
            " view (ADR-0149)"
        )

    def __eq__(self, other: object) -> bool:
        if type(other) is ReceivedActivityView:
            return _model_of(self) == _model_of(other)
        return NotImplemented

    __hash__ = None  # type: ignore[assignment]

    def __repr__(self) -> str:
        return f"ReceivedActivityView({_model_of(self)!r})"


def _model_of(view: ReceivedActivityView) -> BaseModel:
    """The model *view* wraps, for the view's own use alone."""
    return cast(BaseModel, object.__getattribute__(view, "_model"))


def _is_data_attribute(model: BaseModel, name: str) -> bool:
    """Whether *name* is a field, computed field or property of *model*."""
    model_type = type(model)
    return (
        name in model_type.model_fields
        or name in model_type.model_computed_fields
        or isinstance(getattr(model_type, name, None), property)
    )
