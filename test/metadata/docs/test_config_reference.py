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
"""Tests for the generated node configuration reference (#4171).

The page ``docs/reference/configuration.md`` renders its tables and example
file from ``AppConfig`` (CFG-02, CFG-03, CFG-04). These tests pin that every
leaf setting is listed, that the environment variable each row prints is the
one ``pydantic-settings`` reads, that the example file loads back to the
defaults, and that a field with no description fails rather than publishing a
blank row.
"""

from __future__ import annotations

import os
from datetime import timedelta
from pathlib import Path

import pytest
from pydantic import BaseModel, Field

from vultron.config.app import AppConfig, config_override
from vultron.metadata.base import repo_root
from vultron.metadata.docs.config_reference import (
    TOP_LEVEL_SECTION,
    ConfigReferenceError,
    ConfigSetting,
    default_config_yaml,
    iter_settings,
    render_default_config_block,
    render_settings_tables,
)


def _leaf_paths(model: type[BaseModel], prefix: tuple[str, ...] = ()):
    for name, field in model.model_fields.items():
        annotation = field.annotation
        if isinstance(annotation, type) and issubclass(annotation, BaseModel):
            yield from _leaf_paths(annotation, (*prefix, name))
        else:
            yield (*prefix, name)


@pytest.fixture(scope="module")
def settings() -> list[ConfigSetting]:
    return iter_settings()


def test_every_leaf_field_is_listed(settings: list[ConfigSetting]) -> None:
    assert [s.path for s in settings] == list(_leaf_paths(AppConfig))


def test_every_setting_has_a_description(
    settings: list[ConfigSetting],
) -> None:
    blank = [s.yaml_key for s in settings if not s.description]
    assert not blank


def test_env_var_names_follow_the_naming_rule(
    settings: list[ConfigSetting],
) -> None:
    by_key = {s.yaml_key: s.env_var for s in settings}
    assert by_key["mode"] == "VULTRON_MODE"
    assert by_key["server.base_url"] == "VULTRON_SERVER__BASE_URL"
    assert (
        by_key["ledger.staleness_window_days"]
        == "VULTRON_LEDGER__STALENESS_WINDOW_DAYS"
    )


def _sample_value(setting: ConfigSetting) -> tuple[str, object]:
    """Return an env-var string differing from the default, and its parsed value."""
    default = setting.default_value
    if isinstance(default, bool):
        return str(not default).lower(), not default
    if isinstance(default, int):
        return str(default + 1), default + 1
    if isinstance(default, float):
        return str(default + 1), default + 1
    return "", None


@pytest.mark.parametrize(
    "path",
    [p for p in _leaf_paths(AppConfig)],
    ids=".".join,
)
def test_printed_env_var_sets_its_field(path: tuple[str, ...]) -> None:
    """The variable a row prints is the one that overrides that field."""
    setting = next(s for s in iter_settings() if s.path == path)
    raw, expected = _sample_value(setting)
    if not raw:
        overrides = {
            "server.base_url": ("http://node.example:8000/api/v2", None),
            "server.log_level": ("debug", "DEBUG"),
            "database.db_url": ("sqlite:///other.db", None),
            "mode": ("prod", "prod"),
            "actor.default_case_roles": ('["vendor"]', ["vendor"]),
            "actor.case_actor_service_url": (
                "http://case-actor.example:7999/api/v2",
                "http://case-actor.example:7999/api/v2",
            ),
            "actor.min_rsvp_window": ("PT96H", timedelta(hours=96)),
            "actor.default_rsvp_window": ("P8D", timedelta(days=8)),
            "actor.protocol_default_embargo_duration": (
                "PT96H",
                timedelta(hours=96),
            ),
            "actor.post_close_reply": ("reject", "reject"),
            "ledger.position_statement_interval_seconds": ("60", 60),
        }
        raw, expected = overrides[setting.yaml_key]
        if expected is None:
            expected = raw
    with config_override(**{setting.env_var: raw}) as cfg:
        value: object = cfg
        for key in path:
            value = getattr(value, key)
    if isinstance(value, list):
        value = [str(item) for item in value]
    elif not isinstance(value, (bool, int, float, timedelta)):
        value = str(value)
    assert value == expected


