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
import re
from datetime import timedelta
from pathlib import Path
from typing import Literal

import pytest
import yaml
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


def _by_key(settings: list[ConfigSetting]) -> dict[str, ConfigSetting]:
    return {s.yaml_key: s for s in settings}


@pytest.mark.parametrize(
    ("key", "description"),
    [
        (
            "object_fetch_timeout_seconds",
            "Timeout of each fetch attempt, in seconds (AKM-05-008)."
            " It matches the delivery timeout (SYNC-05-004).",
        ),
        (
            "actor.auto_create_case",
            "When `true`, create a `VulnerabilityCase` immediately on"
            " `Offer(VulnerabilityReport)` receipt (CM-15-001, CM-12-001, CP-09-001)."
            " When `false`, defer case creation so the receiver can send a"
            " pre-case ACK (`Read(Offer(VulnerabilityReport))`, VAM-02-003)"
            " before deciding to accept or reject (CM-15-002, CM-15-003;"
            " ADR-0015).",
        ),
        (
            "ledger.invite_resend_cooldown_seconds",
            "The base cooldown between two resends of one unanswered Invite"
            " to one participant (SYNC-20-005). Each consecutive resend"
            " doubles it. It matches the base of the ledger replay cooldown"
            " (SYNC-15-013).",
        ),
        (
            "actor.post_close_reply",
            "The one policy point for replies after the case closes: whether"
            " the CASE_MANAGER answers a late `Leave(VulnerabilityCase)` with"
            " an `as:Reject` or drops it. Every other late activity is dropped"
            " under either setting (CM-23-017, CM-23-045, ADR-0131).",
        ),
    ],
)
def test_real_descriptions_are_cleaned(
    settings: list[ConfigSetting], key: str, description: str
) -> None:
    """Default, override and code-pointer sentences go; the rest survives."""
    assert _by_key(settings)[key].description == description


def test_server_base_url_keeps_its_rationale(
    settings: list[ConfigSetting],
) -> None:
    description = _by_key(settings)["server.base_url"].description
    assert "the shape the compose files set" in description
    assert (
        "localhost" not in description
    )  # the default is the Default column's


_DEFAULT_LEAK = re.compile(
    r"\bDefaults?\b(?! (?:has|matches|ceiling|at))|\(default\)|by default"
)


def test_no_description_restates_a_default_or_a_variable(
    settings: list[ConfigSetting],
) -> None:
    for setting in settings:
        text = setting.description
        assert not _DEFAULT_LEAK.search(text), (setting.yaml_key, text)
        assert "Override via" not in text, setting.yaml_key
        assert "VULTRON_" not in text, setting.yaml_key


def test_descriptions_use_page_vocabulary(
    settings: list[ConfigSetting],
) -> None:
    """No Python literal, Sphinx role, RST span, issue number or MUST leaks."""
    for setting in settings:
        text = setting.description
        for token in (
            "`None`",
            "`True`",
            "`False`",
            "``",
            ":class:",
            "FAILURE",
        ):
            assert token not in text, (setting.yaml_key, token)
        assert not re.search(r"#\d", text), setting.yaml_key
        assert not re.search(r"\b(MUST|SHALL|SHOULD)\b", text), (
            setting.yaml_key
        )


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
            "actor.call_out_time_budget": ("PT10S", timedelta(seconds=10)),
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


def test_default_block_is_the_example_file(
    settings: list[ConfigSetting],
) -> None:
    block = render_default_config_block(settings)
    assert block.startswith("```yaml\n") and block.endswith("```\n")
    body = block.removeprefix("```yaml\n").removesuffix("```\n")
    assert yaml.safe_load(body) == yaml.safe_load(
        default_config_yaml(settings)
    )
    assert yaml.safe_load(body)["actor"]["min_rsvp_window"] == "P3D"


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


class _AllBounds(BaseModel):
    """Every bound kind.

    Attributes:
        low: Lower bounds.
        high: Upper bounds.
    """

    low: int = Field(default=5, ge=1, gt=0)
    high: int = Field(default=5, le=10, lt=11)


def test_every_bound_kind_renders() -> None:
    low, high = iter_settings(_AllBounds)
    assert low.bounds == "> 0, ≥ 1"
    assert high.bounds == "< 11, ≤ 10"
    assert high.type_label == "integer (< 11, ≤ 10)"


