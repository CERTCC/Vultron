"""Tests for vultron.metadata.specs.lint (SR.2.4).

Covers: hard-error checks (duplicate IDs, dangling relationships, prefix
mismatch) and advisory warnings (testable_without_steps, rationale_too_long,
missing_tags) including lint_suppress suppression.
"""

import yaml

from vultron.metadata.specs.lint import lint

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _write_yaml(path, data, filename="specs.yaml"):
    (path / filename).write_text(yaml.dump(data))


def _minimal_spec(spec_id="TST-01-001", priority="MUST", extra=None):
    spec = {
        "id": spec_id,
        "priority": priority,
        "kind": "protocol",
        "statement": f"{spec_id} MUST do the thing",
        "rationale": "Because testing",
        "tags": ["testing"],
    }
    if extra:
        spec.update(extra)
    return {
        "id": "TST",
        "title": "Test File",
        "description": "Test spec file",
        "version": "0.1",
        "scope": ["production"],
        "groups": [
            {
                "id": "TST-01",
                "title": "Group",
                "specs": [spec],
            }
        ],
    }


# ---------------------------------------------------------------------------
# Clean cases
# ---------------------------------------------------------------------------


def test_lint_clean_dir(tmp_path, capsys):
    _write_yaml(tmp_path, _minimal_spec())
    result = lint(tmp_path)
    captured = capsys.readouterr()
    assert result == 0
    assert "[ERROR]" not in captured.err


def test_lint_empty_dir(tmp_path):
    result = lint(tmp_path)
    assert result == 0


# ---------------------------------------------------------------------------
# Hard errors
# ---------------------------------------------------------------------------


def test_lint_duplicate_spec_ids(tmp_path):
    data = _minimal_spec("DUP-01-001")
    data["id"] = "DUP"
    data["groups"][0]["id"] = "DUP-01"
    data["groups"][0]["specs"][0]["statement"] = "DUP-01-001 MUST be unique"
    _write_yaml(tmp_path, data, "file1.yaml")
    _write_yaml(tmp_path, data, "file2.yaml")
    result = lint(tmp_path)
    assert result == 1


def test_lint_dangling_relationship(tmp_path, capsys):
    data = _minimal_spec(
        extra={
            "relationships": [
                {"rel_type": "depends_on", "spec_id": "XX-99-999"}
            ]
        }
    )
    _write_yaml(tmp_path, data)
    result = lint(tmp_path)
    captured = capsys.readouterr()
    assert result == 1
    assert "XX-99-999" in captured.err


def test_lint_prefix_mismatch(tmp_path, capsys):
    data = {
        "id": "TST",
        "title": "Test File",
        "description": "Prefix mismatch test",
        "version": "0.1",
        "scope": ["production"],
        "groups": [
            {
                "id": "OTHER-01",  # prefix "OTHER" != file id "TST"
                "title": "Wrong Group",
                "specs": [
                    {
                        "id": "OTHER-01-001",
                        "priority": "MUST",
                        "kind": "protocol",
                        "statement": "OTHER-01-001 MUST be consistent",
                        "rationale": "Consistency",
                        "tags": ["testing"],
                    }
                ],
            }
        ],
    }
    _write_yaml(tmp_path, data)
    result = lint(tmp_path)
    captured = capsys.readouterr()
    assert result == 1
    assert "OTHER-01" in captured.err


# ---------------------------------------------------------------------------
# Advisory warnings (non-blocking — return 0)
# ---------------------------------------------------------------------------


def test_lint_advisory_testable_without_steps(tmp_path, capsys):
    data = _minimal_spec(extra={"testable": False})
    _write_yaml(tmp_path, data)
    result = lint(tmp_path)
    captured = capsys.readouterr()
    assert result == 0
    assert "[WARN]" in captured.out
    assert "testable=false" in captured.out


def test_lint_advisory_rationale_too_long(tmp_path, capsys):
    data = _minimal_spec(extra={"rationale": "x" * 501})
    _write_yaml(tmp_path, data)
    result = lint(tmp_path)
    captured = capsys.readouterr()
    assert result == 0
    assert "[WARN]" in captured.out
    assert "rationale" in captured.out


def test_lint_advisory_missing_tags(tmp_path, capsys):
    data = _minimal_spec()
    del data["groups"][0]["specs"][0]["tags"]
    _write_yaml(tmp_path, data)
    result = lint(tmp_path)
    captured = capsys.readouterr()
    assert result == 0
    assert "[WARN]" in captured.out
    assert "tags" in captured.out


# ---------------------------------------------------------------------------
# lint_suppress suppression
# ---------------------------------------------------------------------------


def test_lint_suppress_testable_without_steps(tmp_path, capsys):
    data = _minimal_spec(
        extra={
            "testable": False,
            "lint_suppress": ["testable_without_steps"],
        }
    )
    _write_yaml(tmp_path, data)
    result = lint(tmp_path)
    captured = capsys.readouterr()
    assert result == 0
    assert "testable=false" not in captured.out


def test_lint_suppress_rationale_too_long(tmp_path, capsys):
    data = _minimal_spec(
        extra={
            "rationale": "x" * 501,
            "lint_suppress": ["rationale_too_long"],
        }
    )
    _write_yaml(tmp_path, data)
    result = lint(tmp_path)
    captured = capsys.readouterr()
    assert result == 0
    assert "rationale exceeds" not in captured.out


