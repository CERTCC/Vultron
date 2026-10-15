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
"""Tests for ``pr-body-lint`` (:mod:`vultron.metadata.planning.pr_body_lint`).

One class per rule, a check that ``pr-body-guide.md`` lists exactly the tool's
rules, the CLI's fact gathering, and the skills that run it.

Specs: PAD-20-001 through PAD-20-005, PD-03-008.
"""

from __future__ import annotations

import json
import re
import subprocess
from collections.abc import Sequence
from pathlib import Path

import pytest

from test.metadata._git_repo import commit_base, git
from vultron.metadata.planning.pr_body_lint import (
    DOCS_PLACEHOLDER,
    RULES,
    BodyFacts,
    PrType,
    Stage,
    lint_body,
    main,
)

REPO_ROOT = Path(__file__).parents[2]
SKILLS = REPO_ROOT / ".agents" / "skills"

MANIFEST = """Spec manifest
Loaded (floor): PAD-18-001
Loaded (cross-cutting): ARCH, CS
Loaded (selected): SR-12 — the backstop
Considered, skipped: PAD-15 — bundle selection untouched"""

ATTRIBUTION = "🤖 Generated with [Claude Code](https://claude.com/claude-code)"


def _body(
    *,
    top: str = "- Closes #1\n- Closes #2",
    summary: str = "Adds a thing.\n\nIssues: closed 2, opened 0",
    specs: str | None = MANIFEST,
    amended: str | None = None,
    docs: str | None = "Docs: no docs impact — internal tooling only",
    verification: str | None = "- All tests pass",
    tail: str = ATTRIBUTION,
) -> str:
    parts = [top, f"## Summary\n\n{summary}", "## Changes\n\n- a change"]
    if specs is not None:
        parts.append(f"## Specs\n\n{specs}")
    if amended is not None:
        parts.append(f"## Spec amended\n\n{amended}")
    if docs is not None:
        parts.append(f"## Docs\n\n{docs}")
    if verification is not None:
        parts.append(f"## Verification\n\n{verification}")
    parts.append(tail)
    return "\n\n".join(parts) + "\n"


IMPL = BodyFacts(pr_type=PrType.IMPLEMENTATION, py_changed=True)
FINAL = BodyFacts(
    pr_type=PrType.IMPLEMENTATION, py_changed=True, stage=Stage.FINAL
)
DOCS = BodyFacts(pr_type=PrType.DOCS, py_changed=False)


def _ids(text: str, facts: BodyFacts = IMPL) -> list[str]:
    return [f.rule_id for f in lint_body(text, facts)]


def test_a_well_formed_body_has_no_findings():
    assert lint_body(_body(), FINAL) == []


def test_a_well_formed_docs_body_has_no_findings():
    body = _body(
        summary="Edits a note.", specs=None, docs=None, verification=None
    )
    assert lint_body(body, DOCS) == []


@pytest.mark.spec("PAD-20-001")
class TestGuideListsTheRules:
    """pr-body-guide.md's rule table and ``RULES`` are one list."""

    @staticmethod
    def _guide_rows() -> list[tuple[str, str]]:
        guide = (SKILLS / "shared" / "pr-body-guide.md").read_text()
        return re.findall(r"^\| (PRB-\d\d) \| ([a-z-]+) \|", guide, re.M)

    def test_every_rule_is_in_the_guide(self):
        assert [(r.rule_id, r.name) for r in RULES] == self._guide_rows()

    def test_rule_ids_are_unique_and_ordered(self):
        ids = [r.rule_id for r in RULES]
        assert ids == sorted(set(ids))


@pytest.mark.spec("PAD-20-001")
class TestClosesFirst:
    def test_a_closing_reference_after_the_opening_block_is_found(self):
        body = _body(
            summary="Adds a thing; fixes #9.\n\nIssues: closed 2, opened 0"
        )
        assert _ids(body) == ["PRB-01"]

    def test_closing_references_below_a_heading_are_found(self):
        body = "## Summary\n\n- Closes #1\n\n## Changes\n\n- x\n"
        assert "PRB-01" in _ids(body, DOCS)

    def test_a_reference_in_a_code_fence_is_not_a_closing_reference(self):
        body = _body(verification="```text\nCloses #5\n```")
        assert _ids(body) == []

    def test_a_nested_fence_does_not_end_the_outer_block(self):
        fence = "````md\n```\nCloses #5\n```\n## Not a section\n````"
        assert _ids(_body(verification=fence)) == []

    def test_an_html_comment_before_the_closes_lines_is_ignored(self):
        body = _body(top="<!-- note -->\n- Closes #1")
        assert _ids(body) == []


