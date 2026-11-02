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

"""Renderer for the generated tables on ``docs/reference/configuration.md``.

The node configuration reference lists every setting a Vultron node reads from
``config.yaml`` and the ``VULTRON_*`` environment variables. Its tables and its
example file are generated at build time from
:class:`vultron.config.app.AppConfig` by a markdown-exec Python block, so a new,
renamed or re-defaulted field reaches the page without a docs edit (#4171).

Each leaf field of ``AppConfig`` becomes one :class:`ConfigSetting`: its YAML
key path, the environment variable that overrides it, a type label, its
default, its bounds and a description. The description is the field's
entry under its model's ``Attributes:`` docstring section when it has one,
else its ``Field(description=...)``; the docstring entry comes first because it
is the fuller of the two where both exist. A field with neither raises
:class:`ConfigReferenceError`, which fails the strict docs build rather than
publishing a blank row.

Sentences stating the default or the overriding variable are dropped from a
description, because the table prints both from the model; keeping them would
give one row two sources for the same fact.

Usage (in a markdown-exec Python block)::

    from vultron.metadata.docs.config_reference import render_settings_tables
    print(render_settings_tables())
"""

from __future__ import annotations

import inspect
import json
import re
import types
from dataclasses import dataclass
from datetime import timedelta
from enum import Enum
from typing import Any, Literal, Union, get_args, get_origin

import annotated_types
import yaml
from pydantic import BaseModel, HttpUrl, TypeAdapter
from pydantic.fields import FieldInfo
from pydantic_core import PydanticUndefined

from vultron.config.app import AppConfig

#: Prefix of every node environment variable (CFG-03-001).
ENV_PREFIX = "VULTRON_"

#: Separator between nested keys in an environment variable name (CFG-03-002).
ENV_NESTED_DELIMITER = "__"

#: Heading for the settings that sit at the top level of ``AppConfig``.
TOP_LEVEL_SECTION = "Top-level settings"

_ATTRIBUTES_HEADER = "Attributes:"
_ATTRIBUTE_ENTRY = re.compile(r"^(?P<name>\w+):\s*(?P<text>.*)$")
_DEFAULT_SENTENCE = re.compile(r"\s*Defaults?(?: to|:)\s.*?\.(?=\s|$)")
_OVERRIDE_SENTENCE = re.compile(r"\s*Override via\s.*?\.(?=\s|$)")
_SEE_CODE_SENTENCE = re.compile(r"\s*See :\w+:`[^`]+`\.")
_SPHINX_ROLE = re.compile(r":(?:class|func|data|attr|meth|mod):`~?([\w.]+)`")
_DOUBLE_BACKTICK = re.compile(r"``(.+?)``")


class ConfigReferenceError(ValueError):
    """An ``AppConfig`` field cannot be rendered on the reference page."""


@dataclass(frozen=True)
class ConfigSetting:
    """One leaf setting of :class:`AppConfig`, as the reference page lists it.

    Attributes:
        path: Field names from ``AppConfig`` down to the setting, for example
            ``("ledger", "staleness_window_days")``.
        type_label: Markdown label for the value the setting accepts.
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
        return ENV_PREFIX + ENV_NESTED_DELIMITER.join(self.path).upper()


def _docstring_attributes(model: type[BaseModel]) -> dict[str, str]:
    """Return the ``Attributes:`` entries of *model*'s docstring by field name."""
    doc = inspect.cleandoc(model.__doc__ or "")
    entries: dict[str, list[str]] = {}
    current: str | None = None
    in_section = False
    for line in doc.splitlines():
        if line.strip() == _ATTRIBUTES_HEADER:
            in_section = True
            continue
        if not in_section:
            continue
        if line and not line.startswith(" "):
            break  # the next unindented line ends the section
        stripped = line.strip()
        if not stripped:
            current = None
            continue
        # An entry starts at the section's first indent; a continuation is deeper.
        indent = len(line) - len(line.lstrip())
        match = _ATTRIBUTE_ENTRY.match(stripped)
        if match and indent <= 4:
            name = match.group("name")
            entries[name] = [match.group("text")]
            current = name
        elif current is not None:
            entries[current].append(stripped)
    return {name: " ".join(parts) for name, parts in entries.items()}


def _clean_description(text: str) -> str:
    """Turn docstring prose into table-cell Markdown without the default."""
    text = " ".join(text.split())
    text = _SEE_CODE_SENTENCE.sub("", text)  # points into code, not the reader
    text = _SPHINX_ROLE.sub(
        lambda m: f"``{m.group(1).rsplit('.', 1)[-1]}``", text
    )
    text = _DEFAULT_SENTENCE.sub("", text)
    text = _OVERRIDE_SENTENCE.sub("", text)
    text = _DOUBLE_BACKTICK.sub(r"`\1`", text)
    return text.strip().replace("|", "\\|")


def _description(model: type[BaseModel], name: str, field: FieldInfo) -> str:
    """Return the Markdown description of *model*'s field *name*.

    Raises:
        ConfigReferenceError: The field has neither an ``Attributes:``
            docstring entry nor a ``description``.
    """
    raw = _docstring_attributes(model).get(name) or field.description
    if not raw:
        raise ConfigReferenceError(
            f"{model.__name__}.{name} has no entry under the"
            f" {model.__name__} docstring's Attributes: section and no"
            " Field(description=...); the configuration reference page needs one to describe"
            " the setting."
        )
    return _clean_description(raw)


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


