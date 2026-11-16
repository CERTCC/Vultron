"""The committed-data check (VSD-02-001 to VSD-02-005, #5961)."""

import copy
import json
from collections.abc import Mapping
from pathlib import Path

import pytest

from vultron.metadata.base import repo_root
from vultron.metadata.generated_files import serialize_json, stale_paths
from vultron.metadata.git_runner import GitError
from vultron.metadata.vince_data import check as check_module
from vultron.metadata.vince_data.check import (
    check,
    file_faults,
    generate,
    tracked_json_files,
)
from vultron.metadata.vince_data.generator import (
    SYNTHETIC_CASES,
    generated_fixtures,
)
from vultron.metadata.vince_data.marker import (
    CLEARED_CASES_PATH,
    FIXTURE_DIR,
    GENERATOR,
    SANITIZER,
    ProducerVerifier,
    marker_for,
)

_STEM = "999901-active-embargoed"
_GENERATED_PATH = f"{FIXTURE_DIR}/{_STEM}.json"
_CLEARANCE = "https://github.com/CERTCC/Vultron/issues/1#issuecomment-2"


def _reads(stem: str = _STEM) -> dict[str, object]:
    return copy.deepcopy(dict(SYNTHETIC_CASES[stem]))


def _bundle(case_id: str, *, producer: str | None = None) -> str:
    reads = _reads()
    reads["case"]["vuid"] = case_id  # type: ignore[index]
    for vul in reads["vuls"]:  # type: ignore[attr-defined]
        vul["name"] = vul["name"].replace("999901", case_id)
    for status in reads["vendors/vuls"]:  # type: ignore[attr-defined]
        status["vulnerability"] = status["vulnerability"].replace(
            "999901", case_id
        )
    document: dict[str, object] = {"reads": reads}
    if producer is not None:
        document = {**marker_for(producer), **document}
    return serialize_json(document)


def _faults(
    path: str,
    text: str,
    cleared: frozenset[str] = frozenset(),
    verifiers: Mapping[str, ProducerVerifier | None] | None = None,
) -> list[str]:
    if verifiers is None:
        return file_faults(path, text, cleared)
    return file_faults(path, text, cleared, verifiers)


# AC-1 ------------------------------------------------------------------


@pytest.mark.spec("VSD-02-005")
def test_the_committed_fixtures_are_what_the_generator_writes() -> None:
    root = repo_root()
    assert list(stale_paths(root, generated_fixtures())) == []


def test_every_fixture_is_in_the_fixture_directory_and_marked() -> None:
    fixtures = generated_fixtures()
    assert len(fixtures) >= 3
    for path, text in fixtures.items():
        assert path.startswith(f"{FIXTURE_DIR}/")
        document = json.loads(text)
        assert document["synthetic"] == {"producer": GENERATOR}


def test_generate_writes_only_what_is_stale(tmp_path: Path) -> None:
    assert sorted(generate(tmp_path)) == sorted(generated_fixtures())
    assert generate(tmp_path) == []


# AC-2 ------------------------------------------------------------------


@pytest.mark.spec("VSD-02-001")
def test_a_vince_shaped_file_outside_the_fixture_directory_is_refused() -> (
    None
):
    text = json.dumps(_reads()["posts"])
    [fault] = _faults("docs/recorded.json", text)
    assert "only in test/fixtures/vince/" in fault
    assert "post object at $[0]" in fault


@pytest.mark.spec("VSD-02-001")
def test_a_marked_file_outside_the_fixture_directory_is_refused() -> None:
    text = generated_fixtures()[_GENERATED_PATH]
    [fault] = _faults("test/elsewhere/case.json", text)
    assert "only in test/fixtures/vince/" in fault


@pytest.mark.spec("VSD-02-001")
def test_an_unmarked_uncleared_file_in_the_directory_is_refused() -> None:
    [fault] = _faults(f"{FIXTURE_DIR}/recorded.json", _bundle("123456"))
    assert "no synthetic marker" in fault
    assert "case 123456 is not on the cleared-case list" in fault


def test_an_unmarked_list_naming_no_case_id_is_refused() -> None:
    text = json.dumps(_reads()["posts"])
    [fault] = _faults(f"{FIXTURE_DIR}/posts.json", text, frozenset({"999901"}))
    assert "names no case id" in fault
    assert "inside a bundle whose `reads.case.vuid` names it" in fault


