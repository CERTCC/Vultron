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

"""The leaf settings of ``AppConfig``: key path, variable, type, default."""

from __future__ import annotations

import json
import types
from dataclasses import dataclass
from datetime import timedelta
from enum import Enum
from typing import Any, Literal, Union, get_args, get_origin

import annotated_types
from pydantic import BaseModel, HttpUrl
from pydantic.fields import FieldInfo

from vultron.config.app import AppConfig
from vultron.metadata.docs.config_reference.descriptions import (
    field_description,
)
from vultron.metadata.docs.config_reference.errors import (
    ConfigReferenceError,
    field_ref,
)

#: Prefix of every node environment variable (CFG-03-001).
ENV_PREFIX = "VULTRON_"

#: Separator between nested keys in an environment variable name (CFG-03-002).
ENV_NESTED_DELIMITER = "__"

#: Labels for scalar types, checked in order: ``bool`` before ``int`` because
#: ``bool`` subclasses ``int``. An ``Enum`` is labeled before these by its values.
_SCALAR_LABELS: tuple[tuple[type, str], ...] = (
    (bool, "boolean"),
    (int, "integer"),
    (float, "number"),
    (timedelta, "duration"),
    (HttpUrl, "HTTP(S) URL"),
    (str, "string"),
)

#: Numeric bound constraints the page renders, with their symbols.
_BOUND_SYMBOLS: tuple[tuple[type, str, str], ...] = (
    (annotated_types.Ge, "ge", "≥"),
    (annotated_types.Gt, "gt", ">"),
    (annotated_types.Le, "le", "≤"),
    (annotated_types.Lt, "lt", "<"),
)


@dataclass(frozen=True)
class ConfigSetting:
    """One leaf setting of :class:`AppConfig`, as the reference page lists it.

    Attributes:
        path: Field names from ``AppConfig`` down to the setting, for example
            ``("ledger", "staleness_window_days")``.
        type_label: Markdown label for the value the setting accepts, bounds
            included, for example ``integer (≥ 1), or unset``.
        default: Markdown rendering of the default value.
        default_value: The default in JSON form, as ``config.yaml`` holds it.
        bounds: Markdown rendering of the numeric bounds, or empty.
        description: Markdown description of the setting.
    """

    path: tuple[str, ...]
    type_label: str
    default: str
    default_value: Any
    bounds: str
    description: str

    @property
    def yaml_key(self) -> str:
        """The dotted key path in ``config.yaml``, e.g. ``ledger.staleness_window_days``."""
        return ".".join(self.path)

    @property
    def env_var(self) -> str:
        """The environment variable that overrides the setting (CFG-03)."""
        return env_var_name(self.path)


def env_var_name(path: tuple[str, ...]) -> str:
    """Return the environment variable for the setting at *path* (CFG-03)."""
    return ENV_PREFIX + ENV_NESTED_DELIMITER.join(path).upper()


def _non_null_args(annotation: Any) -> tuple[list[Any], bool]:
    """Split an optional annotation into its non-``None`` members and nullability."""
    origin = get_origin(annotation)
    if origin is Union or origin is types.UnionType:
        args = list(get_args(annotation))
        members = [arg for arg in args if arg is not type(None)]
        return members, len(members) != len(args)
    return [annotation], False


def _choices(values: list[str]) -> str:
    return "one of " + ", ".join(f"`{value}`" for value in values)


def _unlabeled(annotation: Any) -> ConfigReferenceError:
    return ConfigReferenceError(
        f"no reference-page type label for annotation {annotation!r}; add one"
        " to vultron.metadata.docs.config_reference.settings."
    )


def _scalar_label(annotation: Any) -> str | None:
    for scalar, label in _SCALAR_LABELS:
        if isinstance(annotation, type) and issubclass(annotation, scalar):
            return label
    return None


def _literal_label(annotation: Any) -> str:
    values = get_args(annotation)
    labels = {_scalar_label(type(value)) for value in values}
    if len(labels) != 1 or None in labels:
        raise _unlabeled(annotation)
    (label,) = labels
    return f"{label}, " + _choices([str(value) for value in values])


