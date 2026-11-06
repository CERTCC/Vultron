# PR Body Guide

All PRs opened by agents MUST use the structured templates below.
Reference this file from the "Open PR" step of any skill that calls
`gh pr create`.

## Mechanical Checks (`pr-body-lint`)

The rules below need no judgment, so a tool checks them (PAD-20-001):

```bash
# Before the push, on the composed body:
PYTHONPATH= uv run pr-body-lint --body <file> [--manifest <file>]
# Once Docs: is recorded, on the open PR (the tool never calls GitHub itself):
gh pr view <N> --json body,baseRefName,headRefOid \
  | PYTHONPATH= uv run pr-body-lint --pr-json - --stage final
```

`pre-push` (the default stage) accepts the placeholders `create-pr` writes;
`final` refuses them. Add `--closes-work-item` when a docs PR closes a `Task`,
`Feature` or `Bug`. Exit 1 lists each finding by rule ID; exit 2 is a setup
error, never a pass, and is what `--pr-json` gives in a checkout not at the PR's
head commit: the changed files are read from that checkout, because GitHub's
`files` list stops at 100. `create-pr` runs it before the first push (PAD-20-002),
`pr-triage` runs it first in Phase 3 (PAD-20-004), and the session that opened
the PR runs the final stage after recording `Docs:` (PAD-20-005). Everything
else in this guide, such as whether the body's claims match the diff, stays a
review judgment.

This table and the tool's `RULES` are one list; a test fails when they differ.

| Rule | Name | Checks |
|---|---|---|
| PRB-01 | closes-first | No closing reference after the opening block of `- Closes #N` lines |
| PRB-02 | closes-one-per-line | Each closing reference is its own `- Closes #N` bullet |
| PRB-03 | required-sections | `## Summary` and `## Changes` exist |
| PRB-04 | issues-line | Implementation: `## Summary` ends with `Issues: closed N, opened M`, or with it then the `Questions:` line |
| PRB-05 | specs-manifest | Implementation: `## Specs` holds the four manifest lines, no `..` ranges |
| PRB-06 | manifest-verbatim | With `--manifest`: every manifest line is in `## Specs` unchanged |
| PRB-07 | verification-section | `## Verification` exists when the diff changes `.py` |
| PRB-08 | docs-line | A `Docs:` line exists; at `final`, in a final form, not the placeholder |
| PRB-09 | spec-amended | A `### <ID>` block per amended ID; at `final`, no `<TODO>` |
| PRB-10 | attribution-last | The `Generated with [...]` line, when present, is the last line |
| PRB-11 | body-length | The body is at most GitHub's 65,536-character limit |
| PRB-12 | maintainer-docs-followup | Tooling diff with no maintainer doc: a `Docs:` line; at `final`, `deferred to #N` or `no maintainer docs impact — …` |
| PRB-13 | questions-line | Implementation: `## Summary` ends with `Questions: asked N, filed M`, right after the `Issues:` line |

---

## Template: Implementation PRs

Use for `build`, `bugfix`, and any PR that modifies `.py` files.

```markdown
- Closes #N
- Closes #M   <!-- one line per issue; GitHub expands the title automatically -->
<!-- ⚠️  THESE LINES MUST BE FIRST — before any ## header. Moving them breaks the GitHub sidebar. -->

## Summary

<1–2 sentences: what this PR does and why. Present tense: "Adds…", "Fixes…",
"Replaces…". Focus on the outcome.>

Issues: closed <N>, opened <M>   <!-- see the Issues rule below -->
Questions: asked <A>, filed <F>   <!-- see the Questions rule below -->

## Motivation

<Why this change is needed. **Omit this section** if the Summary already
captures the full rationale.>

## Changes

- **`path/to/file.py`**: <what changed and why>
- **`path/to/other.py`**: <what changed and why>
- **`test/path/test_file.py`**: <what tests were added or changed>

## Specs

<Spec manifest returned by deepen-context, verbatim>

## Spec amended   <!-- only when the diff changes or removes a spec statement: or priority: -->

### <SPEC-ID>

- Before: <statement/priority on main>
- After: <statement/priority now>
- Reason: <why; clarification, corrected reference, or an obligation change the user approved>

## Docs

Docs: pending check-docs-sync   <!-- create-pr writes this; check-docs-sync's result replaces it -->

## Verification

- All N unit tests pass (M new)
- ruff and mypy clean
- Self-check:   <!-- shared/pre-review-self-check.md; one result per item -->
  - Affected text: <search terms used; files updated, or "no hits">
  - Failure paths: <per write: on failure / on retry / test, or "no writes changed">
  - Branch coverage: <untested branches and why, or "every new branch tested">
  - Reuse: <helpers reused or extracted, or "no duplication found">
- [x] AC-1: ...   <!-- include when the closed issue listed acceptance criteria -->
```