def test_lint_suppress_missing_tags(tmp_path, capsys):
    data = _minimal_spec()
    del data["groups"][0]["specs"][0]["tags"]
    data["groups"][0]["specs"][0]["lint_suppress"] = ["missing_tags"]
    _write_yaml(tmp_path, data)
    result = lint(tmp_path)
    captured = capsys.readouterr()
    assert result == 0
    assert "no tags" not in captured.out


# ---------------------------------------------------------------------------
# Spec ID vs group prefix check (MS-04-004)
# ---------------------------------------------------------------------------


def test_lint_spec_id_prefix_mismatch(tmp_path, capsys):
    """A spec with ID TST-01-001 living in group TST-02 must be a hard error."""
    data = {
        "id": "TST",
        "title": "Test File",
        "description": "Spec ID prefix mismatch test",
        "version": "0.1",
        "scope": ["production"],
        "groups": [
            {
                "id": "TST-02",
                "title": "Group Two",
                "specs": [
                    {
                        "id": "TST-01-001",  # prefix TST-01 != group TST-02
                        "priority": "MUST",
                        "kind": "protocol",
                        "statement": "TST-01-001 MUST be in group TST-01",
                        "rationale": "Prefix consistency",
                        "tags": ["testing"],
                    }
                ],
            }
        ],
    }
    _write_yaml(tmp_path, data)
    result = lint(tmp_path)
    captured = capsys.readouterr()
    assert result == 1
    assert "TST-01-001" in captured.err
    assert "TST-02" in captured.err


def test_lint_spec_id_prefix_match_passes(tmp_path, capsys):
    """A spec ID whose prefix matches its group must not produce an error."""
    data = _minimal_spec("TST-01-001")  # lives in group TST-01 — correct
    _write_yaml(tmp_path, data)
    result = lint(tmp_path)
    captured = capsys.readouterr()
    assert result == 0
    assert "TST-01-001" not in captured.err


# ---------------------------------------------------------------------------
# ADR reference check (dangling_adr_ref) — advisory, non-blocking
# ---------------------------------------------------------------------------


def _make_adr_dir(tmp_path, adr_numbers=None):
    """Create a fake docs/adr/ directory with stub ADR files."""
    adr_dir = tmp_path / "docs" / "adr"
    adr_dir.mkdir(parents=True)
    for num in adr_numbers or []:
        # Valid status frontmatter so the MS-14-001 status check (which runs
        # over every ADR in the dir) does not flag these reference stubs.
        (adr_dir / f"{num}-stub.md").write_text(
            f"---\nstatus: accepted\n---\n# ADR-{num}\n"
        )
    return adr_dir


def test_lint_adr_ref_missing_emits_warn(tmp_path, capsys):
    """A rationale referencing ADR-0099 that has no file emits a [WARN]."""
    data = _minimal_spec(extra={"rationale": "Derived from ADR-0099."})
    _write_yaml(tmp_path, data)
    adr_dir = _make_adr_dir(tmp_path)  # no 0099 file
    result = lint(tmp_path, adr_dir=adr_dir)
    captured = capsys.readouterr()
    assert result == 0  # advisory only, not a hard error
    assert "[WARN]" in captured.out
    assert "ADR-0099" in captured.out


def test_lint_adr_ref_present_no_warn(tmp_path, capsys):
    """A rationale referencing ADR-0099 when the file exists emits no warning."""
    data = _minimal_spec(extra={"rationale": "Derived from ADR-0099."})
    _write_yaml(tmp_path, data)
    adr_dir = _make_adr_dir(tmp_path, ["0099"])
    result = lint(tmp_path, adr_dir=adr_dir)
    captured = capsys.readouterr()
    assert result == 0
    assert "ADR-0099" not in captured.out


def test_lint_adr_ref_no_adr_dir_skips_check(tmp_path, capsys):
    """When adr_dir does not exist the check is silently skipped."""
    data = _minimal_spec(extra={"rationale": "Derived from ADR-0099."})
    _write_yaml(tmp_path, data)
    nonexistent = tmp_path / "nonexistent" / "adr"
    result = lint(tmp_path, adr_dir=nonexistent)
    captured = capsys.readouterr()
    assert result == 0
    assert "ADR-0099" not in captured.out


def test_lint_adr_ref_suppress(tmp_path, capsys):
    """dangling_adr_ref can be suppressed via lint_suppress."""
    data = _minimal_spec(
        extra={
            "rationale": "Derived from ADR-0099.",
            "lint_suppress": ["dangling_adr_ref"],
        }
    )
    _write_yaml(tmp_path, data)
    adr_dir = _make_adr_dir(tmp_path)  # no 0099 file
    result = lint(tmp_path, adr_dir=adr_dir)
    captured = capsys.readouterr()
    assert result == 0
    assert "ADR-0099" not in captured.out


