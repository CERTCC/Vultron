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
"""The comparison script of the CSAF draft-watch job (CSAF-05-005, CSAF-05-007).

Upstream is stood in for by a copy of the pinned local copy, edited, and the
pinned checkout by hand-written profile text and a test-case index. The
Technical Committee's own test documents are never read (CSAF-05-004).
"""

from __future__ import annotations

import json
import shutil
from collections.abc import Callable, Mapping
from pathlib import Path
from typing import Any

import pytest

from vultron.metadata.csaf import draft_watch
from vultron.metadata.csaf.draft_watch import (
    EXIT_CHANGED,
    PROFILES_FILE,
    READ_FIELDS,
    TESTCASES_FILE,
    ReadField,
    SchemaSet,
    compare,
    compare_profiles,
    compare_schemas,
    compare_tests,
    render_issue,
    strip_annotations,
)
from vultron.metadata.csaf.pin import PINNED_COPY_DIR, CsafPin, load_pin

#: A parsed JSON schema, edited in place by a test.
Schema = dict[str, Any]

_DISCLOSURE = ReadField("vulnerabilities[].disclosure_date", ("CSAF-03-001",))
_TITLE = ReadField("document.title", ("CSAF-03-007",))
_PROFILES = "# Profiles\n\n## CSAF Base\n\nA base profile.\n"


def _testcases(*tests: tuple[str, str]) -> str:
    return json.dumps(
        {
            "tests": [
                {"id": test_id, "group": group} for test_id, group in tests
            ]
        }
    )


_TESTS = _testcases(("6.1.1", "mandatory"), ("6.2.1", "recommended"))


def _write(root: Path, relative: object, text: str) -> None:
    path = root / str(relative)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def _checkout(
    root: Path, profiles: str = _PROFILES, tests: str = _TESTS
) -> Path:
    _write(root, PROFILES_FILE, profiles)
    _write(root, TESTCASES_FILE, tests)
    return root


@pytest.fixture
def pin() -> CsafPin:
    return load_pin()


@pytest.fixture
def upstream(tmp_path: Path) -> Path:
    """A stand-in upstream head: the pinned schemas, profiles and test list."""
    root = tmp_path / "upstream"
    shutil.copytree(PINNED_COPY_DIR / "csaf_2.1", root / "csaf_2.1")
    return _checkout(root)


@pytest.fixture
def baseline(tmp_path: Path) -> Path:
    """A stand-in checkout at the pinned commit."""
    return _checkout(tmp_path / "baseline")


def _edit_root(
    upstream: Path, pin: CsafPin, edit: Callable[[Schema], object]
) -> None:
    path = upstream / pin.root
    schema = json.loads(path.read_bytes())
    edit(schema)
    path.write_text(json.dumps(schema, indent=2), encoding="utf-8")


def _vulnerability(schema: Schema) -> Schema:
    """Return the properties of a vulnerability in the CSAF schema *schema*."""
    properties: Schema = schema["properties"]["vulnerabilities"]["items"][
        "properties"
    ]
    return properties


def _no_models(_source: Path, _pin: CsafPin) -> Mapping[str, str]:
    """Stand in for generation where the models are not under test."""
    return {}


def _never_render(_source: Path, _pin: CsafPin) -> Mapping[str, str]:
    raise AssertionError("models must not be generated for this change")


@pytest.mark.spec("CSAF-05-005")
def test_a_description_only_revision_reports_no_change(
    upstream: Path, pin: CsafPin
) -> None:
    def reword(schema: Schema) -> None:
        schema["description"] = "Reworded."
        _vulnerability(schema)["disclosure_date"]["description"] = "Reworded."

    _edit_root(upstream, pin, reword)

    change = compare_schemas(pin, upstream, render=_never_render)

    assert not change.changed, change