### Implementation PR rules

- Closing references (`Closes #N` / `Fixes #N`) go at the **top**, one per
  bullet line, **before any `##` section header**, so GitHub expands the issue
  title in the PR sidebar. **This is the single most commonly missed rule —
  every PR triage flags it when violated.**
- **Every "also" excursion this PR fixed gets its own `- Closes #N` bullet.**
  If, while doing the original work, you fixed something that warranted its own
  filed issue (an "also" excursion per
  `.agents/skills/shared/completeness-doctrine.md`), that issue must appear as a
  closing bullet, and the Changes section must give it a one-line "why." A
  reviewer comparing the closing list to the diff should never be surprised —
  clarity about what the PR does and why, mapped to the issues it closes,
  matters more than keeping the PR small.
- **Issues**: required on implementation PRs; the line before `Questions:`
  at the end of `## Summary`, in the form `Issues: closed N, opened M`. Count per
  `completeness-doctrine.md` § "Net Issues: Close More Than You Open": `N` is
  pre-existing, non-Epic issues the PR closes, and `excursion` issues the PR
  files and closes are left out of both counts. List each issue opened with its
  reason, for example `Issues: closed 2, opened 1 (#4402 debt)`. A PR that opens
  none writes `opened 0`. Also close any nearby `opened:debt` issues (a
  `- Closes #N` bullet each, plus a one-line reason when "nearby" is by spec or
  area rather than file).
- **Questions**: required on implementation PRs; the last line of
  `## Summary`, directly after `Issues:`, in the form
  `Questions: asked A, filed F`. `A` counts decisions this PR's work put to
  the user (or, from a sub-agent, to its orchestrator) and got answered; `F`
  counts questions filed as an issue instead of asked (a Concern, or a Task
  with a `Decision:` line), each listed with why it could not be asked, for
  example `Questions: asked 1, filed 1 (#4402 out of this PR's scope)`. Count
  every session that worked the PR, `pr-execute` included; a PR that met no
  decision writes `asked 0, filed 0`. See `completeness-doctrine.md`
  § "Ask, Then Finish".
- **Summary**: required; 1–2 sentences, present tense.
- **Motivation**: optional; omit when Summary is self-explanatory.
- **Changes**: required; use backtick-wrapped file paths and concrete
  descriptions. Do not just echo the commit message.
- **Specs**: required. Paste the Spec manifest `deepen-context` returned
  (floor, cross-cutting, selected, and considered-but-skipped lines), as
  resolved against the diff by `spec-backstop --manifest` (exit 0). Copy the
  manifest file itself, never a retyped version or a stated exit status:
  `create-pr` requires the exit 0 and checks the copy (PRB-06). Exit 0
  means nothing derivable from the diff was missed — not that the selection
  is complete, so keep the `Considered, skipped` reasons honest.
  `pr-review` and `pr-triage` use it as their spec floor and flag a PR
  without one.