def test_lint_adr_ref_no_rationale_no_warn(tmp_path, capsys):
    """A spec without a rationale field produces no ADR warning."""
    data = _minimal_spec()
    del data["groups"][0]["specs"][0]["rationale"]
    _write_yaml(tmp_path, data)
    adr_dir = _make_adr_dir(tmp_path)
    result = lint(tmp_path, adr_dir=adr_dir)
    captured = capsys.readouterr()
    assert result == 0
    assert "ADR-" not in captured.out


# ---------------------------------------------------------------------------
# Missing item-level kind is a hard error
# ---------------------------------------------------------------------------


def test_lint_missing_item_kind_is_hard_error(tmp_path):
    """A spec item missing kind: is a hard error (exit 1)."""
    data = _minimal_spec()
    del data["groups"][0]["specs"][0]["kind"]
    _write_yaml(tmp_path, data)
    result = lint(tmp_path)
    assert result == 1


# ---------------------------------------------------------------------------
# scenario_start group must contain a BehavioralSpec with steps (MS-13-004)
# ---------------------------------------------------------------------------


def _scenario_start_group(with_behavioral_spec: bool):
    """Return a minimal spec file with one scenario_start group.

    When ``with_behavioral_spec`` is True the group contains a BehavioralSpec
    item with steps; otherwise it contains only a StatementSpec item.
    """
    if with_behavioral_spec:
        workflow_item = {
            "id": "SCN-01-002",
            "priority": "MUST",
            "kind": "project",
            "statement": "SCN-01-002 MUST execute the scenario workflow",
            "rationale": "ECA required",
            "tags": ["demo"],
            "preconditions": [{"description": "Actors running"}],
            "steps": [
                {"order": 1, "actor": "finder", "action": "Submit report"}
            ],
            "postconditions": [{"description": "Case created"}],
        }
    else:
        workflow_item = {
            "id": "SCN-01-002",
            "priority": "MUST",
            "kind": "project",
            "statement": "SCN-01-002 MUST reach final state VFDPxa",
            "rationale": "Terminal state required",
            "tags": ["demo"],
        }

    return {
        "id": "SCN",
        "title": "Scenario Spec",
        "description": "Scenario spec file",
        "version": "0.1",
        "scope": ["prototype"],
        "groups": [
            {
                "id": "SCN-01",
                "title": "FV Scenario",
                "trigger": {"type": "scenario_start", "value": "fv"},
                "specs": [
                    {
                        "id": "SCN-01-001",
                        "priority": "MUST",
                        "kind": "project",
                        "statement": "SCN-01-001 MUST reach VFDPxa",
                        "rationale": "Terminal state",
                        "tags": ["demo"],
                    },
                    workflow_item,
                ],
            }
        ],
    }


def test_scenario_start_with_behavioral_spec_passes(tmp_path, capsys):
    """scenario_start group with a BehavioralSpec+steps item must pass."""
    _write_yaml(tmp_path, _scenario_start_group(with_behavioral_spec=True))
    result = lint(tmp_path)
    captured = capsys.readouterr()
    assert result == 0
    assert "MS-13-004" not in captured.err


def test_scenario_start_without_behavioral_spec_fails(tmp_path, capsys):
    """scenario_start group with only StatementSpec items must be a hard error."""
    _write_yaml(tmp_path, _scenario_start_group(with_behavioral_spec=False))
    result = lint(tmp_path)
    captured = capsys.readouterr()
    assert result == 1
    assert "SCN-01" in captured.err
    assert "MS-13-004" in captured.err


def test_non_scenario_start_group_not_checked(tmp_path, capsys):
    """Groups without a scenario_start trigger are not subject to MS-13-004."""
    data = _minimal_spec()  # no trigger on group TST-01
    _write_yaml(tmp_path, data)
    result = lint(tmp_path)
    captured = capsys.readouterr()
    assert result == 0
    assert "MS-13-004" not in captured.err


# ---------------------------------------------------------------------------
# ADR status frontmatter (MS-14-001 hard, MS-14-002 advisory) — ADR-0041
# ---------------------------------------------------------------------------


def _write_adr(adr_dir, num, status=None, body=""):
    """Write an ADR file; omit the status line entirely when status is None."""
    fm = (
        f"---\nstatus: {status}\n---\n" if status is not None else "---\n---\n"
    )
    (adr_dir / f"{num}-stub.md").write_text(f"{fm}# ADR-{num}\n{body}\n")


def test_lint_adr_missing_status_is_hard_error(tmp_path, capsys):
    """An ADR with no status frontmatter is a hard error (MS-14-001)."""
    _write_yaml(tmp_path, _minimal_spec())
    adr_dir = _make_adr_dir(tmp_path)
    _write_adr(adr_dir, "0099", status=None)
    result = lint(tmp_path, adr_dir=adr_dir)
    captured = capsys.readouterr()
    assert result == 1
    assert "MS-14-001" in captured.err
    assert "0099" in captured.err


def test_lint_adr_invalid_status_is_hard_error(tmp_path, capsys):
    """An ADR with an unknown status value is a hard error (MS-14-001)."""
    _write_yaml(tmp_path, _minimal_spec())
    adr_dir = _make_adr_dir(tmp_path)
    _write_adr(adr_dir, "0099", status="kinda-accepted")
    result = lint(tmp_path, adr_dir=adr_dir)
    captured = capsys.readouterr()
    assert result == 1
    assert "MS-14-001" in captured.err


