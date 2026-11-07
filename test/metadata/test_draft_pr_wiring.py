#!/usr/bin/env python

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
"""The draft life cycle of an implementation Pull Request, as written.

An implementation Pull Request opens as a draft, because no full suite has
run on it when it is first pushed (PAD-18-028), and it is marked ready for
review when, and only when, CI's run on its head has passed (PAD-18-029).
The two halves have to land together: a draft nothing undrafts is a Pull
Request GitHub will not merge, since `gh pr merge` refuses a draft and
`pr-verify` withholds `READY-TO-MERGE` on `PR-IS-DRAFT`.

What this module reads, and the direction each reading is loose in
(`notes/architecture-ratchet-corpus.md`):

- The skills' Markdown, not a running pipeline. It can be satisfied by a
  sentence that says the right thing while a step elsewhere does the wrong
  one. It **misses** a contradiction between two sections of the same file.
- Only the lines an agent runs — fenced blocks and frontmatter ``commands:``
  (:func:`code_lines`). Prose is left out, or "never run ``gh pr ready``
  here" would **invent** a violation out of the sentence forbidding one.
- It is keyed on the `gh` subcommands, which is how the transition is made.
  A transition made some other way — a `gh api` call against the
  `markPullRequestReadyForReview` mutation, say — would be **missed**. None
  exists today.
- The `needs-rebase` arm is read twice: negatively, that the label does not
  appear in the step before its own `gh pr edit` line, and positively, that
  the step says the transition is owed ("owed, not optional", or "any
  draft"). Either reading alone could be satisfied by a rewrite that moved
  the condition past it.

Requirements: specs/parallel-development.yaml PAD-18-028, PAD-18-029,
PAD-18-030.
"""

import re
from pathlib import Path

import pytest

from test.metadata._agent_docs import code_lines

_REPO_ROOT = Path(__file__).parents[2]
_SKILLS = _REPO_ROOT / ".agents" / "skills"

_CREATE_PR = _SKILLS / "create-pr" / "SKILL.md"
_PR_EXECUTE = _SKILLS / "pr-execute" / "SKILL.md"
_PR_EXECUTE_REF = _SKILLS / "pr-execute" / "REFERENCE.md"
_PR_SHIP = _SKILLS / "pr-ship" / "SKILL.md"

#: The files this module reads. Annotated rather than left bare, so the
#: emptiness check below is a check and not a constant pyright folds away
#: (#5535).
_READ_FILES: tuple[Path, ...] = (
    _CREATE_PR,
    _PR_EXECUTE,
    _PR_EXECUTE_REF,
    _PR_SHIP,
)

#: `gh pr create` with `--draft` among its continued lines (PAD-18-028).
_DRAFT_CREATE = re.compile(r"gh pr create\b(?:[^\n]*\\\n)*[^\n]*--draft\b")

#: The transition itself (PAD-18-029).
_PR_READY = re.compile(r"gh pr ready\b")

#: A cap on CI rounds, however it is spelled: a digit or the word, with
#: "iteration" after it and at most one word between. Each match must say
#: what it counts.
_CAP_STATEMENTS = re.compile(
    r"(?:4|four)[- ](?:\w+ )?iterations?", re.IGNORECASE
)

#: The same with no word between: the shape that says nothing about what is
#: counted.
_BARE_CAP = re.compile(r"(?:4|four)[- ]iterations?", re.IGNORECASE)


def _ci_green_step(text: str) -> str:
    """`pr-execute`'s CI-green step, or a failure naming the heading moved."""
    start = re.search(r"\*\*On CI green[^\n]*\*\*", text)
    if start is None:
        pytest.fail(
            "pr-execute's `**On CI green**` heading moved or was reworded; "
            "the draft guard cannot find the step (PAD-18-029)"
        )
    end = re.search(r"\*\*On (?:the )?(?:fourth|iteration 4)", text)
    if end is None or end.start() <= start.end():
        pytest.fail(
            "pr-execute's eject heading moved or was reworded; the draft "
            "guard cannot bound the CI-green step (PAD-18-029, PAD-18-030)"
        )
    return text[start.start() : end.start()]