- **Spec amended**: required on **any** PR (implementation or docs-only) whose
  diff changes or removes a `statement:` or `priority:` in `specs/`; omit it
  otherwise. `bash .agents/skills/shared/spec-amendments.sh origin/main` lists the
  IDs (new requirements are not listed — nothing built on them can be wrong).
  It compares two git refs, so **run it after the spec change is committed**:
  an uncommitted `specs/` edit is invisible to it, and it exits 2 rather than
  answer "no amendment" from a tree it cannot read (#5591).
  One `### <ID>` block each, with **Before**, **After** and **Reason**. On a
  sweep large enough to break GitHub's body limit (PRB-11), show a long
  statement as its changed span with a few words of context either side,
  `…` marking each cut, and say so at the top of the section. A Reason that
  every block shares may be stated once at the top instead (PRB-09 checks only
  the `### <ID>` headings). When the trimmed section would still hide what a
  reviewer must check, such as a split's full old-to-new mapping, write the
  untrimmed record with `uv run append-history implementation --source
  ISSUE-<N>-<slug>` and link it from the section; the slug keeps several such
  records for one issue apart. Never split the PR to fit. The
  section is the single place a reviewer sees spec text moved to fit code; the
  material test in `notes/agentic-workflow.md` § "Spec Text Conflicts With Code"
  decides whether the Reason is a clarification (allowed in the PR) or an
  obligation change (needs the user's approval, recorded in the Reason).
  `create-pr` writes the placeholder with `<TODO>` fields; the author fills
  them. `pr-triage` FAILs a diff that changes a statement or priority without the
  section, or one that still contains `<TODO>`; `pr-verify` blocks on it.
- **Docs**: required on every implementation or bug-fix PR (PD-03-013) —
  one that closes a `Task`, `Feature`, or `Bug` issue, or changes `.py`
  files. This is the scope `create-pr`, `pr-triage`, `pr-execute`, and
  `pr-verify` apply. A single line beginning `Docs:` records
  whether the PR's change is described anywhere in reader-facing `docs/`.
  `create-pr` writes the placeholder `Docs: pending check-docs-sync`, and the
  caller replaces it with the line `check-docs-sync` reports, in one of three
  final forms (a tooling PR has a fourth, below):
  - `Docs: updated <page>, <page>` — the `docs/` pages this PR updated, as
    repo-relative paths.
  - `Docs: no docs impact — <reason>` — no `docs/` page describes the changed
    behavior. The reason names why (for example "internal refactor, no
    described interface changed" or "spec pages regenerate from YAML").
  - `Docs: deferred to #N` — a multi-page rewrite deferred to a `type:Task`
    issue that lists the affected pages (PD-03-007). An older deferral filed as a
    `type:Concern` still validates (PD-03-009). The issue may be open or
    already closed as planned; it must exist. An updated-and-deferred PR
    carries both: `Docs: updated <page>; deferred to #N`.

  A PR whose diff changes a workflow or tooling file and no maintainer-facing
  doc carries a `Docs:` line whatever its template (PRB-12, PD-03-014).
  Tooling is a file under `.github/workflows/`, `.github/scripts/`,
  `.github/actions/`, `.agents/skills/`, `vultron/metadata/`, `scripts/`,
  `.devcontainer/`, `docker/` or `.githooks/`, or `.pre-commit-config.yaml`,
  `mdlint.sh`, `Makefile` or `start-dev.sh`. A maintainer-facing doc is a file
  under `docs/developer/`, `docs/agents/`, `notes/` or `.github/instructions/`,
  any `AGENTS.md`, a skill's Markdown, `CONTRIBUTING.md`, `README-DEV.md`,
  `.devcontainer/README.md`, or `.github/copilot-instructions.md`. At the final
  stage that line takes a final form and names the follow-up docs issue
  (`deferred to #N`) or says why no maintainer doc needs the change
  (`no maintainer docs impact — <reason>`), each clause opening the line or
  following a `;`. The reader-facing `no docs impact` verdict does not count,
  so append the clause to it:
  `Docs: no docs impact — <reason>; no maintainer docs impact — <reason>`.
  On such a PR only, the clause alone,
  `Docs: no maintainer docs impact — <reason>`, is a fourth final form. The
  check is coarse: any maintainer-facing doc in the diff closes the gap, and
  whether that doc covers the change is `pr-triage`'s judgment.

  The session that opened the PR is not done while the placeholder remains,
  and `pr-triage` treats a missing or placeholder `Docs:` line as a FAIL
  (PD-03-009). `pr-execute` refreshes the line when its fixes change described
  behavior.
- **Verification**: required for any PR that modifies `.py` files. Include
  the actual total test count and the number of new tests added. Tick off
  acceptance criteria from the issue when they are listed.
  On every implementation PR it also carries the `Self-check:` block: the four
  results of `.agents/skills/shared/pre-review-self-check.md`, one line each.
  `pr-triage` compares the block against the diff and treats a missing block
  as IMPROVE.

---

## Template: Docs-Only PRs

Use for `plan-issue`, `learn`, and any PR that touches only `.md`, `.yaml`,
or other non-Python files.

```markdown
- Closes #N
<!-- ⚠️  THIS LINE MUST BE FIRST — before any ## header. Moving it breaks the GitHub sidebar. -->

## Summary

<1–2 sentences: what docs, specs, or notes were added or updated and why.>

## Changes

- **`path/to/file.md`**: <what changed>
- **`specs/file.yaml`**: <what changed>

## Spec amended   <!-- only when a spec statement: or priority: is changed or removed -->

### <SPEC-ID>

- Before: ...
- After: ...
- Reason: ...
```

### Docs-only PR rules

- Closing reference goes at the **top**, before any `##` header.
- No Verification section — no Python was changed, no test suite ran.
- `## Spec amended` follows the same rule as for implementation PRs: present
  exactly when a `statement:` or `priority:` is changed or removed.
- Keep Changes concise; list meaningful files only (not `README.md` unless
  it was substantively updated).