def test_lint_adr_superseded_status_ok(tmp_path):
    """A superseded ADR with a resolvable superseded_by target is valid."""
    _write_yaml(tmp_path, _minimal_spec())
    adr_dir = _make_adr_dir(tmp_path, ["0100"])  # replacement exists
    (adr_dir / "0099-stub.md").write_text(
        "---\nstatus: superseded\nsuperseded_by: 0100-stub.md\n---\n# x\n"
    )
    result = lint(tmp_path, adr_dir=adr_dir)
    assert result == 0


def test_lint_adr_superseded_inline_form_ok(tmp_path):
    """The inline 'superseded by <link>' MADR form is accepted and resolved."""
    _write_yaml(tmp_path, _minimal_spec())
    adr_dir = _make_adr_dir(tmp_path, ["0100"])
    (adr_dir / "0099-stub.md").write_text(
        "---\nstatus: superseded by 0100-stub.md\n---\n# x\n"
    )
    result = lint(tmp_path, adr_dir=adr_dir)
    assert result == 0


def test_lint_adr_superseded_without_target_is_hard_error(tmp_path, capsys):
    """A retired ADR missing superseded_by is a hard error (MS-14-004)."""
    _write_yaml(tmp_path, _minimal_spec())
    adr_dir = _make_adr_dir(tmp_path)
    (adr_dir / "0099-stub.md").write_text(
        "---\nstatus: superseded\n---\n# x\n"
    )
    result = lint(tmp_path, adr_dir=adr_dir)
    captured = capsys.readouterr()
    assert result == 1
    assert "superseded_by" in captured.err


def test_lint_adr_accepted_with_provisional_prose_warns(tmp_path, capsys):
    """status: accepted + provisional prose is an advisory warning (MS-14-002)."""
    _write_yaml(tmp_path, _minimal_spec())
    adr_dir = _make_adr_dir(tmp_path)
    _write_adr(
        adr_dir,
        "0099",
        status="accepted",
        body="This design is formed in sand.",
    )
    result = lint(tmp_path, adr_dir=adr_dir)
    captured = capsys.readouterr()
    assert result == 0  # advisory, not a hard error
    assert "MS-14-002" in captured.out
    assert "[WARN]" in captured.out


def test_lint_adr_accepted_provisional_status_no_warn(tmp_path, capsys):
    """accepted-provisional + provisional prose is consistent — no warning."""
    _write_yaml(tmp_path, _minimal_spec())
    adr_dir = _make_adr_dir(tmp_path)
    _write_adr(
        adr_dir,
        "0099",
        status="accepted-provisional",
        body="This design is formed in sand.",
    )
    result = lint(tmp_path, adr_dir=adr_dir)
    captured = capsys.readouterr()
    assert result == 0
    assert "MS-14-002" not in captured.out


# ---------------------------------------------------------------------------
# Structured adr: field references (SR-02-020) — hard error on dangling target
# ---------------------------------------------------------------------------


def test_lint_structured_adr_ref_missing_is_hard_error(tmp_path, capsys):
    """A structured adr: target with no ADR file is a hard error."""
    data = _minimal_spec(extra={"adr": ["ADR-0099"]})
    _write_yaml(tmp_path, data)
    adr_dir = _make_adr_dir(tmp_path)  # no 0099 file
    result = lint(tmp_path, adr_dir=adr_dir)
    captured = capsys.readouterr()
    assert result == 1
    assert "ADR-0099" in captured.err


def test_lint_structured_adr_ref_present_ok(tmp_path, capsys):
    """A structured adr: target that resolves to a file is clean."""
    data = _minimal_spec(extra={"adr": ["ADR-0099"]})
    _write_yaml(tmp_path, data)
    adr_dir = _make_adr_dir(tmp_path, ["0099"])
    result = lint(tmp_path, adr_dir=adr_dir)
    assert result == 0


def test_lint_structured_adr_ref_resolves_to_archived(tmp_path):
    """A structured adr: target in docs/adr/archived/ resolves (no error)."""
    data = _minimal_spec(extra={"adr": ["ADR-0099"]})
    _write_yaml(tmp_path, data)
    adr_dir = _make_adr_dir(tmp_path)
    archived = adr_dir / "archived"
    archived.mkdir()
    (archived / "0099-stub.md").write_text(
        "---\nstatus: deprecated\nsuperseded_by: 0100-stub.md\n---\n# x\n"
    )
    (adr_dir / "0100-stub.md").write_text("---\nstatus: accepted\n---\n# x\n")
    result = lint(tmp_path, adr_dir=adr_dir)
    assert result == 0


def test_lint_adr_status_prose_suppress(tmp_path, capsys):
    """lint_suppress: [status_prose_contradiction] silences the MS-14-002 warn."""
    _write_yaml(tmp_path, _minimal_spec())
    adr_dir = _make_adr_dir(tmp_path)
    (adr_dir / "0099-stub.md").write_text(
        "---\nstatus: accepted\n"
        "lint_suppress: [status_prose_contradiction]\n---\n"
        "# ADR-0099\nThis ADR is formed in sand.\n"
    )
    result = lint(tmp_path, adr_dir=adr_dir)
    captured = capsys.readouterr()
    assert result == 0
    assert "MS-14-002" not in captured.out