@pytest.fixture(scope="module")
def property_change(
    tmp_path_factory: pytest.TempPathFactory,
) -> draft_watch.DraftChange:
    """Compare an upstream whose ``disclosure_date`` became a plain date."""
    pin = load_pin()
    root = tmp_path_factory.mktemp("upstream")
    shutil.copytree(PINNED_COPY_DIR / "csaf_2.1", root / "csaf_2.1")

    def to_date(schema: Schema) -> None:
        _vulnerability(schema)["disclosure_date"]["format"] = "date"

    _edit_root(root, pin, to_date)
    return compare_schemas(pin, root)


@pytest.mark.spec("CSAF-05-005")
def test_a_revision_that_changes_a_property_reports_a_change(
    property_change: draft_watch.DraftChange,
) -> None:
    assert property_change.changed
    assert property_change.changed_modules == ("_internal.py",)
    assert any("date" in line for line in property_change.model_diff)


@pytest.mark.spec("CSAF-05-007")
def test_a_changed_disclosure_date_is_listed_as_a_read_field(
    property_change: draft_watch.DraftChange, pin: CsafPin
) -> None:
    paths = [a.field.path for a in property_change.fields]

    assert paths == ["vulnerabilities[].disclosure_date"]
    body = render_issue(property_change, pin, "a" * 40)
    assert "`vulnerabilities[].disclosure_date`" in body
    assert "review its mapping" in body
    assert "uv run csaf-models" in body


@pytest.mark.spec("CSAF-05-007")
def test_a_change_to_no_read_field_says_a_regeneration_is_enough(
    pin: CsafPin,
) -> None:
    body = render_issue(
        draft_watch.DraftChange(changed_modules=("_internal.py",)), pin
    )

    assert "regenerating the models is enough" in body


def test_every_read_field_resolves_in_the_pinned_schema(pin: CsafPin) -> None:
    pinned = SchemaSet.read(pin, PINNED_COPY_DIR)

    assert pinned.problems == ()
    for read in READ_FIELDS:
        located = pinned.locate(read.path)
        assert located is not None, read.path
        pinned.expand(*located)


def test_a_read_field_missing_from_the_pin_fails_loudly(
    upstream: Path, pin: CsafPin
) -> None:
    with pytest.raises(ValueError, match="no_such_field"):
        compare_schemas(
            pin,
            upstream,
            read_fields=[ReadField("document.no_such_field", ())],
            render=_never_render,
        )


def test_a_removed_read_field_is_reported(
    upstream: Path, pin: CsafPin
) -> None:
    _edit_root(
        upstream,
        pin,
        lambda schema: _vulnerability(schema).pop("disclosure_date"),
    )

    change = compare_schemas(
        pin, upstream, read_fields=[_DISCLOSURE, _TITLE], render=_no_models
    )

    assert [(a.field, a.how) for a in change.fields] == [
        (_DISCLOSURE, "is gone upstream")
    ]


@pytest.mark.spec("CSAF-05-005")
def test_an_unmapped_reference_is_reported_not_raised(
    upstream: Path, pin: CsafPin
) -> None:
    new_url = "https://www.first.org/cvss/cvss-v5.0.json"

    def cvss_v5(schema: Schema) -> None:
        metrics = _vulnerability(schema)["metrics"]["items"]
        metrics["properties"]["content"]["properties"]["cvss_v4"] = {
            "$ref": new_url
        }

    _edit_root(upstream, pin, cvss_v5)

    change = compare_schemas(
        pin, upstream, read_fields=[_DISCLOSURE], render=_never_render
    )

    assert change.changed
    assert any(new_url in problem for problem in change.problems)
    assert change.fields == ()


def test_a_read_field_behind_an_unmapped_reference_is_reported(
    upstream: Path, pin: CsafPin
) -> None:
    ssvc = ReadField("vulnerabilities[].metrics[].content.ssvc_v2", ())
    new_url = "https://certcc.github.io/SSVC/data/schema/v2/SelectionList_2_1_0.schema.json"

    def ssvc_bump(schema: Schema) -> None:
        metrics = _vulnerability(schema)["metrics"]["items"]
        metrics["properties"]["content"]["properties"]["ssvc_v2"] = {
            "$ref": new_url
        }

    _edit_root(upstream, pin, ssvc_bump)

    change = compare_schemas(
        pin, upstream, read_fields=[ssvc], render=_never_render
    )

    assert [a.field for a in change.fields] == [ssvc]
    assert new_url in change.fields[0].how