def _type_label(annotation: Any) -> str:
    """Return a reader-facing label for the values *annotation* accepts."""
    members, nullable = _non_null_args(annotation)
    labels = [_member_label(member) for member in members]
    label = " or ".join(labels)
    return f"{label}, or unset" if nullable else label


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


def _member_label(annotation: Any) -> str:
    """Return the label for one non-``None`` member of a field's annotation.

    Raises:
        ConfigReferenceError: The renderer has no label for *annotation*.
    """
    if get_origin(annotation) is Literal:
        return "string, " + _choices(
            [str(arg) for arg in get_args(annotation)]
        )
    if get_origin(annotation) is list:
        (item,) = get_args(annotation)
        item_label = _member_label(item)
        if item_label.startswith("string, "):
            return "list of strings, each " + item_label.removeprefix(
                "string, "
            )
        return f"list of {item_label}"
    if isinstance(annotation, type) and issubclass(annotation, Enum):
        return "string, " + _choices([str(m.value) for m in annotation])
    for scalar, label in _SCALAR_LABELS:
        if isinstance(annotation, type) and issubclass(annotation, scalar):
            return label
    raise ConfigReferenceError(
        f"no reference-page type label for annotation {annotation!r}; add one"
        " to vultron.metadata.docs.config_reference._SCALAR_LABELS."
    )


def _bounds(field: FieldInfo) -> str:
    """Return the field's numeric bounds as Markdown, e.g. ``≥ 1``."""
    parts: list[str] = []
    for item in field.metadata:
        if isinstance(item, annotated_types.Ge):
            parts.append(f"≥ {item.ge}")
        elif isinstance(item, annotated_types.Gt):
            parts.append(f"> {item.gt}")
        elif isinstance(item, annotated_types.Le):
            parts.append(f"≤ {item.le}")
        elif isinstance(item, annotated_types.Lt):
            parts.append(f"< {item.lt}")
    return ", ".join(parts)


def _default_value(field: FieldInfo) -> Any:
    """Return the field's default in JSON form, as ``config.yaml`` holds it."""
    if field.default_factory is not None:
        value = field.default_factory()  # type: ignore[call-arg]
    elif field.default is PydanticUndefined:
        raise ConfigReferenceError(
            "every AppConfig field has a default (CFG-02-005); found one"
            " without"
        )
    else:
        value = field.default
    return TypeAdapter(field.annotation).dump_python(value, mode="json")


def _render_default(value: Any) -> str:
    """Render a JSON-form default as a code span: strings bare, others as JSON."""
    if value is None:
        return "unset"
    text = value if isinstance(value, str) else json.dumps(value)
    return f"`{text}`".replace("|", "\\|")


def _is_section(field: FieldInfo) -> bool:
    annotation = field.annotation
    return isinstance(annotation, type) and issubclass(annotation, BaseModel)


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
        if _is_section(field):
            section = field.annotation
            assert isinstance(section, type) and issubclass(section, BaseModel)
            settings.extend(iter_settings(section, path))
            continue
        default_value = _default_value(field)
        settings.append(
            ConfigSetting(
                path=path,
                type_label=_type_label(field.annotation),
                default=_render_default(default_value),
                default_value=default_value,
                bounds=_bounds(field),
                description=_description(model, name, field),
            )
        )
    return settings


def _section_name(setting: ConfigSetting) -> str:
    return setting.path[0] if len(setting.path) > 1 else TOP_LEVEL_SECTION


def render_settings_tables(settings: list[ConfigSetting] | None = None) -> str:
    """Return one Markdown table per ``config.yaml`` section.

    Top-level settings come first, then each section in ``AppConfig`` order,
    headed by its key.
    """
    settings = iter_settings() if settings is None else settings
    sections: dict[str, list[ConfigSetting]] = {TOP_LEVEL_SECTION: []}
    for setting in settings:
        sections.setdefault(_section_name(setting), []).append(setting)

    lines: list[str] = []
    for name, members in sections.items():
        if not members:
            continue
        heading = name if name == TOP_LEVEL_SECTION else f"`{name}:` section"
        lines += [f"### {heading}", ""]
        lines += [
            "| YAML key | Environment variable | Type | Default | Description |",
            "|---|---|---|---|---|",
        ]
        for s in members:
            value_type = (
                f"{s.type_label} ({s.bounds})" if s.bounds else s.type_label
            )
            lines.append(
                f"| `{s.yaml_key}` | `{s.env_var}` | {value_type}"
                f" | {s.default} | {s.description} |"
            )
        lines.append("")
    return "\n".join(lines)


def default_config_yaml(settings: list[ConfigSetting] | None = None) -> str:
    """Return a ``config.yaml`` that sets every setting to its default."""
    settings = iter_settings() if settings is None else settings
    document: dict[str, Any] = {}
    for setting in settings:
        node = document
        for key in setting.path[:-1]:
            node = node.setdefault(key, {})
        node[setting.path[-1]] = setting.default_value
    return yaml.safe_dump(document, sort_keys=False, default_flow_style=False)


def render_default_config_block(
    settings: list[ConfigSetting] | None = None,
) -> str:
    """Return :func:`default_config_yaml` as a fenced ``yaml`` code block."""
    return f"```yaml\n{default_config_yaml(settings)}```\n"