# ---------------------------------------------------------------------------
# MS-15-001: phantom path references in spec statements
# ---------------------------------------------------------------------------


def _repo_with_specs(tmp_path):
    """Return (repo_root, spec_dir) — lint() treats spec_dir.parent as the root.

    Creates the top-level directories the phantom-path tests reference, so a
    match is exercised against the existence check rather than being skipped as
    a package-relative illustration.
    """
    spec_dir = tmp_path / "specs"
    spec_dir.mkdir()
    for name in ("vultron", "test", ".claude", "docs"):
        (tmp_path / name).mkdir()
    return tmp_path, spec_dir


def test_lint_phantom_path_is_hard_error(tmp_path, capsys):
    """A statement naming a non-existent repo-relative path fails (MS-15-001)."""
    _, spec_dir = _repo_with_specs(tmp_path)
    data = _minimal_spec()
    data["groups"][0]["specs"][0][
        "statement"
    ] = "The harness MUST be registered in `vultron/nope.py`"
    _write_yaml(spec_dir, data)
    result = lint(spec_dir)
    captured = capsys.readouterr()
    assert result == 1
    assert "MS-15-001" in captured.err
    assert "vultron/nope.py" in captured.err


def test_lint_phantom_path_existing_file_passes(tmp_path):
    """A statement naming a path that exists is accepted."""
    repo, spec_dir = _repo_with_specs(tmp_path)
    (repo / "vultron" / "real.py").write_text("x = 1\n")
    data = _minimal_spec()
    data["groups"][0]["specs"][0][
        "statement"
    ] = "The thing MUST live in `vultron/real.py`"
    _write_yaml(spec_dir, data)
    assert lint(spec_dir) == 0


def test_lint_phantom_path_placeholder_exempt(tmp_path):
    """Placeholder path forms describe a shape, not a file, and are exempt."""
    _, spec_dir = _repo_with_specs(tmp_path)
    data = _minimal_spec()
    data["groups"][0]["specs"][0][
        "statement"
    ] = "Each scenario MUST have a `test/ci/invariants/test_XXX_invariants.py`"
    _write_yaml(spec_dir, data)
    assert lint(spec_dir) == 0


def test_lint_phantom_path_without_placeholder_token_fails(tmp_path):
    """The same path minus the placeholder token is checked and fails.

    Guards the exemption above against becoming vacuous: `test/` exists in the
    fixture repo, so this path reaches the existence check.
    """
    _, spec_dir = _repo_with_specs(tmp_path)
    data = _minimal_spec()
    data["groups"][0]["specs"][0][
        "statement"
    ] = "Each scenario MUST have a `test/ci/invariants/test_fv_invariants.py`"
    _write_yaml(spec_dir, data)
    assert lint(spec_dir) == 1


def test_lint_phantom_path_placeholder_basename_exempt(tmp_path):
    """Placeholder basenames are exempt, but only as a whole path segment."""
    repo, spec_dir = _repo_with_specs(tmp_path)
    (repo / "notes").mkdir()
    data = _minimal_spec()
    data["groups"][0]["specs"][0][
        "statement"
    ] = "A new note MUST be created at `notes/new-topic.md`"
    _write_yaml(spec_dir, data)
    assert lint(spec_dir) == 0


def test_lint_phantom_path_placeholder_basename_not_a_substring(tmp_path):
    """A real path merely *starting* with a placeholder name is still checked."""
    repo, spec_dir = _repo_with_specs(tmp_path)
    (repo / "notes").mkdir()
    data = _minimal_spec()
    data["groups"][0]["specs"][0][
        "statement"
    ] = "The workflow MUST be documented in `notes/new-topic-workflow.md`"
    _write_yaml(spec_dir, data)
    assert lint(spec_dir) == 1


def test_lint_phantom_path_dot_directory_is_checked(tmp_path, capsys):
    """Dot-directories such as `.claude/` are enforced, not silently skipped."""
    _, spec_dir = _repo_with_specs(tmp_path)
    data = _minimal_spec()
    data["groups"][0]["specs"][0][
        "statement"
    ] = "Linting MUST run via `.claude/skills/format-markdown/SKILL.md`"
    _write_yaml(spec_dir, data)
    result = lint(spec_dir)
    captured = capsys.readouterr()
    assert result == 1
    assert ".claude/skills/format-markdown/SKILL.md" in captured.err


def test_lint_phantom_path_dot_directory_existing_passes(tmp_path):
    """A dot-directory path that does exist is accepted."""
    repo, spec_dir = _repo_with_specs(tmp_path)
    skill = repo / ".claude" / "skills" / "format-markdown"
    skill.mkdir(parents=True)
    (skill / "SKILL.md").write_text("# skill\n")
    data = _minimal_spec()
    data["groups"][0]["specs"][0][
        "statement"
    ] = "Linting MUST run via `.claude/skills/format-markdown/SKILL.md`"
    _write_yaml(spec_dir, data)
    assert lint(spec_dir) == 0