def test_a_vul_list_names_its_case_by_the_vul_names() -> None:
    text = json.dumps(_reads()["vuls"])
    path = f"{FIXTURE_DIR}/vuls.json"
    assert _faults(path, text, frozenset({"999901"})) == []
    [fault] = _faults(path, text, frozenset({"123456"}))
    assert "case 999901 is not on the cleared-case list" in fault


@pytest.mark.spec("VSD-02-002")
def test_a_cleared_bundle_carrying_another_case_is_refused() -> None:
    reads = _reads()
    reads["case"]["vuid"] = "111"  # type: ignore[index]
    other = copy.deepcopy(reads["case"])
    other["vuid"] = "222"  # type: ignore[index]
    text = json.dumps({"reads": reads, "extra": [other]})
    path = f"{FIXTURE_DIR}/recorded.json"
    [fault] = _faults(path, text, frozenset({"111"}))
    assert "case 222, 999901 is not on the cleared-case list" in fault
    assert _faults(path, text, frozenset({"111", "222", "999901"})) == []


def test_json_that_is_not_vince_shaped_passes_anywhere() -> None:
    assert _faults("docs/example.json", '{"type": "Note"}') == []


def test_a_file_that_does_not_parse_is_refused() -> None:
    [fault] = _faults("docs/broken.json", "{oops")
    assert "cannot be ruled out" in fault


def test_a_vince_response_in_an_uppercase_or_har_file_is_found() -> None:
    body = json.dumps(_reads()["case"])
    har = json.dumps(
        {"log": {"entries": [{"response": {"content": {"text": body}}}]}}
    )
    [fault] = _faults("docs/session.har", har)
    assert (
        "case object at $.log.entries[0].response.content.text<json>" in fault
    )
    assert _faults("docs/RECORDED.JSON", body) != []


def test_a_line_file_keeps_unicode_line_separators_inside_strings() -> None:
    line = json.dumps({"a": "one\u2028two"}, ensure_ascii=False)
    assert _faults("logs/run.jsonl", f"{line}\n") == []


def test_json_nested_too_deeply_is_refused_not_raised() -> None:
    [fault] = _faults("docs/deep.json", "[" * 100_000 + "]" * 100_000)
    assert "nested too deeply" in fault


def test_a_file_that_is_not_utf8_is_refused(tmp_path: Path) -> None:
    root = _tree(tmp_path, "cleared: []\n")
    (root / "bad.json").write_bytes(b'{"a": "\xff"}')
    faults = check(root, ["bad.json", *generated_fixtures()])
    assert faults == [
        "bad.json: cannot be read as JSON, so it cannot be ruled out as VINCE "
        "data: not valid UTF-8: 'utf-8' codec can't decode byte 0xff in "
        "position 7: invalid start byte"
    ]


def test_each_vince_line_of_a_line_file_is_refused() -> None:
    line = json.dumps(_reads()["case"])
    faults = _faults("logs/run.jsonl", f"{line}\n{{}}\n{line}\n")
    assert len(faults) == 2


# AC-4 ------------------------------------------------------------------


@pytest.mark.spec("VSD-02-002")
def test_a_cleared_case_passes_without_the_marker() -> None:
    text = _bundle("123456")
    path = f"{FIXTURE_DIR}/recorded.json"
    assert _faults(path, text, frozenset({"123456"})) == []


@pytest.mark.spec("VSD-02-002")
def test_a_clearance_clears_its_own_case_and_no_other() -> None:
    path = f"{FIXTURE_DIR}/recorded.json"
    assert _faults(path, _bundle("654321"), frozenset({"123456"})) != []


def test_a_cleared_raw_case_response_passes() -> None:
    case = _reads()["case"]
    case["vuid"] = "123456"  # type: ignore[index]
    path = f"{FIXTURE_DIR}/case.json"
    assert _faults(path, json.dumps(case), frozenset({"123456"})) == []


def test_a_cleared_file_outside_the_directory_is_still_refused() -> None:
    faults = _faults("docs/recorded.json", _bundle("1"), frozenset({"1"}))
    assert faults != []


# AC-5 ------------------------------------------------------------------


