"""Tests for vultron.metadata.specs.rationale (MS-10-012, MS-10-013, MS-10-015).

The growth guard's extractor is exercised through ``added_since_base`` in
``test_growth_guard.py``; this module covers the two advisory worklists, the
per-file filter, and the ``spec-rationale`` command line.
"""

from pathlib import Path

import pytest
import yaml

from vultron.metadata.specs.rationale import (
    adr_link_candidates,
    history_labels,
    history_narration_hits,
    live_adr_bodies,
    load_with_files,
    main,
    missing_rationale,
    report_lines,
)


def _spec(spec_id: str, rationale: str | None = "It prevents a gap.", **extra):
    spec = {
        "id": spec_id,
        "priority": "SHOULD",
        "kind": "project",
        "statement": f"{spec_id} SHOULD do the thing",
        **extra,
    }
    if rationale is not None:
        spec["rationale"] = rationale
    return spec


def _write_file(spec_dir: Path, prefix: str, *specs: dict) -> None:
    data = {
        "id": prefix,
        "title": f"{prefix} file",
        "description": f"{prefix} test specs",
        "scope": ["production"],
        "groups": [
            {"id": f"{prefix}-01", "title": "Group", "specs": list(specs)}
        ],
    }
    (spec_dir / f"{prefix.lower()}.yaml").write_text(yaml.dump(data))


def _write_adr(adr_dir: Path, name: str, status: str, body: str) -> None:
    (adr_dir / name).write_text(
        "---\n"
        f"status: {status}\n"
        "created: 2026-01-01\n"
        "updated: 2026-01-01\n"
        "revision: 1\n"
        "---\n\n"
        f"# {name}\n\n{body}\n"
    )


@pytest.fixture
def repo(tmp_path: Path) -> Path:
    """Two spec files and three records: live, rejected and archived."""
    spec_dir = tmp_path / "specs"
    spec_dir.mkdir()
    _write_file(
        spec_dir,
        "AAA",
        _spec("AAA-01-001"),
        _spec("AAA-01-002", rationale=None),
        _spec("AAA-01-003", rationale="Added in #123 after review."),
        _spec("AAA-01-004", adr=["ADR-0001"]),
    )
    _write_file(
        spec_dir,
        "BBB",
        _spec("BBB-01-001", rationale=None),
        _spec("BBB-01-002", rationale="It was previously optional."),
    )
    adr_dir = tmp_path / "docs" / "adr"
    (adr_dir / "archived").mkdir(parents=True)
    _write_adr(
        adr_dir,
        "0001-live.md",
        "accepted",
        "Generates AAA-01-001, AAA-01-004 and BBB-01-001; ZZZ-01-001 is gone.",
    )
    _write_adr(adr_dir, "0002-rejected.md", "rejected", "Names AAA-01-002.")
    _write_adr(
        adr_dir / "archived", "0003-old.md", "accepted", "Names AAA-01-003."
    )
    return tmp_path


# --- the rule's subject: requirements with no rationale ---------------------


@pytest.mark.spec("MS-10-012")
def test_missing_rationale_lists_each_requirement_without_one(repo):
    registry = load_with_files(repo / "specs")[0]
    assert missing_rationale(registry) == {"AAA-01-002", "BBB-01-001"}


def test_load_with_files_names_each_requirement_file(repo):
    registry, owner = load_with_files(repo / "specs")
    assert owner["AAA-01-004"] == "specs/aaa.yaml"
    assert owner["BBB-01-002"] == "specs/bbb.yaml"
    assert owner.keys() == registry.all_specs.keys()


# --- history-narration worklist (MS-10-015) ---------------------------------


@pytest.mark.spec("MS-10-015")
@pytest.mark.parametrize(
    ("text", "label"),
    [
        ("Fixed in #4170.", "issue reference"),
        ("A PR reverted it.", "pull request"),
        ("See CONCERN-2382.", "planning item"),
        ("This was previously a SHOULD.", "prior state"),
        ("It no longer applies to joins.", "prior state"),
        ("The field was renamed last year.", "edit event"),
        ("Upgraded from SHOULD to MUST.", "edit event"),
        ("Holds until ADR-0099 lands.", "until a decision"),
        ("Until ADR-0099 lands, it holds.", "until a decision"),
        ("Rejected in PR #4170.", "pull request"),
        ("Agents used to skip the check.", "prior state"),
    ],
)
def test_history_labels_flag_narration(text, label):
    assert label in history_labels(text)