def test_lint_phantom_path_package_relative_resolves_as_suffix(tmp_path):
    """A package-relative illustration resolves against a real file's suffix."""
    repo, spec_dir = _repo_with_specs(tmp_path)
    pkg = repo / "vultron" / "wire" / "received"
    pkg.mkdir(parents=True)
    (pkg / "sync.py").write_text("x = 1\n")
    data = _minimal_spec()
    data["groups"][0]["specs"][0][
        "statement"
    ] = "Patterns MUST be defined in `received/sync.py`"
    _write_yaml(spec_dir, data)
    assert lint(spec_dir) == 0


def test_lint_phantom_path_package_relative_unresolvable_fails(tmp_path):
    """A package-relative path matching nothing in the tree is still an error."""
    _, spec_dir = _repo_with_specs(tmp_path)
    data = _minimal_spec()
    data["groups"][0]["specs"][0][
        "statement"
    ] = "Patterns MUST be defined in `received/sync.py`"
    _write_yaml(spec_dir, data)
    assert lint(spec_dir) == 1


def test_lint_phantom_path_mistyped_leading_segment_fails(tmp_path, capsys):
    """A mistyped first segment does not escape via the suffix path.

    `tests/` (plural) is not a top-level dir, so the match is resolved as a
    suffix — and no file ends with `tests/ci/common.py`, so it errors.
    """
    repo, spec_dir = _repo_with_specs(tmp_path)
    real = repo / "test" / "ci"
    real.mkdir(parents=True)
    (real / "common.py").write_text("x = 1\n")
    data = _minimal_spec()
    data["groups"][0]["specs"][0][
        "statement"
    ] = "Checks MUST live in `tests/ci/common.py`"
    _write_yaml(spec_dir, data)
    result = lint(spec_dir)
    captured = capsys.readouterr()
    assert result == 1
    assert "tests/ci/common.py" in captured.err


def test_lint_phantom_path_suffix_ignores_build_artifacts(tmp_path):
    """A path satisfied only inside `.venv/` or `__pycache__/` is not resolved."""
    repo, spec_dir = _repo_with_specs(tmp_path)
    vendored = repo / ".venv" / "lib" / "received"
    vendored.mkdir(parents=True)
    (vendored / "sync.py").write_text("x = 1\n")
    data = _minimal_spec()
    data["groups"][0]["specs"][0][
        "statement"
    ] = "Patterns MUST be defined in `received/sync.py`"
    _write_yaml(spec_dir, data)
    assert lint(spec_dir) == 1


def test_lint_phantom_path_absolute_rejected(tmp_path, capsys):
    """An absolute path is rejected outright, not exempted."""
    _, spec_dir = _repo_with_specs(tmp_path)
    data = _minimal_spec()
    data["groups"][0]["specs"][0][
        "statement"
    ] = "Config MUST be read from `/etc/vultron/settings.yaml`"
    _write_yaml(spec_dir, data)
    result = lint(spec_dir)
    captured = capsys.readouterr()
    assert result == 1
    assert "not a valid repo-relative path" in captured.err


def test_lint_phantom_path_parent_traversal_rejected(tmp_path, capsys):
    """A `..` segment is rejected even when it resolves on the filesystem."""
    repo, spec_dir = _repo_with_specs(tmp_path)
    (repo / "vultron" / "real.py").write_text("x = 1\n")
    data = _minimal_spec()
    data["groups"][0]["specs"][0][
        "statement"
    ] = "The thing MUST live in `test/../vultron/real.py`"
    _write_yaml(spec_dir, data)
    result = lint(spec_dir)
    captured = capsys.readouterr()
    assert result == 1
    assert "not a valid repo-relative path" in captured.err


def test_lint_phantom_path_rationale_not_scanned(tmp_path):
    """rationale narrates history and may cite paths that no longer exist."""
    _, spec_dir = _repo_with_specs(tmp_path)
    data = _minimal_spec()
    data["groups"][0]["specs"][0][
        "rationale"
    ] = "`vultron/old_config.py` has been converted to a package."
    _write_yaml(spec_dir, data)
    assert lint(spec_dir) == 0


def test_lint_phantom_path_suppress(tmp_path, capsys):
    """lint_suppress: [phantom_path_ref] allows a deliberate forward reference."""
    _, spec_dir = _repo_with_specs(tmp_path)
    data = _minimal_spec(extra={"lint_suppress": ["phantom_path_ref"]})
    data["groups"][0]["specs"][0][
        "statement"
    ] = "A new module MUST be created at `vultron/planned.py`"
    _write_yaml(spec_dir, data)
    result = lint(spec_dir)
    captured = capsys.readouterr()
    assert result == 0
    assert "MS-15-001" not in captured.err


def test_lint_phantom_path_in_verification_is_hard_error(tmp_path, capsys):
    """A verification field naming a non-existent path fails (MS-15-001)."""
    _, spec_dir = _repo_with_specs(tmp_path)
    data = _minimal_spec()
    data["groups"][0]["specs"][0][
        "verification"
    ] = "Assert via `vultron/nope.py` that the invariant holds."
    _write_yaml(spec_dir, data)
    result = lint(spec_dir)
    captured = capsys.readouterr()
    assert result == 1
    assert "MS-15-001" in captured.err
    assert "vultron/nope.py" in captured.err


