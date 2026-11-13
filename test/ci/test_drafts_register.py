"""The drafts register, its loader, its fragments and its release check.

Requirements: DOCBW-08-001 to DOCBW-08-008 (ADR-0188). The register is
``docs/reference/vultron-spec/drafts.yaml``; the loader, the fragment
generators and the release-tag check are
:mod:`vultron.metadata.docs.drafts_register`.
"""

from __future__ import annotations

import json
import re
from datetime import UTC, datetime
from pathlib import Path
from types import SimpleNamespace

import markdown  # type: ignore[import-untyped]  # Python-Markdown ships no stubs
import pytest
import yaml

from test.ci._scratch_git import git, isolate_git_config, scratch_clone
from test.ci._workflows import (
    BUILD_SITE_ACTION,
    WORKFLOWS_DIR,
    index_of,
    live_text,
    load_workflow,
    neutering,
    steps,
)
from vultron.metadata.base import repo_root
from vultron.metadata.docs import drafts_register as dr, site_sync
from vultron.metadata.file_loading import MetadataLoadError, MetadataLoadErrors
from vultron.metadata.generated_files import stale_paths, write_generated

SHOWN = "drafts.yaml"


def _register(*entries: str) -> str:
    """Register text with one ``- ...`` entry per argument, as written."""
    return "drafts:\n" + "".join(entries)


def _entry(
    version: str,
    status: str = "released",
    date: str = "2026-11-06",
    release: str | None = None,
) -> str:
    text = f"  - version: {version}\n    status: {status}\n    date: {date}\n"
    if release is not None:
        text += f"    release: {release}\n"
    return text


def _released(n: int, tag: str | None = None) -> str:
    return _entry(f"draft-{n}", "released", release=tag or f"v2026.{n}.0")


def _open(n: int) -> str:
    return _entry(f"draft-{n}", "unreleased")


def _faults(text: str) -> list[MetadataLoadError]:
    """The faults parsing *text* raises, each as structured data."""
    with pytest.raises((MetadataLoadError, MetadataLoadErrors)) as caught:
        dr.parse_register(text, SHOWN)
    exc = caught.value
    if isinstance(exc, MetadataLoadErrors):
        return list(exc.failures)
    assert isinstance(exc, MetadataLoadError)
    return [exc]


# --- DOCBW-08-001: the committed register and each entry's fields ----------


@pytest.mark.spec("DOCBW-08-001")
def test_the_committed_register_holds_every_draft_with_its_fields():
    register = dr.load_register(repo_root())
    assert register.drafts, "the register holds no draft"
    numbers = [entry.number for entry in register.drafts]
    assert numbers == list(range(1, len(numbers) + 1))
    for entry in register.drafts:
        assert re.fullmatch(r"draft-[1-9]\d*", entry.version)
        assert entry.date.isoformat()
        if isinstance(entry, dr.ReleasedDraft):
            assert entry.release.startswith("v")


@pytest.mark.spec("DOCBW-08-001")
@pytest.mark.parametrize(
    ("text", "expected"),
    [
        ("drafts:\n  - status: unreleased\n    date: 2026-11-06\n", "version"),
        ("drafts:\n  - version: draft-1\n    date: 2026-11-06\n", "status"),
        ("drafts:\n  - version: draft-1\n    status: unreleased\n", "date"),
        (_register(_entry("draft-1", "released")), "release"),
        (
            _register(_entry("draft-1", "unreleased", release="v2026.11.0")),
            "release",
        ),
        (_register(_entry("draft-1", "frozen")), "status"),
        (_register(_entry("draft-01", "unreleased")), "version"),
        (_register(_entry("draft-0", "unreleased")), "version"),
        (_register(_entry("Draft-1", "unreleased")), "version"),
        (_register(_entry("draft-1", date="2026-11-6")), "date"),
        (_register(_entry("draft-1", date="20261106")), "date"),
        (_register(_entry("draft-1", date="2026-11-06T10:00:00Z")), "date"),
        (_register(_entry("draft-1", release="2026.11.0")), "release"),
        (_register(_entry("draft-1", release="v2026.13.0")), "release"),
        (_register(_open(1) + "    notes: hi\n"), "notes"),
    ],
    ids=[
        "no-version",
        "no-status",
        "no-date",
        "released-without-tag",
        "unreleased-with-tag",
        "unknown-status",
        "leading-zero-version",
        "draft-zero",
        "capitalised-version",
        "short-date",
        "number-date",
        "timestamp-date",
        "tag-without-v",
        "tag-month-13",
        "unknown-field",
    ],
)
def test_an_entry_missing_or_breaking_a_field_is_refused_at_its_entry(
    text: str, expected: str
):
    (fault,) = _faults(text)
    assert fault.path == SHOWN
    assert fault.line == 2 and fault.column is not None, fault
    assert expected in fault.detail


@pytest.mark.spec("DOCBW-08-001")
@pytest.mark.parametrize(
    "text",
    ["drafts: []\n", "drafts:\n", "- version: draft-1\n", "{}\n"],
    ids=["empty-list", "null", "top-level-list", "no-drafts-key"],
)
def test_a_register_with_no_entries_is_refused(text: str):
    (fault,) = _faults(text)
    assert fault.path == SHOWN