@pytest.mark.spec("PAD-20-001")
class TestClosesOnePerLine:
    def test_two_references_on_one_line_are_found(self):
        assert _ids(_body(top="- Closes #1, closes #2")) == ["PRB-02"]

    def test_a_reference_without_the_bullet_is_found(self):
        assert _ids(_body(top="Closes #1")) == ["PRB-02"]

    def test_fixes_and_resolves_bullets_pass(self):
        assert _ids(_body(top="- Fixes #1\n- Resolves #2")) == []


@pytest.mark.spec("PAD-20-001")
class TestRequiredSections:
    def test_missing_summary_and_changes_are_found(self):
        body = "- Closes #1\n\n## Specs\n\nnothing\n"
        found = lint_body(body, DOCS)
        assert [f.rule_id for f in found] == ["PRB-03", "PRB-03"]

    def test_a_heading_inside_a_fence_is_not_a_section(self):
        body = "- Closes #1\n\n```md\n## Summary\n\n## Changes\n```\n"
        assert _ids(body, DOCS) == ["PRB-03", "PRB-03"]


@pytest.mark.spec("PAD-20-001")
class TestIssuesLine:
    def test_an_implementation_summary_without_it_is_found(self):
        assert _ids(_body(summary="Adds a thing.")) == ["PRB-04"]

    def test_it_must_be_the_last_line_of_the_summary(self):
        summary = "Issues: closed 1, opened 0\n\nAdds a thing."
        assert _ids(_body(summary=summary)) == ["PRB-04"]

    def test_a_listed_opened_issue_passes(self):
        summary = "Adds a thing.\n\nIssues: closed 2, opened 1 (#4402 debt)"
        assert _ids(_body(summary=summary)) == []

    def test_a_docs_pr_needs_none(self):
        assert _ids(_body(summary="Edits a note.", specs=None), DOCS) == []


@pytest.mark.spec("PAD-20-001")
class TestSpecsManifest:
    def test_a_missing_section_is_found(self):
        assert _ids(_body(specs=None)) == ["PRB-05"]

    def test_a_bare_id_list_is_found_once_per_missing_line(self):
        assert _ids(_body(specs="PAD-18-001, SR-12")) == ["PRB-05"] * 4

    def test_an_id_range_is_found(self):
        specs = MANIFEST.replace("ARCH, CS", "ARCH-01..03")
        assert _ids(_body(specs=specs)) == ["PRB-05"]

    def test_a_manifest_in_a_fence_or_bullets_passes(self):
        bulleted = "\n".join(f"- {ln}" for ln in MANIFEST.splitlines())
        assert _ids(_body(specs=f"```text\n{MANIFEST}\n```")) == []
        assert _ids(_body(specs=bulleted)) == []

    def test_a_docs_pr_needs_none(self):
        assert _ids(_body(summary="x", specs=None), DOCS) == []


@pytest.mark.spec("PAD-20-002")
class TestManifestVerbatim:
    def _facts(self, manifest: str) -> BodyFacts:
        return BodyFacts(
            pr_type=PrType.IMPLEMENTATION, py_changed=True, manifest=manifest
        )

    def test_the_pasted_manifest_passes(self):
        assert lint_body(_body(), self._facts(MANIFEST)) == []

    def test_a_retyped_line_is_found(self):
        retyped = MANIFEST.replace("PAD-18-001", "PAD-18-001, PAD-18-008")
        found = lint_body(_body(), self._facts(retyped))
        assert [f.rule_id for f in found] == ["PRB-06"]
        assert "PAD-18-008" in found[0].message


@pytest.mark.spec("PAD-20-001")
class TestVerificationSection:
    def test_missing_when_python_changed_is_found(self):
        assert _ids(_body(verification=None)) == ["PRB-07"]

    def test_not_needed_when_no_python_changed(self):
        facts = BodyFacts(pr_type=PrType.IMPLEMENTATION, py_changed=False)
        assert _ids(_body(verification=None), facts) == []