def test_example_file_loads_back_to_the_defaults(
    tmp_path: Path, settings: list[ConfigSetting]
) -> None:
    """Every key in the example file loads, and loads to its default.

    A setting the test environment itself overrides (the suite points
    ``VULTRON_DATABASE__DB_URL`` at memory, for one) is skipped: the variable
    outranks the file, which is the precedence the page documents.
    """
    config_file = tmp_path / "config.yaml"
    config_file.write_text(default_config_yaml(settings))
    with config_override(VULTRON_CONFIG=str(config_file)) as cfg:
        loaded = cfg.model_dump(mode="json")
    checked = [s for s in settings if s.env_var not in os.environ]
    assert checked
    for setting in checked:
        value = loaded
        for key in setting.path:
            value = value[key]
        assert value == setting.default_value, setting.yaml_key


def test_tables_have_one_row_per_setting(
    settings: list[ConfigSetting],
) -> None:
    rendered = render_settings_tables(settings)
    for setting in settings:
        assert f"| `{setting.yaml_key}` | `{setting.env_var}` |" in rendered
    assert rendered.index(f"### {TOP_LEVEL_SECTION}") < rendered.index(
        "### `server:` section"
    )


def test_descriptions_drop_default_and_override_sentences(
    settings: list[ConfigSetting],
) -> None:
    for setting in settings:
        assert "Defaults to" not in setting.description, setting.yaml_key
        assert "Override via" not in setting.description, setting.yaml_key
        assert "``" not in setting.description, setting.yaml_key
        assert ":class:" not in setting.description, setting.yaml_key


def test_unset_default_renders_as_unset(settings: list[ConfigSetting]) -> None:
    url = next(
        s for s in settings if s.yaml_key == "actor.case_actor_service_url"
    )
    assert url.default == "unset"
    assert url.type_label == "HTTP(S) URL, or unset"


def test_bounds_are_rendered(settings: list[ConfigSetting]) -> None:
    attempts = next(
        s for s in settings if s.yaml_key == "max_object_fetch_attempts"
    )
    assert attempts.bounds == "≥ 1"


def test_default_block_is_a_yaml_fence(settings: list[ConfigSetting]) -> None:
    block = render_default_config_block(settings)
    assert block.startswith("```yaml\n") and block.endswith("```\n")


class _Undocumented(BaseModel):
    """A model whose field has no description anywhere."""

    blank: int = 0


class _FieldDescribed(BaseModel):
    """A model described only through ``Field``."""

    value: int = Field(default=1, description="A ``value``. Defaults to 1.")


class _DocDescribed(BaseModel):
    """A model described through its docstring.

    Attributes:
        value: The value, see ``x``.  Defaults to 2.  Override via
            ``VULTRON_VALUE``.
        other: Another value | with a pipe.
    """

    value: int = 2
    other: str = "a"


def test_field_without_description_fails() -> None:
    with pytest.raises(ConfigReferenceError, match=r"_Undocumented\.blank"):
        iter_settings(_Undocumented)


def test_field_description_is_the_fallback() -> None:
    (setting,) = iter_settings(_FieldDescribed)
    assert setting.description == "A `value`."


def test_docstring_attributes_are_read_and_cleaned() -> None:
    value, other = iter_settings(_DocDescribed)
    assert value.description == "The value, see `x`."
    assert other.description == "Another value \\| with a pipe."


class _Unlabelled(BaseModel):
    """A model with a type the renderer has no label for.

    Attributes:
        thing: A set.
    """

    thing: set[int] = Field(default_factory=set)


def test_unknown_type_fails() -> None:
    with pytest.raises(ConfigReferenceError, match="type label"):
        iter_settings(_Unlabelled)


def test_page_renders_the_generated_blocks() -> None:
    page = (
        repo_root() / "docs" / "reference" / "configuration.md"
    ).read_text()
    assert "render_settings_tables()" in page
    assert "render_default_config_block()" in page