@pytest.mark.spec("DOCBW-08-001")
def test_a_yaml_fault_is_named_at_its_position():
    (fault,) = _faults("drafts:\n  - version: draft-1\n   status: [\n")
    assert fault.path == SHOWN
    assert fault.line is not None and fault.column is not None
    assert "YAML parse error" in fault.detail


@pytest.mark.spec("DOCBW-08-001")
@pytest.mark.parametrize("value", ["2026-13-45", "'2026-13-45'"])
def test_an_impossible_date_is_refused_at_the_register(value: str):
    (fault,) = _faults(_register(_entry("draft-1", "unreleased", date=value)))
    assert fault.path == SHOWN
    assert "month" in fault.detail


@pytest.mark.spec("DOCBW-08-001")
def test_a_quoted_date_is_admitted():
    register = dr.parse_register(
        _register(_entry("draft-1", "unreleased", date="'2026-11-06'")), SHOWN
    )
    assert register.drafts[0].date.isoformat() == "2026-11-06"


# --- DOCBW-08-002: faults between entries -----------------------------------


@pytest.mark.spec("DOCBW-08-002")
@pytest.mark.parametrize(
    ("text", "line", "words"),
    [
        (_register(_released(1), _released(1, "v2026.2.0")), 6, "duplicate"),
        (_register(_released(1), _open(3)), 6, "draft-2 missing"),
        (_register(_released(2), _open(3)), 2, "draft-1 missing"),
        (_register(_open(1), _open(2)), 2, "highest-numbered"),
        (_register(_released(1), _released(2, "v2026.1.0")), 6, "one release"),
    ],
    ids=[
        "duplicate-version",
        "gap",
        "no-draft-1",
        "open-not-highest",
        "same-tag",
    ],
)
def test_a_conflict_between_entries_is_named_at_the_failing_entry(
    text: str, line: int, words: str
):
    faults = _faults(text)
    matching = [f for f in faults if words in f.detail]
    assert matching, [f.detail for f in faults]
    assert all(f.path == SHOWN for f in faults)
    assert matching[0].line == line
    assert matching[0].column == 5
    assert str(matching[0]).startswith(f"{SHOWN}:{line}:5 — ")


@pytest.mark.spec("DOCBW-08-002")
def test_two_unreleased_entries_are_refused():
    faults = _faults(_register(_released(1), _open(2), _open(2)))
    assert any("at most one draft is unreleased" in f.detail for f in faults)


@pytest.mark.spec("DOCBW-08-002")
def test_every_conflict_is_reported_not_only_the_first():
    faults = _faults(
        _register(_released(1), _released(1, "v2026.1.0"), _open(2), _open(4))
    )
    details = " | ".join(f.detail for f in faults)
    for words in (
        "duplicate",
        "one release",
        "at most one",
        "draft-3 missing",
    ):
        assert words in details, details


@pytest.mark.spec("DOCBW-08-002")
def test_entries_in_any_order_load_ordered_by_number():
    register = dr.parse_register(
        _register(_open(3), _released(1), _released(2)), SHOWN
    )
    assert [e.version for e in register.drafts] == [
        "draft-1",
        "draft-2",
        "draft-3",
    ]


# --- The reading API (AC-3) -------------------------------------------------


@pytest.mark.spec("DOCBW-08-001")
def test_the_register_names_the_current_draft_and_each_release():
    register = dr.parse_register(
        _register(
            _released(1, "v2026.11.0"), _released(2, "v2027.2.0"), _open(3)
        ),
        SHOWN,
    )
    assert register.current is not None
    assert register.current.version == "draft-3"
    assert [(e.version, e.release) for e in register.released] == [
        ("draft-1", "v2026.11.0"),
        ("draft-2", "v2027.2.0"),
    ]
    assert register.newest_released == register.released[-1]
    assert register.released_by("v2027.2.0") == register.released[-1]
    assert register.released_by("v2027.3.0") is None
    assert register.entry("draft-9") is None
    assert register.as_json() == {
        "register": SHOWN,
        "current": {"version": "draft-3", "date": "2026-11-06"},
        "released": [
            {
                "version": "draft-1",
                "date": "2026-11-06",
                "release": "v2026.11.0",
            },
            {
                "version": "draft-2",
                "date": "2026-11-06",
                "release": "v2027.2.0",
            },
        ],
    }


@pytest.mark.spec("DOCBW-08-001")
def test_an_all_released_register_has_no_current_draft():
    register = dr.parse_register(_register(_released(1)), SHOWN)
    assert register.current is None
    assert register.as_json()["current"] is None


@pytest.mark.spec("DOCBW-08-001")
def test_show_prints_the_committed_register_as_json(capsys):
    dr.main(["show"])
    printed = json.loads(capsys.readouterr().out)
    assert printed == dr.load_register(repo_root()).as_json()