@pytest.mark.spec("PAD-20-005")
@pytest.mark.spec("PD-03-008")
class TestDocsLine:
    def test_a_missing_line_is_found(self):
        assert _ids(_body(docs=None)) == ["PRB-08"]

    def test_the_placeholder_passes_before_the_push(self):
        assert _ids(_body(docs=DOCS_PLACEHOLDER), IMPL) == []

    def test_the_placeholder_fails_at_the_final_stage(self):
        assert _ids(_body(docs=DOCS_PLACEHOLDER), FINAL) == ["PRB-08"]

    @pytest.mark.parametrize(
        "line",
        [
            "Docs: updated docs/a.md, docs/b.md",
            "Docs: no docs impact — internal refactor",
            "Docs: deferred to #12",
            "Docs: updated docs/a.md; deferred to #12",
        ],
    )
    def test_final_forms_pass(self, line):
        assert _ids(_body(docs=line), FINAL) == []

    @pytest.mark.parametrize(
        "line", ["Docs: none needed", "Docs: no docs impact", "Docs: n/a"]
    )
    def test_other_forms_fail_at_the_final_stage(self, line):
        assert _ids(_body(docs=line), FINAL) == ["PRB-08"]

    def test_a_docs_pr_closing_a_work_item_needs_the_line(self):
        facts = BodyFacts(
            pr_type=PrType.DOCS, py_changed=False, closes_work_item=True
        )
        body = _body(summary="x", specs=None, docs=None, verification=None)
        assert _ids(body, facts) == ["PRB-08"]


@pytest.mark.spec("PAD-20-001")
class TestSpecAmended:
    def _facts(self, stage: Stage = Stage.PRE_PUSH) -> BodyFacts:
        return BodyFacts(
            pr_type=PrType.IMPLEMENTATION,
            py_changed=True,
            amended_ids=("PAD-18-001", "PAD-18-008"),
            stage=stage,
        )

    def test_a_missing_section_is_found(self):
        assert _ids(_body(), self._facts()) == ["PRB-09"]

    def test_a_missing_block_is_found(self):
        amended = "### PAD-18-001\n\n- Before: a\n- After: b\n- Reason: c"
        found = lint_body(_body(amended=amended), self._facts())
        assert [f.message for f in found] == [
            "`## Spec amended` has no `### PAD-18-008` block"
        ]

    def test_a_todo_passes_before_the_push_and_fails_after(self):
        amended = (
            "### PAD-18-001\n\n- Before: <TODO — x>\n\n"
            "### PAD-18-008\n\n- Before: a"
        )
        assert _ids(_body(amended=amended), self._facts()) == []
        final = self._facts(Stage.FINAL)
        assert _ids(_body(amended=amended), final) == ["PRB-09"]


@pytest.mark.spec("PAD-20-001")
class TestAttributionLast:
    def test_text_after_the_attribution_is_found(self):
        assert _ids(_body(tail=f"{ATTRIBUTION}\n\nOne more thing.")) == [
            "PRB-10"
        ]

    def test_no_attribution_line_is_not_a_finding(self):
        assert _ids(_body(tail="Thanks.")) == []

    def test_trailing_blank_lines_are_ignored(self):
        assert _ids(_body(tail=f"{ATTRIBUTION}\n\n\n")) == []


# --- CLI ---------------------------------------------------------------------


@pytest.fixture
def repo(tmp_path: Path, monkeypatch) -> Path:
    """A repository on branch ``work``, one commit past its ``base`` branch."""
    (tmp_path / "README.md").write_text("x\n")
    commit_base(tmp_path)
    git(tmp_path, "checkout", "-q", "-b", "work")
    (tmp_path / "tool.py").write_text("x = 1\n")
    monkeypatch.chdir(tmp_path)
    return tmp_path


class _FakeRunner:
    """Stands in for ``bash spec-amendments.sh``."""

    def __init__(self, amended: str = "", amend_rc: int = 0):
        self.amended, self.amend_rc = amended, amend_rc
        self.calls: list[list[str]] = []

    def __call__(
        self, argv: Sequence[str], cwd: Path
    ) -> subprocess.CompletedProcess[str]:
        self.calls.append(list(argv))
        return subprocess.CompletedProcess(
            list(argv), self.amend_rc, self.amended, "boom"
        )