def test_lint_phantom_path_in_verification_existing_passes(tmp_path):
    """A verification field naming an existing path is accepted."""
    repo, spec_dir = _repo_with_specs(tmp_path)
    (repo / "vultron" / "real.py").write_text("x = 1\n")
    data = _minimal_spec()
    data["groups"][0]["specs"][0][
        "verification"
    ] = "Assert via `vultron/real.py` that the invariant holds."
    _write_yaml(spec_dir, data)
    assert lint(spec_dir) == 0


def test_lint_phantom_path_verification_suppress(tmp_path, capsys):
    """lint_suppress: [phantom_path_ref] exempts phantom paths in verification."""
    _, spec_dir = _repo_with_specs(tmp_path)
    data = _minimal_spec(extra={"lint_suppress": ["phantom_path_ref"]})
    data["groups"][0]["specs"][0][
        "verification"
    ] = "A test at `vultron/future.py` will assert this."
    _write_yaml(spec_dir, data)
    result = lint(spec_dir)
    captured = capsys.readouterr()
    assert result == 0
    assert "MS-15-001" not in captured.err


# ---------------------------------------------------------------------------
# MS-15-001: directory reference checks
# ---------------------------------------------------------------------------


def test_lint_phantom_dir_is_hard_error(tmp_path, capsys):
    """A statement naming a non-existent multi-segment directory fails (MS-15-001)."""
    _, spec_dir = _repo_with_specs(tmp_path)
    data = _minimal_spec()
    data["groups"][0]["specs"][0][
        "statement"
    ] = "Helpers MUST live in `vultron/missing/`"
    _write_yaml(spec_dir, data)
    result = lint(spec_dir)
    captured = capsys.readouterr()
    assert result == 1
    assert "MS-15-001" in captured.err
    assert "vultron/missing/" in captured.err


def test_lint_phantom_dir_existing_passes(tmp_path):
    """A statement naming an existing directory passes."""
    repo, spec_dir = _repo_with_specs(tmp_path)
    (repo / "vultron" / "real").mkdir()
    data = _minimal_spec()
    data["groups"][0]["specs"][0][
        "statement"
    ] = "Helpers MUST live in `vultron/real/`"
    _write_yaml(spec_dir, data)
    assert lint(spec_dir) == 0


def test_lint_phantom_dir_single_segment_not_checked(tmp_path):
    """A single-segment directory ref is not checked — high false-positive risk."""
    _, spec_dir = _repo_with_specs(tmp_path)
    data = _minimal_spec()
    data["groups"][0]["specs"][0][
        "statement"
    ] = "Output MUST be written to the `devlogs/` directory"
    _write_yaml(spec_dir, data)
    assert lint(spec_dir) == 0


def test_lint_phantom_dir_placeholder_exempt(tmp_path):
    """A directory ref containing a placeholder token is exempt."""
    _, spec_dir = _repo_with_specs(tmp_path)
    data = _minimal_spec()
    data["groups"][0]["specs"][0][
        "statement"
    ] = "Each run MUST write to `plan/history/YYMM/`"
    _write_yaml(spec_dir, data)
    assert lint(spec_dir) == 0


def test_lint_phantom_dir_placeholder_negative(tmp_path):
    """The same path without the placeholder token fails.

    Guards the exemption above against becoming vacuous: the directory
    `plan/history/2601/` is expected to not exist in the fixture tree.
    """
    _, spec_dir = _repo_with_specs(tmp_path)
    (tmp_path / "plan").mkdir()
    (tmp_path / "plan" / "history").mkdir()
    data = _minimal_spec()
    data["groups"][0]["specs"][0][
        "statement"
    ] = "Each run MUST write to `plan/history/2601/`"
    _write_yaml(spec_dir, data)
    assert lint(spec_dir) == 1


def test_lint_phantom_dir_package_relative_resolves(tmp_path):
    """A package-relative directory resolves against a real directory suffix."""
    repo, spec_dir = _repo_with_specs(tmp_path)
    (repo / "vultron" / "wire" / "received").mkdir(parents=True)
    data = _minimal_spec()
    data["groups"][0]["specs"][0][
        "statement"
    ] = "Handlers MUST live in `wire/received/`"
    _write_yaml(spec_dir, data)
    assert lint(spec_dir) == 0


def test_lint_phantom_dir_package_relative_fails(tmp_path):
    """A package-relative directory matching nothing in the tree fails."""
    _, spec_dir = _repo_with_specs(tmp_path)
    data = _minimal_spec()
    data["groups"][0]["specs"][0][
        "statement"
    ] = "Handlers MUST live in `wire/received/`"
    _write_yaml(spec_dir, data)
    assert lint(spec_dir) == 1


def test_lint_phantom_dir_suppress(tmp_path):
    """lint_suppress: [phantom_path_ref] exempts phantom directory refs."""
    _, spec_dir = _repo_with_specs(tmp_path)
    data = _minimal_spec(extra={"lint_suppress": ["phantom_path_ref"]})
    data["groups"][0]["specs"][0][
        "statement"
    ] = "Helpers MUST live in `vultron/planned/`"
    _write_yaml(spec_dir, data)
    assert lint(spec_dir) == 0