# --- DOCBW-08-004 to DOCBW-08-008: the generated fragments -----------------


@pytest.mark.spec("DOCBW-08-004")
def test_the_fragments_carry_each_entry_of_the_register():
    register = dr.parse_register(
        _register(
            _released(1, "v2026.11.0"),
            _entry("draft-2", "unreleased", date="2027-01-04"),
        ),
        SHOWN,
    )
    fragments = dr.desired_fragments(register)
    assert set(fragments) == {
        dr.STATUS_BOX_PATH,
        dr.fragment_path("draft-1"),
        dr.fragment_path("draft-2"),
    }
    one = fragments[dr.fragment_path("draft-1")]
    assert "| Version | `draft-1` |" in one
    assert "| Status | Released in `v2026.11.0` |" in one
    assert "| Date | 2026-11-06 |" in one
    two = fragments[dr.fragment_path("draft-2")]
    assert "| Version | `draft-2` |" in two
    assert "| Opened | 2027-01-04 |" in two
    assert "Frozen copy" not in two
    box = fragments[dr.STATUS_BOX_PATH]
    assert "| Version | `draft-2` |" in box
    assert "`draft-1`, which release `v2026.11.0` carries" in box


@pytest.mark.spec("DOCBW-08-040")
def test_the_current_draft_is_dated_by_the_publish_that_builds_the_page():
    """Its last-updated date is a slot the build fills, in table and citation."""
    register = dr.parse_register(
        _register(
            _released(1), _entry("draft-2", "unreleased", date="2027-01-04")
        ),
        SHOWN,
    )
    fragments = dr.desired_fragments(register)
    slot = dr.PUBLISH_DATE_SLOT
    for path in (dr.STATUS_BOX_PATH, dr.fragment_path("draft-2")):
        assert f"| Last updated | {slot} |" in fragments[path]
        assert "| Opened | 2027-01-04 |" in fragments[path]
        assert "| Date |" not in fragments[path]
    box = fragments[dr.STATUS_BOX_PATH]
    assert f"Vultron Protocol Specification, `draft-2`, {slot}." in box
    assert "each publish stamps it" in box
    assert slot not in fragments[dr.fragment_path("draft-1")]


@pytest.mark.spec("DOCBW-08-001", "DOCBW-08-040")
def test_a_released_draft_keeps_the_date_of_the_publish_that_froze_it():
    register = dr.parse_register(
        _register(_released(1, "v2026.11.0"), _released(2, "v2027.2.0")), SHOWN
    )
    fragments = dr.desired_fragments(register)
    for text in fragments.values():
        assert dr.PUBLISH_DATE_SLOT not in text
        assert "| Date | 2026-11-06 |" in text
    assert (
        "the publish of the site that froze this draft"
        in (fragments[dr.STATUS_BOX_PATH])
    )


@pytest.mark.spec("DOCBW-08-040")
def test_the_slot_reaches_the_rendered_status_box_as_written():
    """Markdown passes the raw-HTML slot through, inside the admonition table."""
    box = dr.render_status_box(dr.parse_register(_register(_open(1)), SHOWN))
    html = markdown.markdown(box, extensions=["admonition", "tables"])
    assert html.count(dr.PUBLISH_DATE_SLOT) == 2
    assert "<td>" + dr.PUBLISH_DATE_SLOT + "</td>" in html


@pytest.mark.spec("DOCBW-08-006")
def test_an_open_draft_labels_the_specification_current_draft():
    box = dr.render_status_box(dr.parse_register(_register(_open(1)), SHOWN))
    assert '!!! note "Current draft (work in progress): Draft 1"' in box
    assert dr.CURRENT_DRAFT_LABEL in box


@pytest.mark.spec("DOCBW-08-007")
def test_an_all_released_register_names_the_newest_draft_and_its_tag():
    box = dr.render_status_box(
        dr.parse_register(
            _register(_released(1, "v2026.11.0"), _released(2, "v2027.2.0")),
            SHOWN,
        )
    )
    assert '!!! note "Status: Draft 2, released in `v2027.2.0`"' in box
    assert "| Version | `draft-2` |" in box
    assert "| Status | Released in `v2027.2.0` |" in box
    assert "`draft-2`, 2026-11-06, `v2027.2.0`." in box
    assert "draft-1" not in box
    assert "Current draft" not in box
    assert "work in progress" not in box


@pytest.mark.spec("DOCBW-08-008")
def test_each_released_drafts_table_links_its_frozen_copy():
    register = dr.parse_register(
        _register(
            _released(1, "v2026.11.0"), _released(2, "v2027.2.0"), _open(3)
        ),
        SHOWN,
    )
    fragments = dr.desired_fragments(register)
    for version in ("draft-1", "draft-2"):
        assert (
            f"| Frozen copy | [`spec/{version}/`](../../../spec/{version}/) |"
            in fragments[dr.fragment_path(version)]
        )
    assert "Frozen copy" not in fragments[dr.fragment_path("draft-3")]