@pytest.mark.spec("VSD-02-005")
def test_a_file_the_generator_wrote_passes() -> None:
    text = generated_fixtures()[_GENERATED_PATH]
    assert _faults(_GENERATED_PATH, text) == []


@pytest.mark.spec("VSD-02-005")
def test_an_edited_generator_file_is_refused() -> None:
    text = generated_fixtures()[_GENERATED_PATH].replace("Alpha", "Real Co")
    [fault] = _faults(_GENERATED_PATH, text)
    assert "differs from what the generator writes" in fault


@pytest.mark.spec("VSD-02-005")
def test_a_generator_marker_on_a_file_it_did_not_write_is_refused() -> None:
    path = f"{FIXTURE_DIR}/hand-made.json"
    [fault] = _faults(path, _bundle("123456", producer=GENERATOR))
    assert "generator writes no file at this path" in fault


@pytest.mark.spec("VSD-02-005")
def test_a_sanitizer_marker_is_refused_until_the_sanitizer_vouches() -> None:
    path = f"{FIXTURE_DIR}/sanitized/one.json"
    [fault] = _faults(path, _bundle("123456", producer=SANITIZER))
    assert "cannot vouch for a file yet" in fault


@pytest.mark.spec("VSD-02-005")
def test_a_registered_sanitizer_verifier_decides_its_files() -> None:
    path = f"{FIXTURE_DIR}/sanitized/one.json"
    text = _bundle("123456", producer=SANITIZER)
    seen: list[tuple[str, str]] = []

    def vouch(p: str, t: str) -> str | None:
        seen.append((p, t))
        return None

    def refuse(p: str, t: str) -> str | None:
        return "it holds a source string"

    assert _faults(path, text, verifiers={SANITIZER: vouch}) == []
    assert seen == [(path, text)]
    [fault] = _faults(path, text, verifiers={SANITIZER: refuse})
    assert "it holds a source string" in fault


@pytest.mark.spec("VSD-02-005")
def test_a_marker_naming_another_tool_is_refused() -> None:
    path = f"{FIXTURE_DIR}/one.json"
    [fault] = _faults(path, _bundle("1", producer="me, by hand"))
    assert "not a tool that may mark" in fault


@pytest.mark.spec("VSD-02-005")
@pytest.mark.parametrize(
    "marker",
    [True, "generator", {}, {"producer": ""}, {"producer": "x", "y": 1}],
)
def test_a_marker_that_names_no_single_tool_is_refused(marker: object) -> None:
    document = {"synthetic": marker, "reads": _reads()}
    [fault] = _faults(f"{FIXTURE_DIR}/one.json", json.dumps(document))
    assert "malformed synthetic marker" in fault


def test_the_sanitizer_name_is_reserved() -> None:
    assert check_module.PRODUCER_VERIFIERS[SANITIZER] is None


# The cleared-case list (AC-4, VSD-02-002, VSD-02-003) ------------------


def _tree(tmp_path: Path, cleared: str) -> Path:
    generate(tmp_path)
    (tmp_path / CLEARED_CASES_PATH).write_text(cleared, encoding="utf-8")
    return tmp_path


def test_a_well_formed_list_clears_its_case(tmp_path: Path) -> None:
    root = _tree(
        tmp_path,
        f'cleared:\n  - case_id: "123456"\n    clearance: {_CLEARANCE}\n',
    )
    recorded = f"{FIXTURE_DIR}/recorded.json"
    (root / recorded).write_text(_bundle("123456"), encoding="utf-8")
    assert check(root, [recorded, *generated_fixtures()]) == []


@pytest.mark.spec("VSD-02-003")
@pytest.mark.parametrize(
    ("entry", "names"),
    [
        (f"clearance: {_CLEARANCE}", "case_id"),
        ('case_id: "123456"', "clearance"),
        (f'case_id: ""\n    clearance: {_CLEARANCE}', "case_id"),
        ('case_id: "123456"\n    clearance: ""', "clearance"),
    ],
)
def test_an_entry_missing_its_case_id_or_link_is_refused(
    tmp_path: Path, entry: str, names: str
) -> None:
    root = _tree(tmp_path, f"cleared:\n  - {entry}\n")
    [fault] = check(root, list(generated_fixtures()))
    assert "cleared-case list refused (VSD-02-003)" in fault
    assert names in fault