def _text(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def test_the_files_this_module_reads_exist() -> None:
    assert _READ_FILES, "the declared file list is empty"
    missing = [str(p) for p in _READ_FILES if not p.is_file()]
    assert not missing, f"moved or renamed: {missing}"


@pytest.mark.spec("PAD-18-028")
def test_create_pr_opens_an_implementation_pr_as_a_draft() -> None:
    text = _text(_CREATE_PR)
    code = "\n".join(code_lines(text))
    assert _DRAFT_CREATE.search(code), (
        "create-pr's `gh pr create` call does not carry `--draft`. An "
        "implementation Pull Request opens as a draft (PAD-18-028): no full "
        "suite has run on the branch when it is first pushed. Read from the "
        "fenced command, not the prose: a sentence saying so is not the call."
    )
    assert "PAD-18-028" in text


@pytest.mark.spec("PAD-18-028", "PAD-18-029")
def test_create_pr_never_marks_the_draft_ready_itself() -> None:
    """`create-pr` has no CI result to read, so it cannot satisfy -029."""
    offenders = [
        line.strip()
        for line in code_lines(_text(_CREATE_PR))
        if _PR_READY.search(line)
    ]
    assert not offenders, (
        "create-pr runs `gh pr ready`, but no CI run has judged the branch "
        "at that point (PAD-18-029):\n" + "\n".join(offenders)
    )


@pytest.mark.spec("PAD-18-029")
def test_the_ci_green_step_marks_any_draft_ready() -> None:
    """Not only one labelled `needs-rebase`, as it was before #5948.

    The label said *why* a draft could not be marked ready yet; it was never
    what made the Pull Request a draft. Now every implementation Pull
    Request opens as one, so a step conditioned on the label would leave the
    ordinary Pull Request a draft for good.
    """
    text = _text(_PR_EXECUTE)
    assert _PR_READY.search(text), "pr-execute never runs `gh pr ready`"
    step = _ci_green_step(text)
    assert _PR_READY.search(step), (
        "the CI-green step does not run `gh pr ready` (PAD-18-029)"
    )
    # Negative: the label may not gate the step, before or after the command.
    before_label_drop = step.replace("# only if it carries one", "").split(
        "gh pr edit", 1
    )[0]
    assert "needs-rebase" not in before_label_drop, (
        "the CI-green step's undraft is conditioned on the `needs-rebase` "
        "label. Every implementation Pull Request is a draft now "
        "(PAD-18-028), so the transition is owed to all of them "
        "(PAD-18-029)."
    )
    # Positive: the step has to say the transition is owed, not permitted.
    assert any(
        phrase in step for phrase in ("owed, not optional", "any draft")
    ), (
        "the CI-green step does not say the transition is owed. A step that "
        "only permits it leaves a green draft a draft (PAD-18-029)."
    )
    assert "PAD-18-029" in step


@pytest.mark.spec("PAD-18-030")
@pytest.mark.parametrize("path", [_PR_EXECUTE, _PR_EXECUTE_REF])
def test_the_ci_round_cap_does_not_count_the_first_draft_run(
    path: Path,
) -> None:
    """The cap is on rounds spent on a fix, not on loops (PAD-18-030).

    CI's first run on a draft is the full-suite run the local gate no longer
    makes. Counting it would leave one round fewer for fixes than before.
    """
    text = _text(path)
    bare = _BARE_CAP.findall(text)
    assert not bare, (
        f"{path.name} states a cap over plain iterations: {bare}. CI's first "
        "run on a draft is not one of them (PAD-18-030); say what the cap "
        "counts."
    )
    statements = _CAP_STATEMENTS.findall(text)
    assert statements, (
        f"{path.name} no longer states the cap at all; the guard would pass "
        "having read nothing (#5535)"
    )
    for statement in statements:
        assert "counted" in statement, (
            f"{path.name} states a cap that does not say what it counts: "
            f"{statement!r} (PAD-18-030)"
        )


@pytest.mark.spec("PAD-18-030")
def test_pr_execute_names_the_rule_for_the_uncounted_first_round() -> None:
    text = _text(_PR_EXECUTE)
    assert "PAD-18-030" in text
    assert "not counted" in text or "does not consume" in text


@pytest.mark.spec("PAD-18-029")
def test_pr_ship_backstops_the_transition_on_its_resume_path() -> None:
    """`pr-ship` is where PAD-18-029 names the transition.

    Its `pr-execute` phase makes it on the CI-green step. On the resume
    path, where execute is skipped because its artifact already exists, that
    step never runs, so the orchestrator checks the draft state itself
    before handing the Pull Request to `pr-verify` — which withholds
    `READY-TO-MERGE` from a draft.
    """
    text = _text(_PR_SHIP)
    runs = [line for line in code_lines(text) if _PR_READY.search(line)]
    assert runs, "pr-ship never runs `gh pr ready` (PAD-18-029)"
    assert "isDraft" in text, (
        "pr-ship runs `gh pr ready` without reading the draft state first"
    )
    assert "final_ci_status" in text, (
        "pr-ship's backstop does not say which recorded CI result permits "
        "the transition (PAD-18-029)"
    )