@pytest.mark.spec("PAD-20-002")
class TestCli:
    def test_a_clean_body_exits_0(self, repo):
        (repo / "body.md").write_text(_body())
        assert (
            main(["--body", "body.md", "--base", "base"], run=_FakeRunner())
            == 0
        )

    def test_python_in_the_diff_makes_it_an_implementation_pr(
        self, repo, capsys
    ):
        (repo / "body.md").write_text(_body(specs=None, verification=None))
        assert (
            main(["--body", "body.md", "--base", "base"], run=_FakeRunner())
            == 1
        )
        out = capsys.readouterr().out
        assert "PRB-05 specs-manifest" in out
        assert "PRB-07 verification-section" in out

    def test_amended_ids_come_from_spec_amendments(self, repo, capsys):
        (repo / "body.md").write_text(_body())
        run = _FakeRunner(
            amended="PAD-18-001\tchanged\tstatement\n", amend_rc=1
        )
        assert main(["--body", "body.md", "--base", "base"], run=run) == 1
        assert "PRB-09" in capsys.readouterr().out
        assert run.calls[0][-2:] == ["base", "HEAD"]

    def test_a_spec_amendments_load_error_exits_2(self, repo):
        (repo / "body.md").write_text(_body())
        run = _FakeRunner(amend_rc=2)
        assert main(["--body", "body.md", "--base", "base"], run=run) == 2

    def test_an_unresolvable_base_exits_2(self, repo):
        (repo / "body.md").write_text(_body())
        assert (
            main(["--body", "body.md", "--base", "nope"], _FakeRunner()) == 2
        )

    def test_a_missing_body_file_exits_2(self, repo):
        assert (
            main(["--body", "missing.md", "--base", "base"], run=_FakeRunner())
            == 2
        )

    def test_the_manifest_file_is_checked_verbatim(self, repo, capsys):
        (repo / "body.md").write_text(_body())
        (repo / "manifest.txt").write_text(MANIFEST + "\nLoaded (extra): X\n")
        argv = [
            "--body",
            "body.md",
            "--base",
            "base",
            "--manifest",
            "manifest.txt",
        ]
        assert main(argv, run=_FakeRunner()) == 1
        assert "PRB-06" in capsys.readouterr().out

    def test_a_pr_payload_supplies_body_files_and_base(self, repo, capsys):
        view = {
            "body": _body(docs=DOCS_PLACEHOLDER),
            "files": [{"path": "vultron/x.py"}],
            "baseRefName": "base",
        }
        (repo / "view.json").write_text(json.dumps(view))
        run = _FakeRunner()
        argv = ["--pr-json", "view.json", "--stage", "final"]
        assert main(argv, run=run) == 1
        assert "PRB-08" in capsys.readouterr().out
        assert run.calls[0][-2:] == ["origin/base", "HEAD"]

    def test_a_payload_without_python_is_a_docs_pr(self, repo):
        view = {"body": _body(specs=None, verification=None), "files": []}
        (repo / "view.json").write_text(json.dumps(view))
        argv = ["--pr-json", "view.json", "--stage", "final"]
        assert main(argv, run=_FakeRunner()) == 0

    @pytest.mark.parametrize("payload", ["not json", "[]", '{"files": []}'])
    def test_a_malformed_payload_exits_2(self, repo, payload):
        (repo / "view.json").write_text(payload)
        assert main(["--pr-json", "view.json"], run=_FakeRunner()) == 2

    def test_list_rules_prints_every_rule(self, capsys):
        assert main(["--list-rules"]) == 0
        out = capsys.readouterr().out.splitlines()
        assert [ln.split()[0] for ln in out] == [r.rule_id for r in RULES]

    def test_body_or_pr_is_required(self):
        with pytest.raises(SystemExit):
            main([])


# --- the skills that run the gates ---------------------------------------------


def _section(path: Path, start: str, end: str) -> str:
    text = path.read_text()
    return text[text.index(start) : text.index(end, text.index(start))]


class TestSkillsRunTheGates:
    @pytest.mark.spec("PAD-20-002")
    @pytest.mark.spec("PAD-20-003")
    def test_create_pr_runs_the_gates_before_the_push(self):
        gate = _section(
            SKILLS / "create-pr" / "SKILL.md",
            "### 3b — Pre-push body and spec gates",
            "## Phase 4",
        )
        assert "spec-lint --changed-since origin/main" in gate
        assert "spec-backstop --manifest <manifest>" in gate
        assert "pr-body-lint --body /tmp/pr-body-<issue>.md" in gate
        assert "--manifest <manifest>" in gate

    @pytest.mark.spec("PAD-20-002")
    def test_create_pr_opens_the_pr_from_the_linted_file(self):
        push = _section(
            SKILLS / "create-pr" / "SKILL.md", "## Phase 4", "## Constraints"
        )
        assert "--body-file /tmp/pr-body-<issue>.md" in push

    @pytest.mark.spec("PAD-20-004")
    def test_pr_triage_runs_it_first_in_its_body_phase(self):
        phase = _section(
            SKILLS / "pr-triage" / "SKILL.md",
            "### Phase 3 — PR Body Format",
            "### Phase 4",
        )
        first_step = phase.split("```bash", 1)[1].split("```", 1)[0]
        assert (
            "gh pr view <number> --json body,files,baseRefName" in first_step
        )
        assert "pr-body-lint --pr-json - --stage final" in first_step

    @pytest.mark.spec("PAD-20-005")
    def test_check_docs_sync_has_the_caller_lint_the_final_body(self):
        text = (SKILLS / "check-docs-sync" / "SKILL.md").read_text()
        assert "pr-body-lint --pr-json - --stage final" in text