def test_a_pinned_file_gone_upstream_is_reported(
    upstream: Path, pin: CsafPin
) -> None:
    gone = "csaf_2.1/referenced_schema/first/cvss-v4.0.json"
    (upstream / gone).unlink()

    change = compare_schemas(
        pin, upstream, read_fields=[_TITLE], render=_never_render
    )

    assert any(gone in problem for problem in change.problems)


def test_a_pinned_file_that_is_not_json_upstream_is_reported(
    upstream: Path, pin: CsafPin
) -> None:
    (upstream / pin.root).write_text("{not json", encoding="utf-8")

    change = compare_schemas(
        pin, upstream, read_fields=[], render=_never_render
    )

    assert any("not JSON" in problem for problem in change.problems)


def test_a_new_unreferenced_upstream_schema_is_no_change(
    upstream: Path, pin: CsafPin
) -> None:
    _write(
        upstream, "csaf_2.1/json_schema/provider.json", '{"type": "object"}'
    )

    assert not compare_schemas(pin, upstream, render=_never_render).changed


def test_stripping_keeps_a_property_named_description() -> None:
    schema = {
        "description": "dropped",
        "$comment": "dropped",
        "properties": {"description": {"type": "string", "examples": ["x"]}},
        "items": [{"description": "dropped", "type": "integer"}],
        "enum": [{"description": "a value, kept"}],
    }

    assert strip_annotations(schema) == {
        "properties": {"description": {"type": "string"}},
        "items": [{"type": "integer"}],
        "enum": [{"description": "a value, kept"}],
    }


@pytest.mark.spec("CSAF-05-005")
def test_a_profile_text_change_is_reported(
    baseline: Path, tmp_path: Path
) -> None:
    head = _checkout(tmp_path / "head", _PROFILES + "\nA new rule.\n")

    lines, problem = compare_profiles(baseline, head)

    assert problem == ""
    assert "+A new rule." in lines


def test_trailing_whitespace_in_the_profiles_is_no_change(
    baseline: Path, tmp_path: Path
) -> None:
    head = _checkout(tmp_path / "head", _PROFILES.replace("\n", "  \r\n"))

    assert compare_profiles(baseline, head) == ([], "")


def test_profiles_gone_upstream_are_reported(
    baseline: Path, tmp_path: Path
) -> None:
    head = _checkout(tmp_path / "head")
    (head / PROFILES_FILE).unlink()

    assert "is gone upstream" in compare_profiles(baseline, head)[1]


def test_a_pinned_checkout_without_profiles_fails_the_run(
    baseline: Path, tmp_path: Path
) -> None:
    (baseline / PROFILES_FILE).unlink()

    with pytest.raises(FileNotFoundError):
        compare_profiles(baseline, _checkout(tmp_path / "head"))


@pytest.mark.spec("CSAF-05-005")
def test_mandatory_tests_added_and_removed_are_reported(
    baseline: Path, tmp_path: Path
) -> None:
    head = _checkout(
        tmp_path / "head",
        tests=_testcases(
            ("6.1.10", "mandatory"),
            ("6.1.9", "mandatory"),
            ("6.2.1", "informative"),
        ),
    )

    assert compare_tests(baseline, head) == (
        ["6.1.9", "6.1.10"],
        ["6.1.1"],
        "",
    )


def test_a_non_mandatory_test_change_is_no_change(
    baseline: Path, tmp_path: Path
) -> None:
    head = _checkout(
        tmp_path / "head", tests=_testcases(("6.1.1", "mandatory"))
    )

    assert compare_tests(baseline, head) == ([], [], "")