def _member_label(annotation: Any) -> str:
    """Return the label for one non-``None`` member of a field's annotation.

    Raises:
        ConfigReferenceError: The renderer has no label for *annotation*.
    """
    if get_origin(annotation) is Literal:
        return _literal_label(annotation)
    if get_origin(annotation) is list:
        (item,) = get_args(annotation)  # list[X] always has exactly one
        item_label = _member_label(item)
        if item_label.startswith("string, "):
            return "list of strings, each " + item_label.removeprefix(
                "string, "
            )
        return f"list of {item_label}"
    if isinstance(annotation, type) and issubclass(annotation, Enum):
        return "string, " + _choices([str(m.value) for m in annotation])
    label = _scalar_label(annotation)
    if label is None:
        raise _unlabeled(annotation)
    return label


def _type_label(annotation: Any, bounds: str) -> str:
    """Return a reader-facing label for the values *annotation* accepts.

    Bounds attach to the value type, before any ``or unset``, so they never
    read as applying to the unset case.
    """
    members, nullable = _non_null_args(annotation)
    label = " or ".join(_member_label(member) for member in members)
    if bounds:
        label = f"{label} ({bounds})"
    return f"{label}, or unset" if nullable else label


def _bounds(model: type[BaseModel], name: str, field: FieldInfo) -> str:
    """Return the field's numeric bounds as Markdown, e.g. ``≥ 1``.

    Raises:
        ConfigReferenceError: The field carries a constraint the page cannot
            render, which would otherwise be dropped from the page silently.
    """
    parts: list[str] = []
    for item in field.metadata:
        for kind, attr, symbol in _BOUND_SYMBOLS:
            if isinstance(item, kind):
                parts.append(f"{symbol} {getattr(item, attr)}")
                break
        else:
            raise ConfigReferenceError(
                f"{field_ref(model, name)} carries constraint {item!r}, which"
                " the configuration reference page cannot render; add it to"
                " vultron.metadata.docs.config_reference.settings._BOUND_SYMBOLS."
            )
    return ", ".join(parts)


def _default_value(model: type[BaseModel], name: str, field: FieldInfo) -> Any:
    """Return the field's default in JSON form, as ``config.yaml`` holds it.

    The value is serialized through *model*, so a field serializer the model
    declares shapes it exactly as the node would. ``model_construct`` builds
    the model without reading any settings source.

    Raises:
        ConfigReferenceError: The field has no default (CFG-02-005).
    """
    if field.is_required():
        raise ConfigReferenceError(
            f"{field_ref(model, name)} has no default; every node setting"
            " needs one so a node starts with no configuration (CFG-02-005)."
        )
    value = field.get_default(call_default_factory=True, validated_data={})
    dumped = model.model_construct(**{name: value}).model_dump(
        mode="json", include={name}
    )
    return dumped[name]


def _render_default(value: Any) -> str:
    """Render a JSON-form default as a code span: strings bare, others as JSON."""
    if value is None:
        return "unset"
    text = value if isinstance(value, str) else json.dumps(value)
    return f"`{text}`".replace("|", "\\|")


def _check_section_default(
    model: type[BaseModel],
    name: str,
    field: FieldInfo,
    section: type[BaseModel],
) -> None:
    """Refuse a section whose default instance overrides its fields' defaults.

    The page reads each leaf's default from the section model's own fields, so
    a parent default such as ``ServerConfig(log_level="DEBUG")`` would put the
    wrong default on the page.

    Raises:
        ConfigReferenceError: The section's default is not ``section()``.
    """
    default = field.get_default(call_default_factory=True, validated_data={})
    if default != section():
        raise ConfigReferenceError(
            f"{field_ref(model, name)} defaults to {default!r}, not"
            f" {section.__name__}(); the configuration reference page reads"
            " leaf defaults from the section model, so set them there."
        )


def iter_settings(
    model: type[BaseModel] = AppConfig, prefix: tuple[str, ...] = ()
) -> list[ConfigSetting]:
    """Return every leaf setting under *model*, in declaration order.

    A field whose type is itself a model is a section: its leaves are listed
    under the section's key rather than the section itself.

    Raises:
        ConfigReferenceError: A leaf field cannot be rendered.
    """
    settings: list[ConfigSetting] = []
    for name, field in model.model_fields.items():
        path = (*prefix, name)
        section = field.annotation
        if isinstance(section, type) and issubclass(section, BaseModel):
            _check_section_default(model, name, field, section)
            settings.extend(iter_settings(section, path))
            continue
        default_value = _default_value(model, name, field)
        bounds = _bounds(model, name, field)
        settings.append(
            ConfigSetting(
                path=path,
                type_label=_type_label(field.annotation, bounds),
                default=_render_default(default_value),
                default_value=default_value,
                bounds=bounds,
                description=field_description(
                    model, name, field, env_var_name(path)
                ),
            )
        )
    return settings