class _OtherConstraint(BaseModel):
    """A constraint the page cannot render.

    Attributes:
        roles: A list with a length limit.
    """

    roles: list[str] = Field(default_factory=list, max_length=3)


def test_unrenderable_constraint_fails() -> None:
    with pytest.raises(ConfigReferenceError, match=r"_OtherConstraint\.roles"):
        iter_settings(_OtherConstraint)


class _Required(BaseModel):
    """A field with no default.

    Attributes:
        needed: Required.
    """

    needed: int


def test_field_without_default_fails_naming_it() -> None:
    with pytest.raises(ConfigReferenceError, match=r"_Required\.needed"):
        iter_settings(_Required)


class _Lists(BaseModel):
    """Lists of non-string items, and integer literals.

    Attributes:
        counts: Integers.
        level: An integer literal.
    """

    counts: list[int] = Field(default_factory=lambda: [1, 2])
    level: Literal[1, 2] = 1


def test_non_string_list_and_literal_labels() -> None:
    counts, level = iter_settings(_Lists)
    assert counts.type_label == "list of integer"
    assert counts.default == "`[1, 2]`"
    assert level.type_label == "integer, one of `1`, `2`"


class _MixedLiteral(BaseModel):
    """A literal mixing value types.

    Attributes:
        mixed: Mixed.
    """

    mixed: Literal[1, "a"] = 1


class _BareList(BaseModel):
    """An unparameterized list.

    Attributes:
        items: Anything.
    """

    items: list = Field(default_factory=list)  # type: ignore[type-arg]


@pytest.mark.parametrize("model", [_MixedLiteral, _BareList])
def test_unlabeled_annotations_fail(model: type[BaseModel]) -> None:
    with pytest.raises(ConfigReferenceError, match="type label"):
        iter_settings(model)


class _TwoSpaceDocstring(BaseModel):
    """Entries at a two-space indent, with a deeper ``word:`` continuation.

    Attributes:
      first: The first value, which
        note: continues here rather than starting an entry.

      second: The second value.

        An orphan line after a blank belongs to no entry.

    Notes:
      third: Not an attribute.
    """

    first: int = 1
    second: int = 2
    third: int = Field(default=3, description="From Field.")


def test_docstring_entries_follow_the_first_entry_indent() -> None:
    first, second, third = iter_settings(_TwoSpaceDocstring)
    assert first.description == (
        "The first value, which note: continues here rather than starting an"
        " entry."
    )
    assert second.description == "The second value."
    assert third.description == "From Field."


class _OnlySections(BaseModel):
    """A model with sections and no top-level settings.

    Attributes:
        inner: A section.
    """

    inner: _FieldDescribed = _FieldDescribed()


def test_model_without_top_level_settings_has_no_top_level_table() -> None:
    rendered = render_settings_tables(iter_settings(_OnlySections))
    assert TOP_LEVEL_SECTION not in rendered
    assert "### `inner:` section" in rendered
    assert "| `inner.value` | `VULTRON_INNER__VALUE` |" in rendered


class _Literals(BaseModel):
    """Python literals in descriptions.

    Attributes:
        url: When ``None``, nothing happens; ``True`` and ``False`` read as
            JSON (CP-08-001, #1872).  See :class:`_Literals`.
    """

    url: str | None = None


def test_python_literals_and_issue_refs_are_rewritten() -> None:
    (url,) = iter_settings(_Literals)
    assert url.description == (
        "When unset, nothing happens; `true` and `false` read as JSON"
        " (CP-08-001)."
    )


class _CodeSpans(BaseModel):
    """Issue numbers and parentheses inside code spans.

    Attributes:
        path: Reached at ``/actors/#1`` by calling ``fetch()`` (#12).
            Read at startup (#3, CP-08-001); see ``fetch()`` (CP-08-002,
            issue #4).  Default ``"a"``.
    """

    path: str = "a"


def test_code_spans_keep_issue_marks_and_parentheses() -> None:
    (path,) = iter_settings(_CodeSpans)
    assert path.description == (
        "Reached at `/actors/#1` by calling `fetch()`. Read at startup"
        " (CP-08-001); see `fetch()` (CP-08-002)."
    )