@pytest.mark.parametrize(
    ("text", "problem"),
    [(None, "is gone upstream"), ("{broken", "no longer reads upstream")],
)
def test_an_unreadable_upstream_test_list_is_reported(
    baseline: Path, tmp_path: Path, text: str | None, problem: str
) -> None:
    head = _checkout(tmp_path / "head", tests=text or _TESTS)
    if text is None:
        (head / TESTCASES_FILE).unlink()

    assert problem in compare_tests(baseline, head)[2]


def test_compare_gathers_every_kind_of_change(
    baseline: Path, upstream: Path, pin: CsafPin
) -> None:
    _write(upstream, PROFILES_FILE, _PROFILES + "More.\n")
    _write(upstream, TESTCASES_FILE, _testcases(("6.1.2", "mandatory")))
    (upstream / pin.root).unlink()

    change = compare(
        pin, baseline, upstream, read_fields=[], render=_never_render
    )

    body = render_issue(change, pin)
    assert change.problems and change.profiles_diff
    assert (change.tests_added, change.tests_removed) == (
        ("6.1.2",),
        ("6.1.1",),
    )
    for heading in (
        "Inputs the pin cannot follow",
        "Profile text",
        "Mandatory tests",
    ):
        assert f"## {heading}" in body


def test_main_exits_0_and_writes_nothing_without_a_change(
    baseline: Path, upstream: Path, tmp_path: Path
) -> None:
    report = tmp_path / "report.md"

    status = draft_watch.main(
        [
            "--baseline",
            str(baseline),
            "--upstream",
            str(upstream),
            "--report",
            str(report),
        ]
    )

    assert status == 0
    assert not report.exists()


def test_main_exits_3_and_writes_the_issue_body_on_a_change(
    baseline: Path, upstream: Path, tmp_path: Path
) -> None:
    _write(upstream, PROFILES_FILE, _PROFILES + "More.\n")
    report = tmp_path / "report.md"

    status = draft_watch.main(
        [
            "--baseline",
            str(baseline),
            "--upstream",
            str(upstream),
            "--upstream-commit",
            "b" * 40,
            "--report",
            str(report),
        ]
    )

    assert status == EXIT_CHANGED
    body = report.read_text(encoding="utf-8")
    assert "b" * 40 in body
    assert "## What to do" in body


def test_a_relative_reference_to_an_unlisted_file_is_reported(
    upstream: Path, pin: CsafPin
) -> None:
    def new_file(schema: Schema) -> None:
        schema["$defs"]["added_t"] = {"$ref": "aggregator.json"}

    _edit_root(upstream, pin, new_file)

    change = compare_schemas(
        pin, upstream, read_fields=[], render=_never_render
    )

    assert any("aggregator.json" in p for p in change.problems)


def test_read_fields_cannot_be_read_when_the_root_is_gone(
    upstream: Path, pin: CsafPin
) -> None:
    (upstream / pin.root).unlink()

    change = compare_schemas(
        pin, upstream, read_fields=[_TITLE], render=_never_render
    )

    assert [a.field for a in change.fields] == [_TITLE]
    assert "cannot be read upstream" in change.fields[0].how


def test_a_long_diff_is_cut_short_in_the_issue(pin: CsafPin) -> None:
    lines = tuple(f"+line {n}" for n in range(500))

    body = render_issue(
        draft_watch.DraftChange(changed_modules=("x.py",), model_diff=lines),
        pin,
    )

    assert "+line 199" in body
    assert "+line 200" not in body
    assert "300 more lines" in body


@pytest.mark.parametrize(
    ("fragment", "found"),
    [("/oneOf/1/type", "integer"), ("/oneOf/2", None), ("anchor", None)],
)
def test_a_json_pointer_resolves_or_is_unresolved(
    pin: CsafPin, fragment: str, found: str | None
) -> None:
    schemas = SchemaSet(
        pin=pin,
        files={pin.root: {"oneOf": [{"type": "string"}, {"type": "integer"}]}},
    )

    if found is None:
        with pytest.raises(draft_watch.UnresolvedReferenceError):
            schemas.node(pin.root, fragment)
    else:
        assert schemas.node(pin.root, fragment) == found