@pytest.mark.spec("MS-10-015")
@pytest.mark.parametrize(
    "text",
    [
        "Without it, a receiver cannot tell a duplicate from a new message.",
        "A count pinned to the live value races every concurrent change.",
        "Prevents a replica from diverging from the canonical ledger.",
        "A PR-only growth guard has no shared number to race.",
        "Each PR must say what it closes, so reviewers can map the diff.",
        "The marker is used to find the owner of each requirement.",
    ],
)
def test_history_labels_pass_a_reason(text):
    assert history_labels(text) == ()


@pytest.mark.spec("MS-10-015")
def test_history_hits_name_each_flagged_requirement_and_file(repo):
    hits = history_narration_hits(*load_with_files(repo / "specs"))
    assert [(h.spec_id, h.spec_file, h.labels) for h in hits] == [
        ("AAA-01-003", "specs/aaa.yaml", ("issue reference",)),
        ("BBB-01-002", "specs/bbb.yaml", ("prior state",)),
    ]


# --- candidate ADR links (MS-10-015) ----------------------------------------


@pytest.mark.spec("MS-10-015")
def test_live_adr_bodies_skip_retired_and_archived_records(repo):
    bodies = live_adr_bodies(repo)
    assert set(bodies) == {"ADR-0001"}
    assert "AAA-01-001" in bodies["ADR-0001"]


@pytest.mark.spec("MS-10-015")
def test_adr_link_candidates_omit_cited_and_unknown_ids(repo):
    """A cited record and an ID naming no requirement are not candidates."""
    candidates = adr_link_candidates(
        *load_with_files(repo / "specs"), live_adr_bodies(repo)
    )
    assert [(c.spec_id, c.spec_file, c.adr_id) for c in candidates] == [
        ("AAA-01-001", "specs/aaa.yaml", "ADR-0001"),
        ("BBB-01-001", "specs/bbb.yaml", "ADR-0001"),
    ]


# --- per-file reports and the command line ----------------------------------


@pytest.mark.spec("MS-10-015")
@pytest.mark.parametrize(
    ("report", "expected"),
    [
        ("missing", ["specs/bbb.yaml: BBB-01-001: no rationale"]),
        (
            "history",
            [
                "specs/bbb.yaml: BBB-01-002: rationale may narrate history "
                "(prior state)"
            ],
        ),
        (
            "adr-links",
            [
                "specs/bbb.yaml: BBB-01-001: ADR-0001 names it, but its adr: "
                "does not cite ADR-0001"
            ],
        ),
    ],
)
def test_report_lines_filter_by_spec_file(repo, report, expected):
    assert report_lines(report, repo, ["specs/bbb.yaml"]) == expected


def test_report_lines_without_filter_keep_every_file(repo):
    assert report_lines("missing", repo) == [
        "specs/aaa.yaml: AAA-01-002: no rationale",
        "specs/bbb.yaml: BBB-01-001: no rationale",
    ]


def test_report_lines_refuse_an_unknown_spec_file(repo):
    with pytest.raises(ValueError, match="not a spec file"):
        report_lines("missing", repo, ["specs/nope.yaml"])


def test_report_lines_refuse_an_unknown_report(repo):
    with pytest.raises(ValueError, match="unknown report"):
        report_lines("everything", repo)


def test_cli_prints_the_report_and_exits_zero(repo, monkeypatch, capsys):
    (repo / "pyproject.toml").write_text("")
    monkeypatch.chdir(repo)
    main(["missing", "--file", "aaa.yaml"])
    out = capsys.readouterr().out.splitlines()
    assert out == [
        "specs/aaa.yaml: AAA-01-002: no rationale",
        "[INFO] 1 item(s) in the missing report",
    ]


def test_cli_accepts_a_path_under_specs(repo, monkeypatch, capsys):
    (repo / "pyproject.toml").write_text("")
    monkeypatch.chdir(repo)
    main(["missing", "--file", "specs/bbb.yaml", "--file", "aaa.yaml"])
    assert capsys.readouterr().out.splitlines()[-1] == (
        "[INFO] 2 item(s) in the missing report"
    )


def test_cli_rejects_an_unknown_spec_file(repo, monkeypatch, capsys):
    (repo / "pyproject.toml").write_text("")
    monkeypatch.chdir(repo)
    with pytest.raises(SystemExit) as exc:
        main(["history", "--file", "nope.yaml"])
    assert exc.value.code == 2
    assert "not a spec file" in capsys.readouterr().err