@pytest.mark.spec("DOCBW-08-008")
def test_the_frozen_copy_link_resolves_to_spec_draft_n_from_the_revision_log():
    """The built Revision Log is ``reference/vultron-spec/revision-log/``."""
    page = "reference/vultron-spec/revision-log/"
    resolved = Path("/site", page, dr.frozen_copy_url("draft-7")).resolve()
    assert resolved == Path("/site/spec/draft-7")


# --- DOCBW-08-005: the drift check and its hook -----------------------------


def _write_fragments(root: Path, text: str) -> dr.DraftsRegister:
    (root / dr.REGISTER_PATH).parent.mkdir(parents=True)
    (root / dr.REGISTER_PATH).write_text(text, encoding="utf-8")
    register = dr.load_register(root)
    for path, body in dr.desired_fragments(register).items():
        write_generated(root / path, body)
    return register


@pytest.mark.spec("DOCBW-08-005")
def test_a_register_edit_without_regeneration_leaves_the_fragments_stale(
    tmp_path,
):
    _write_fragments(tmp_path, _register(_open(1)))
    edited = _register(_released(1, "v2026.11.0"))
    (tmp_path / dr.REGISTER_PATH).write_text(edited, encoding="utf-8")
    desired = dr.desired_fragments(dr.load_register(tmp_path))
    assert sorted(stale_paths(tmp_path, desired)) == sorted(
        [dr.STATUS_BOX_PATH, dr.fragment_path("draft-1")]
    )


@pytest.mark.spec("DOCBW-08-005")
def test_a_regenerated_tree_is_not_stale(tmp_path):
    register = _write_fragments(tmp_path, _register(_released(1), _open(2)))
    assert list(stale_paths(tmp_path, dr.desired_fragments(register))) == []


@pytest.mark.spec("DOCBW-08-005")
def test_docs_site_generates_the_fragments_and_the_hook_watches_them():
    """``docs-site --check`` compares the fragments; its hook fires on each input."""
    config = yaml.safe_load(
        (repo_root() / ".pre-commit-config.yaml").read_text(encoding="utf-8")
    )
    (hook,) = [
        h
        for repo in config["repos"]
        for h in repo.get("hooks", [])
        if h.get("id") == "docs-site-sync"
    ]
    assert hook["entry"] == "uv run docs-site --check"
    files = re.compile(hook["files"])
    for path in (
        dr.REGISTER_PATH,
        dr.STATUS_BOX_PATH,
        dr.fragment_path("draft-1"),
        dr.REVISION_LOG_PATH,
        "vultron/metadata/docs/drafts_register.py",
    ):
        assert files.search(path), path


@pytest.mark.spec("DOCBW-08-005")
def test_a_table_of_a_draft_the_register_lacks_is_a_committed_fragment(
    tmp_path,
):
    """``docs-site --write`` deletes it: it is listed beside the boxes."""
    stray = tmp_path / dr.fragment_path("draft-9")
    write_generated(stray, "old\n")
    assert dr.fragment_path("draft-9") in site_sync._committed_fragments(
        tmp_path
    )


@pytest.mark.spec("DOCBW-08-004")
def test_the_committed_fragments_match_the_committed_register():
    root = repo_root()
    desired = dr.desired_fragments(dr.load_register(root))
    assert list(stale_paths(root, desired)) == [], (
        "run 'uv run docs-site --write' and commit the result"
    )
    assert dr.revision_log_faults(root, dr.load_register(root)) == []


# --- The Revision Log's include lines ---------------------------------------


def _revision_log(root: Path, *versions: str, raw: str = "") -> None:
    body = "".join(
        f"## Draft {v.removeprefix('draft-')}\n\n{dr.include_line(v)}\n\n"
        for v in versions
    )
    write_generated(root / dr.REVISION_LOG_PATH, f"# Log\n\n{body}{raw}")


_TWO = _register(_released(1), _open(2))


@pytest.mark.spec("DOCBW-08-008")
def test_a_revision_log_including_each_table_newest_first_passes(tmp_path):
    register = dr.parse_register(_TWO, SHOWN)
    _revision_log(tmp_path, "draft-2", "draft-1")
    assert dr.revision_log_faults(tmp_path, register) == []


@pytest.mark.spec("DOCBW-08-008")
@pytest.mark.parametrize(
    ("versions", "raw", "words"),
    [
        (("draft-2",), "", "draft-1 has no section"),
        (("draft-2", "draft-1", "draft-1"), "", "included twice"),
        (("draft-1", "draft-2"), "", "newest first"),
        (("draft-2", "draft-1", "draft-3"), "", "names no draft"),
        (
            ("draft-2",),
            '{% include-markdown "./_drafts/draft-1.md" %}\n',
            "names no draft",
        ),
    ],
    ids=[
        "missing",
        "twice",
        "oldest-first",
        "unknown-draft",
        "url-rewriting-include",
    ],
)
def test_a_revision_log_fault_is_named(tmp_path, versions, raw, words):
    register = dr.parse_register(_TWO, SHOWN)
    _revision_log(tmp_path, *versions, raw=raw)
    faults = dr.revision_log_faults(tmp_path, register)
    assert any(words in f.detail for f in faults), [f.detail for f in faults]
    assert all(f.path == dr.REVISION_LOG_PATH for f in faults)