def test_lint_phantom_dir_in_verification_is_hard_error(tmp_path, capsys):
    """A verification field naming a non-existent directory fails (MS-15-001)."""
    _, spec_dir = _repo_with_specs(tmp_path)
    data = _minimal_spec()
    data["groups"][0]["specs"][0][
        "verification"
    ] = "Assert via `test/ci/invariants/` that the invariant holds."
    _write_yaml(spec_dir, data)
    result = lint(spec_dir)
    captured = capsys.readouterr()
    assert result == 1
    assert "MS-15-001" in captured.err
    assert "test/ci/invariants/" in captured.err


# ---------------------------------------------------------------------------
# MS-15-001: behavioral step / precondition / postcondition scanning
# ---------------------------------------------------------------------------


def _minimal_behavioral_spec_data(
    step_action="Execute workflow",
    precondition_desc="System is ready",
    postcondition_desc="Workflow complete",
):
    """Return a minimal spec file containing one BehavioralSpec item."""
    spec = {
        "id": "TST-01-001",
        "priority": "MUST",
        "kind": "protocol",
        "statement": "TST-01-001 MUST execute the workflow",
        "rationale": "ECA required",
        "tags": ["testing"],
        "preconditions": [{"description": precondition_desc}],
        "steps": [{"order": 1, "actor": "finder", "action": step_action}],
        "postconditions": [{"description": postcondition_desc}],
    }
    return {
        "id": "TST",
        "title": "Test File",
        "description": "Test spec file",
        "version": "0.1",
        "scope": ["production"],
        "groups": [{"id": "TST-01", "title": "Group", "specs": [spec]}],
    }


def test_lint_phantom_dir_in_behavioral_step_is_hard_error(tmp_path, capsys):
    """A behavioral step action naming a non-existent directory fails (MS-15-001)."""
    _, spec_dir = _repo_with_specs(tmp_path)
    data = _minimal_behavioral_spec_data(
        step_action="Write output to `vultron/output/`"
    )
    _write_yaml(spec_dir, data)
    result = lint(spec_dir)
    captured = capsys.readouterr()
    assert result == 1
    assert "MS-15-001" in captured.err
    assert "vultron/output/" in captured.err


def test_lint_phantom_path_in_behavioral_step_is_hard_error(tmp_path, capsys):
    """A behavioral step action naming a non-existent path fails (MS-15-001)."""
    _, spec_dir = _repo_with_specs(tmp_path)
    data = _minimal_behavioral_spec_data(
        step_action="Register via `vultron/nope.py`"
    )
    _write_yaml(spec_dir, data)
    result = lint(spec_dir)
    captured = capsys.readouterr()
    assert result == 1
    assert "MS-15-001" in captured.err
    assert "vultron/nope.py" in captured.err


def test_lint_phantom_path_in_behavioral_step_existing_passes(tmp_path):
    """A behavioral step action naming an existing file passes."""
    repo, spec_dir = _repo_with_specs(tmp_path)
    (repo / "vultron" / "real.py").write_text("x = 1\n")
    data = _minimal_behavioral_spec_data(
        step_action="Register via `vultron/real.py`"
    )
    _write_yaml(spec_dir, data)
    assert lint(spec_dir) == 0


def test_lint_phantom_path_in_precondition_is_hard_error(tmp_path, capsys):
    """A precondition description naming a non-existent path fails (MS-15-001)."""
    _, spec_dir = _repo_with_specs(tmp_path)
    data = _minimal_behavioral_spec_data(
        precondition_desc="File `vultron/missing.py` is loaded"
    )
    _write_yaml(spec_dir, data)
    result = lint(spec_dir)
    captured = capsys.readouterr()
    assert result == 1
    assert "MS-15-001" in captured.err
    assert "vultron/missing.py" in captured.err


def test_lint_phantom_path_in_postcondition_is_hard_error(tmp_path, capsys):
    """A postcondition description naming a non-existent path fails (MS-15-001)."""
    _, spec_dir = _repo_with_specs(tmp_path)
    data = _minimal_behavioral_spec_data(
        postcondition_desc="Result written to `vultron/missing.py`"
    )
    _write_yaml(spec_dir, data)
    result = lint(spec_dir)
    captured = capsys.readouterr()
    assert result == 1
    assert "MS-15-001" in captured.err
    assert "vultron/missing.py" in captured.err


def test_lint_phantom_path_behavioral_step_suppress(tmp_path):
    """lint_suppress: [phantom_path_ref] exempts phantom paths in behavioral fields."""
    _, spec_dir = _repo_with_specs(tmp_path)
    spec = {
        "id": "TST-01-001",
        "priority": "MUST",
        "kind": "protocol",
        "statement": "TST-01-001 MUST execute",
        "rationale": "Required",
        "tags": ["testing"],
        "preconditions": [{"description": "System ready"}],
        "steps": [
            {
                "order": 1,
                "actor": "system",
                "action": "Create `vultron/future.py`",
            }
        ],
        "postconditions": [{"description": "Complete"}],
        "lint_suppress": ["phantom_path_ref"],
    }
    data = {
        "id": "TST",
        "title": "T",
        "description": "T",
        "version": "0.1",
        "scope": ["production"],
        "groups": [{"id": "TST-01", "title": "G", "specs": [spec]}],
    }
    _write_yaml(spec_dir, data)
    assert lint(spec_dir) == 0