class _DefaultWithExtraFact(BaseModel):
    """A default sentence that carries a second fact.

    Attributes:
        window: The window. Defaults to 30; set 0 to disable it.
    """

    window: int = 30


class _PointerWithExtraFact(BaseModel):
    """A code-pointer sentence that carries a second fact.

    Attributes:
        window: The window. See ``Policy`` for the values it refuses.
    """

    window: int = 30


class _WrongOverride(BaseModel):
    """An override sentence naming another variable.

    Attributes:
        window: The window. Override via ``VULTRON_OTHER``.
    """

    window: int = 30


class _OnlyDefault(BaseModel):
    """A description that is nothing but its default.

    Attributes:
        window: Defaults to 30.
    """

    window: int = 30


class _UnknownRole(BaseModel):
    """A Sphinx role the renderer does not convert.

    Attributes:
        window: Raises :exc:`ValueError` when negative.
    """

    window: int = 30


class _DanglingIssueRef(BaseModel):
    """An issue number that is not in a citation list.

    Attributes:
        window: The window (see #12).
    """

    window: int = 30


class _UnbalancedSpan(BaseModel):
    """An RST code span with no closing marks.

    Attributes:
        window: The ``window value.
    """

    window: int = 30


@pytest.mark.parametrize(
    ("model", "match"),
    [
        (_DefaultWithExtraFact, r"_DefaultWithExtraFact\.window.*says more"),
        (_PointerWithExtraFact, r"_PointerWithExtraFact\.window.*says more"),
        (_WrongOverride, r"_WrongOverride\.window.*VULTRON_WINDOW"),
        (_OnlyDefault, r"_OnlyDefault\.window.*empty"),
        (_UnknownRole, r"_UnknownRole\.window.*':exc:`'"),
        (_UnbalancedSpan, r"_UnbalancedSpan\.window.*'``'"),
        (_DanglingIssueRef, r"_DanglingIssueRef\.window.*'#1'"),
    ],
)
def test_unsafe_description_cleanup_fails(
    model: type[BaseModel], match: str
) -> None:
    """A description the heuristics would mangle fails the build instead."""
    with pytest.raises(ConfigReferenceError, match=match):
        iter_settings(model)


class _OverriddenSection(BaseModel):
    """A section whose parent default changes a leaf default.

    Attributes:
        inner: A section.
    """

    inner: _FieldDescribed = _FieldDescribed(value=5)


def test_section_default_overriding_leaf_defaults_fails() -> None:
    with pytest.raises(
        ConfigReferenceError, match=r"_OverriddenSection\.inner"
    ):
        iter_settings(_OverriddenSection)


@pytest.mark.parametrize(
    ("variable", "raw"),
    [
        ("VULTRON_ACTOR__MIN_RSVP_WINDOW", "259200"),
        ("VULTRON_ACTOR__DEFAULT_CASE_ROLES", "vendor"),
    ],
)
def test_env_value_formats_the_page_refuses(variable: str, raw: str) -> None:
    """A bare number for a duration, and a non-JSON list, are refused."""
    with pytest.raises(ValueError):
        with config_override(**{variable: raw}):
            pass


def test_yaml_duration_accepts_a_number_of_seconds(tmp_path: Path) -> None:
    config_file = tmp_path / "config.yaml"
    config_file.write_text("actor:\n  min_rsvp_window: 345600\n")
    with config_override(VULTRON_CONFIG=str(config_file)) as cfg:
        assert cfg.actor.min_rsvp_window == timedelta(hours=96)


def test_unknown_top_level_key_is_refused(tmp_path: Path) -> None:
    config_file = tmp_path / "config.yaml"
    config_file.write_text("bogus: 1\n")
    with pytest.raises(ValueError, match="bogus"):
        with config_override(VULTRON_CONFIG=str(config_file)):
            pass


def test_unknown_section_key_is_ignored(tmp_path: Path) -> None:
    """Pins the page's sentence on unknown section keys; #3656 will refuse them."""
    config_file = tmp_path / "config.yaml"
    config_file.write_text("actor:\n  auto_create_cas: false\n")
    with config_override(VULTRON_CONFIG=str(config_file)) as cfg:
        assert cfg.actor.auto_create_case is True