# --- DOCBW-08-003: released entries against their release tags --------------


@pytest.fixture
def repo(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    isolate_git_config(monkeypatch)
    work = tmp_path / "work"
    work.mkdir()
    git(work, "init", "-q")
    return work


def _commit_register(repo: Path, text: str, message: str = "register") -> None:
    path = repo / dr.REGISTER_PATH
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")
    git(repo, "add", "-A")
    git(repo, "commit", "-q", "-m", message)


def _released_at_tag(repo: Path) -> None:
    """``v2026.11.0`` carries a register that names it as draft-1's release."""
    _commit_register(repo, _register(_released(1, "v2026.11.0")))
    git(repo, "tag", "-a", "v2026.11.0", "-m", "release")


@pytest.mark.spec("DOCBW-08-003")
def test_an_unchanged_released_entry_passes(repo):
    _released_at_tag(repo)
    _commit_register(repo, _register(_released(1, "v2026.11.0"), _open(2)))
    assert dr.check_releases(repo) == []


@pytest.mark.spec("DOCBW-08-003")
def test_a_removed_released_entry_fails(repo):
    _released_at_tag(repo)
    _commit_register(repo, _register(_open(1)))
    (fault,) = dr.check_releases(repo)
    assert "draft-1" in fault and "v2026.11.0" in fault


@pytest.mark.spec("DOCBW-08-003")
def test_a_changed_released_entry_fails(repo):
    _released_at_tag(repo)
    changed = _register(
        _entry("draft-1", "released", date="2026-11-07", release="v2026.11.0")
    )
    _commit_register(repo, changed)
    (fault,) = dr.check_releases(repo)
    assert "differs from its entry at release v2026.11.0" in fault


@pytest.mark.spec("DOCBW-08-003")
def test_a_new_entry_naming_an_existing_tag_that_never_carried_it_fails(repo):
    _commit_register(repo, _register(_open(1)))
    git(repo, "tag", "-a", "v2026.10.0", "-m", "earlier release")
    _commit_register(repo, _register(_released(1, "v2026.10.0")))
    (fault,) = dr.check_releases(repo)
    assert "v2026.10.0" in fault and "does not hold the same entry" in fault


@pytest.mark.spec("DOCBW-08-003")
def test_an_entry_naming_a_tag_older_than_the_register_fails(repo):
    git(repo, "commit", "--allow-empty", "-q", "-m", "before the register")
    git(repo, "tag", "-a", "v2025.1.0", "-m", "old release")
    _commit_register(repo, _register(_released(1, "v2025.1.0")))
    (fault,) = dr.check_releases(repo)
    assert "that tag's register does not exist" in fault


@pytest.mark.spec("DOCBW-08-003")
def test_an_entry_whose_tag_is_not_made_yet_is_not_judged(repo):
    """Marked released before the promote: the tag does not exist yet."""
    _commit_register(repo, _register(_released(1, "v2026.11.0")))
    assert dr.check_releases(repo) == []


@pytest.mark.spec("DOCBW-08-003")
def test_the_cli_exits_nonzero_on_a_fault(repo, monkeypatch, capsys):
    _released_at_tag(repo)
    _commit_register(repo, _register(_open(1)))
    monkeypatch.setattr(dr, "repo_root", lambda: repo)
    with pytest.raises(SystemExit) as exited:
        dr.main(["check-releases"])
    assert exited.value.code == 1
    assert "DOCBW-08-003" in capsys.readouterr().err


@pytest.mark.spec("DOCBW-08-001")
def test_a_ref_without_a_register_reads_as_none(repo):
    git(repo, "commit", "--allow-empty", "-q", "-m", "before the register")
    git(repo, "tag", "-a", "v2025.1.0", "-m", "old release")
    assert dr.load_register_at("v2025.1.0", repo) is None


@pytest.mark.spec("DOCBW-08-002")
def test_a_malformed_register_at_a_ref_is_named_at_ref_path_line(repo):
    _commit_register(repo, _register(_open(1), _open(2)))
    git(repo, "tag", "-a", "v2026.11.0", "-m", "release")
    with pytest.raises(MetadataLoadErrors) as caught:
        dr.load_register_at("v2026.11.0", repo)
    assert str(caught.value.failures[0]).startswith(
        f"v2026.11.0:{dr.REGISTER_PATH}:2:5"
    )


@pytest.mark.spec("DOCBW-08-003")
def test_the_review_workflow_runs_the_check_after_the_build():
    wf_steps = steps(load_workflow(WORKFLOWS_DIR / "docs-build-check.yml"))
    build = index_of(wf_steps, BUILD_SITE_ACTION, "uses")
    check = next(
        i
        for i, step in enumerate(wf_steps)
        if "uv run drafts-register check-releases" in live_text(step)
    )
    assert build is not None and build < check, "the build fetches the tags"
    assert neutering(wf_steps[check]) == []


@pytest.mark.spec("DOCBW-08-001")
def test_show_reads_the_register_at_a_ref(repo, monkeypatch, capsys):
    _released_at_tag(repo)
    _commit_register(repo, _register(_released(1, "v2026.11.0"), _open(2)))
    monkeypatch.setattr(dr, "repo_root", lambda: repo)
    dr.main(["show", "--ref", "v2026.11.0"])
    printed = json.loads(capsys.readouterr().out)
    assert printed["current"] is None
    assert printed["register"] == f"v2026.11.0:{dr.REGISTER_PATH}"


@pytest.mark.spec("DOCBW-08-001")
@pytest.mark.parametrize(
    ("ref", "words"), [("v2025.1.0", "holds no"), ("no-such-ref", "git")]
)
def test_show_fails_on_a_ref_with_no_register(
    repo, monkeypatch, capsys, ref, words
):
    git(repo, "commit", "--allow-empty", "-q", "-m", "before the register")
    git(repo, "tag", "-a", "v2025.1.0", "-m", "old release")
    monkeypatch.setattr(dr, "repo_root", lambda: repo)
    with pytest.raises(SystemExit) as exited:
        dr.main(["show", "--ref", ref])
    assert exited.value.code == 1
    assert words in capsys.readouterr().err


@pytest.mark.spec("DOCBW-08-001")
def test_show_prints_null_for_a_ref_with_no_register_when_asked(
    repo, monkeypatch, capsys
):
    """The promote reads a release older than the register as carrying no draft."""
    git(repo, "commit", "--allow-empty", "-q", "-m", "before the register")
    git(repo, "tag", "-a", "v2025.1.0", "-m", "old release")
    monkeypatch.setattr(dr, "repo_root", lambda: repo)
    dr.main(["show", "--ref", "v2025.1.0", "--absent-ok"])
    assert json.loads(capsys.readouterr().out) is None
    # A ref git cannot read is still an error.
    with pytest.raises(SystemExit) as exited:
        dr.main(["show", "--ref", "no-such-ref", "--absent-ok"])
    assert exited.value.code == 1


@pytest.mark.spec("DOCBW-08-003")
def test_the_cli_passes_an_agreeing_register(repo, monkeypatch, capsys):
    _released_at_tag(repo)
    monkeypatch.setattr(dr, "repo_root", lambda: repo)
    dr.main(["check-releases"])
    assert "matches" in capsys.readouterr().out


@pytest.mark.spec("DOCBW-08-004")
@pytest.mark.parametrize(
    ("text", "words"),
    [
        (
            "# Log\n\n## Draft 2\n\n" + dr.include_line("draft-1") + "\n",
            "not '## Draft 1'",
        ),
        ("# Log\n\n" + dr.include_line("draft-1") + "\n", "no heading"),
    ],
    ids=["wrong-heading", "no-heading"],
)
def test_a_table_under_another_drafts_heading_is_named(tmp_path, text, words):
    register = dr.parse_register(_register(_open(1)), SHOWN)
    write_generated(tmp_path / dr.REVISION_LOG_PATH, text)
    (fault,) = dr.revision_log_faults(tmp_path, register)
    assert words in fault.detail
    assert fault.line is not None


@pytest.mark.spec("DOCBW-08-004")
def test_a_draft_section_with_no_table_is_named_at_its_heading(tmp_path):
    register = dr.parse_register(_register(_open(1)), SHOWN)
    text = (
        "# Log\n\n## Draft 2\n\nA hand-written section.\n\n"
        "## Draft 1\n\n" + dr.include_line("draft-1") + "\n"
    )
    write_generated(tmp_path / dr.REVISION_LOG_PATH, text)
    (fault,) = dr.revision_log_faults(tmp_path, register)
    assert "no status-table include" in fault.detail
    assert fault.line == 3


@pytest.mark.spec("DOCBW-08-004")
def test_the_order_fault_is_named_where_the_order_breaks(tmp_path):
    register = dr.parse_register(
        _register(_released(1), _released(2), _open(3)), SHOWN
    )
    _revision_log(tmp_path, "draft-3", "draft-1", "draft-2")
    (fault,) = dr.revision_log_faults(tmp_path, register)
    assert "draft-2 comes after draft-1" in fault.detail
    lines = (tmp_path / dr.REVISION_LOG_PATH).read_text().splitlines()
    assert fault.line is not None
    assert lines[fault.line - 1] == dr.include_line("draft-2")


# --- DOCBW-08-043: marking the open draft released ----------------------------

_HEADER = "# The register's header comment.\n#\n# It is kept as written.\n"
FREEZE = dr.Freeze("v2026.11.1", dr.date(2026, 11, 16))


@pytest.fixture
def clone(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    """A clone of a bare ``origin``, so the command can fetch its tags."""
    isolate_git_config(monkeypatch)
    return scratch_clone(tmp_path)


def _freeze_repo(repo: Path, text: str) -> None:
    _commit_register(repo, _HEADER + text)


def _never_predicted(_root: Path) -> dr.Freeze:
    raise AssertionError("predicted a freeze")


def _tracked(repo: Path) -> dict[str, str]:
    """The register and its fragments, as the clone holds them now."""
    paths = [dr.REGISTER_PATH, dr.STATUS_BOX_PATH]
    paths += [
        str(p.relative_to(repo)) for p in (repo / dr.FRAGMENT_DIR).glob("*")
    ]
    return {
        p: (repo / p).read_text(encoding="utf-8")
        for p in paths
        if (repo / p).exists()
    }


@pytest.mark.spec("DOCBW-08-043")
def test_release_marks_the_open_draft_released_and_regenerates(clone):
    _freeze_repo(clone, _register(_released(1, "v2026.11.0"), _open(2)))
    git(clone, "tag", "-a", "v2026.11.0", "-m", "release")
    asked: list[Path] = []

    def predict(root: Path) -> dr.Freeze:
        asked.append(root)
        return FREEZE

    entry, freeze = dr.release_open_draft(clone, predict=predict)
    assert asked == [clone]
    assert freeze == FREEZE
    assert (entry.version, entry.release, entry.date.isoformat()) == (
        "draft-2",
        "v2026.11.1",
        "2026-11-16",
    )
    text = (clone / dr.REGISTER_PATH).read_text(encoding="utf-8")
    assert text == _HEADER + _register(
        _released(1, "v2026.11.0"),
        _entry("draft-2", "released", "2026-11-16", "v2026.11.1"),
    )
    register = dr.load_register(clone)
    assert list(stale_paths(clone, dr.desired_fragments(register))) == []
    # The released entry still matches its tag's register (DOCBW-08-003).
    assert dr.check_releases(clone) == []


@pytest.mark.spec("DOCBW-08-043")
def test_release_with_a_given_freeze_does_not_predict(clone):
    _freeze_repo(clone, _register(_open(1)))
    entry, freeze = dr.release_open_draft(
        clone, FREEZE, predict=_never_predicted
    )
    assert freeze == FREEZE and entry.release == "v2026.11.1"


@pytest.mark.spec("DOCBW-08-041", "DOCBW-08-043", "DOCBW-08-045")
def test_release_dates_again_a_draft_whose_release_is_not_made(clone):
    """The publish it was dated for never ran: run the command again."""
    _freeze_repo(
        clone,
        _register(_entry("draft-1", "released", "2026-11-13", "v2026.11.1")),
    )
    entry, _ = dr.release_open_draft(clone, FREEZE)
    assert (entry.version, entry.date.isoformat()) == ("draft-1", "2026-11-16")


@pytest.mark.spec("DOCBW-08-003", "DOCBW-08-043", "DOCBW-08-045")
@pytest.mark.parametrize("where", ["local", "origin-only"])
def test_release_refuses_when_every_drafts_release_is_made(clone, where):
    """A tag only ``origin`` holds counts too: the command fetches it first."""
    _freeze_repo(clone, _register(_released(1, "v2026.11.0")))
    git(clone, "tag", "-a", "v2026.11.0", "-m", "release")
    if where == "origin-only":
        git(clone, "push", "-q", "origin", "HEAD", "v2026.11.0")
        git(clone, "tag", "-d", "v2026.11.0")
    before = _tracked(clone)
    with pytest.raises(
        dr.ReleaseCommandError, match="every draft is released"
    ):
        dr.release_open_draft(clone, FREEZE)
    assert _tracked(clone) == before


@pytest.mark.spec("DOCBW-08-043")
def test_release_refuses_a_register_it_would_write_malformed(clone):
    """A given tag that another entry already names is refused before any write."""
    _freeze_repo(clone, _register(_released(1, "v2026.11.0"), _open(2)))
    before = _tracked(clone)
    with pytest.raises((MetadataLoadError, MetadataLoadErrors)):
        dr.release_open_draft(clone, dr.Freeze("v2026.11.0", FREEZE.day))
    assert _tracked(clone) == before


@pytest.mark.spec("DOCBW-08-043")
def test_release_refuses_a_flow_style_list(clone):
    """With no ``drafts:`` block line, the header cannot be told apart."""
    _commit_register(
        clone,
        "{drafts: [{version: draft-1, status: unreleased, date: 2026-11-06}]}\n",
    )
    with pytest.raises(dr.ReleaseCommandError, match="block list"):
        dr.release_open_draft(clone, FREEZE)


@pytest.mark.spec("DOCBW-08-043")
@pytest.mark.parametrize(
    "text",
    [
        _register(_open(1)) + "  # draft-2 opens after the release\n",
        _register(_open(1)).replace("2026-11-06", "2026-11-06  # opened"),
    ],
    ids=["own-line", "trailing"],
)
def test_release_refuses_a_comment_inside_the_list(clone, text):
    """Writing the list again would drop the comment, so nothing is written."""
    _freeze_repo(clone, text)
    before = _tracked(clone)
    with pytest.raises(dr.ReleaseCommandError, match="comment inside"):
        dr.release_open_draft(clone, FREEZE)
    assert _tracked(clone) == before


@pytest.mark.spec("DOCBW-08-003", "DOCBW-08-043", "DOCBW-08-045")
def test_release_fails_before_any_write_when_the_tags_cannot_be_fetched(clone):
    _freeze_repo(clone, _register(_open(1)))
    git(clone, "remote", "remove", "origin")
    before = _tracked(clone)
    with pytest.raises(dr.GitError):
        dr.release_open_draft(clone, FREEZE)
    assert _tracked(clone) == before


@pytest.mark.spec("DOCBW-08-043")
def test_release_cli_takes_a_given_tag_and_date(clone, monkeypatch, capsys):
    _freeze_repo(clone, _register(_open(1)))
    monkeypatch.setattr(dr, "repo_root", lambda: clone)
    monkeypatch.setattr(dr, "predict_freeze", _never_predicted)
    dr.main(["release", "--release", "v2026.12.0", "--date", "2026-12-01"])
    out = capsys.readouterr().out
    assert "Marked draft-1 released in v2026.12.0, dated 2026-12-01" in out
    assert "before the publish of 2026-12-01" in out
    assert "promote workflow with an empty input" in out
    (entry,) = dr.load_register(clone).released
    assert (entry.release, entry.date.isoformat()) == (
        "v2026.12.0",
        "2026-12-01",
    )


@pytest.mark.spec("DOCBW-08-043")
def test_release_cli_names_the_predicted_publish_start(
    clone, monkeypatch, capsys
):
    _freeze_repo(clone, _register(_open(1)))
    monkeypatch.setattr(dr, "repo_root", lambda: clone)
    starts = dr.datetime.fromisoformat("2026-11-16T06:07:00+00:00")
    monkeypatch.setattr(
        dr,
        "predict_freeze",
        lambda _root: dr.Freeze(FREEZE.release, FREEZE.day, starts),
    )
    dr.main(["release"])
    assert "before 2026-11-16 06:07 UTC" in capsys.readouterr().out


@pytest.mark.spec("DOCBW-08-043")
def test_release_cli_refuses_a_tag_without_a_date(clone, monkeypatch, capsys):
    _freeze_repo(clone, _register(_open(1)))
    monkeypatch.setattr(dr, "repo_root", lambda: clone)
    with pytest.raises(SystemExit) as exited:
        dr.main(["release", "--release", "v2026.12.0"])
    assert exited.value.code == 1
    assert "go together" in capsys.readouterr().err


@pytest.mark.spec("DOCBW-08-043")
def test_predict_freeze_reads_next_freeze(tmp_path, monkeypatch):
    calls: list[list[str]] = []

    class _Proc:
        returncode = 0
        stdout = (
            '{"release": "v2026.11.1", "date": "2026-11-16", '
            '"publish_starts": "2026-11-16T06:07:00+00:00"}\n'
        )
        stderr = ""

    def fake_run(argv, **kwargs):
        calls.append(list(argv))
        assert kwargs["cwd"] == tmp_path
        return _Proc()

    monkeypatch.setattr(dr.subprocess, "run", fake_run)
    freeze = dr.predict_freeze(tmp_path)
    assert (freeze.release, freeze.day) == (FREEZE.release, FREEZE.day)
    assert freeze.publish_starts == dr.datetime.fromisoformat(
        "2026-11-16T06:07:00+00:00"
    )
    (script,) = calls
    assert script[1:] == [
        "-I",
        str(tmp_path / dr.RELEASE_SCRIPT),
        "next-freeze",
    ]


@pytest.mark.spec("DOCBW-08-043")
@pytest.mark.parametrize(
    ("code", "stdout", "words"),
    [
        (1, "", "next-freeze failed"),
        (0, "not json", "printed no prediction"),
        (
            0,
            '{"release": "v2026.11.1", "date": "2026-11-16"}',
            "printed no prediction",
        ),
    ],
    ids=["failed", "not-json", "no-start"],
)
def test_predict_freeze_refuses_a_failed_prediction(
    tmp_path, monkeypatch, code, stdout, words
):
    proc = SimpleNamespace(returncode=code, stdout=stdout, stderr="boom")
    monkeypatch.setattr(dr.subprocess, "run", lambda argv, **kw: proc)
    with pytest.raises(dr.ReleaseCommandError, match=words):
        dr.predict_freeze(tmp_path)


def test_predict_freeze_runs_the_real_script():
    """The isolated (``-I``) run of ``next-freeze`` imports and predicts."""
    before = datetime.now(UTC)
    freeze = dr.predict_freeze(repo_root())
    assert re.fullmatch(r"v\d{4}\.\d{1,2}\.\d+", freeze.release)
    assert freeze.publish_starts > before
    assert freeze.publish_starts.date() == freeze.day
    assert freeze.day.weekday() < 5
    assert (freeze.publish_starts.hour, freeze.publish_starts.minute) == (6, 7)


def test_release_script_is_the_promotes_script():
    """The command runs the script the promote runs, which has next-freeze."""
    script = repo_root() / dr.RELEASE_SCRIPT
    assert '"next-freeze"' in script.read_text(encoding="utf-8")