@pytest.mark.spec("VSD-02-002")
@pytest.mark.parametrize(
    "case_id", ['["123456", "654321"]', '"123456, 654321"', '"VU#1 VU#2"']
)
def test_an_entry_naming_more_than_one_case_id_is_refused(
    tmp_path: Path, case_id: str
) -> None:
    root = _tree(
        tmp_path,
        f"cleared:\n  - case_id: {case_id}\n    clearance: {_CLEARANCE}\n",
    )
    [fault] = check(root, list(generated_fixtures()))
    assert "exactly one VINCE case id" in fault


@pytest.mark.parametrize(
    "link",
    [
        "https://github.com/CERTCC/Vultron/issues/1",
        "https://example.com/issues/1#issuecomment-2",
        "see the thread",
    ],
)
def test_a_link_that_is_not_a_comment_here_is_refused(
    tmp_path: Path, link: str
) -> None:
    root = _tree(
        tmp_path, f'cleared:\n  - case_id: "1"\n    clearance: "{link}"\n'
    )
    [fault] = check(root, list(generated_fixtures()))
    assert "clearance comment" in fault


def test_a_case_cleared_twice_is_refused(tmp_path: Path) -> None:
    entry = f'  - case_id: "1"\n    clearance: {_CLEARANCE}\n'
    root = _tree(tmp_path, f"cleared:\n{entry}{entry}")
    [fault] = check(root, list(generated_fixtures()))
    assert "listed more than once: 1" in fault


def test_a_missing_list_is_refused(tmp_path: Path) -> None:
    generate(tmp_path)
    [fault] = check(tmp_path, list(generated_fixtures()))
    assert "cleared-case list is missing" in fault


def test_a_faulty_list_hides_no_other_fault(tmp_path: Path) -> None:
    root = _tree(tmp_path, "cleared: [{case_id: '1'}]\n")
    (root / "recorded.json").write_text(
        json.dumps(_reads()["case"]), encoding="utf-8"
    )
    faults = check(root, ["recorded.json", *generated_fixtures()])
    assert len(faults) == 2
    assert "cleared-case list refused" in faults[0]
    assert faults[1].startswith("recorded.json: holds")


# AC-3 ------------------------------------------------------------------


@pytest.mark.spec("VSD-02-001")
def test_an_empty_target_set_fails(tmp_path: Path) -> None:
    root = _tree(tmp_path, "cleared: []\n")
    [fault] = check(root, [])
    assert "empty target set" in fault


def test_a_stale_generator_fixture_fails(tmp_path: Path) -> None:
    root = _tree(tmp_path, "cleared: []\n")
    (root / _GENERATED_PATH).unlink()
    faults = check(root, ["other.json"])
    assert any("missing or stale" in fault for fault in faults)


@pytest.mark.spec("VSD-02-001")
def test_the_committed_tree_passes() -> None:
    root = repo_root()
    targets = tracked_json_files(root)
    assert set(generated_fixtures()) <= set(targets)
    assert check(root, targets) == []


def test_main_check_reports_and_exits(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    root = _tree(tmp_path, "cleared: []\n")
    (root / "docs").mkdir()
    (root / "docs" / "recorded.json").write_text(
        json.dumps(_reads()["case"]), encoding="utf-8"
    )
    monkeypatch.setattr(check_module, "repo_root", lambda: root)
    monkeypatch.setattr(
        check_module,
        "tracked_json_files",
        lambda r: ["docs/recorded.json", *generated_fixtures()],
    )
    assert check_module.main(["check"]) == 1
    assert "docs/recorded.json" in capsys.readouterr().err
    (root / "docs" / "recorded.json").unlink()
    assert check_module.main(["check"]) == 0


def test_main_fails_when_git_cannot_list_the_tree(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    def no_git(root: Path) -> list[str]:
        raise GitError("cannot run git: not found")

    monkeypatch.setattr(check_module, "tracked_json_files", no_git)
    assert check_module.main(["check"]) == 1
    assert "cannot run git" in capsys.readouterr().err


def test_main_generate_writes_the_fixtures(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    monkeypatch.setattr(check_module, "repo_root", lambda: tmp_path)
    assert check_module.main(["generate"]) == 0
    assert _GENERATED_PATH in capsys.readouterr().out
