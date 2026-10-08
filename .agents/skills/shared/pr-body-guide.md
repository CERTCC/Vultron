# PR Body Guide

All PRs opened by agents MUST use the structured templates below.
Reference this file from the "Open PR" step of any skill that calls
`gh pr create`.

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
- ruff, mypy, pyright clean
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
- **Issues**: required on implementation PRs; the last line of `## Summary`,
  in the form `Issues: closed N, opened M`. Count per
  `completeness-doctrine.md` § "Net Issues: Close More Than You Open": `N` is
  pre-existing, non-Epic issues the PR closes, and `excursion` issues the PR
  files and closes are left out of both counts. List each issue opened with its
  reason, for example `Issues: closed 2, opened 1 (#4402 debt)`. A PR that opens
  none writes `opened 0`. Also close any nearby `opened:debt` issues (a
  `- Closes #N` bullet each, plus a one-line reason when "nearby" is by spec or
  area rather than file).
- **Summary**: required; 1–2 sentences, present tense.
- **Motivation**: optional; omit when Summary is self-explanatory.
- **Changes**: required; use backtick-wrapped file paths and concrete
  descriptions. Do not just echo the commit message.
- **Specs**: required. Paste the Spec manifest `deepen-context` returned
  (floor, cross-cutting, selected, and considered-but-skipped lines), as
  resolved against the diff by `spec-backstop --manifest` (exit 0). Exit 0
  means nothing derivable from the diff was missed — not that the selection
  is complete, so keep the `Considered, skipped` reasons honest.
  `pr-review` and `pr-triage` use it as their spec floor and flag a PR
  without one.
- **Spec amended**: required on **any** PR (implementation or docs-only) whose
  diff changes or removes a `statement:` or `priority:` in `specs/`; omit it
  otherwise. `bash .agents/skills/shared/spec-amendments.sh origin/main` lists the
  IDs (new requirements are not listed — nothing built on them can be wrong).
  One `### <ID>` block each, with **Before**, **After** and **Reason**. The
  section is the single place a reviewer sees spec text moved to fit code; the
  material test in `notes/agentic-workflow.md` § "Spec Text Conflicts With Code"
  decides whether the Reason is a clarification (allowed in the PR) or an
  obligation change (needs the user's approval, recorded in the Reason).
  `create-pr` writes the placeholder with `<TODO>` fields; the author fills
  them. `pr-triage` FAILs a diff that changes a statement or priority without the
  section, or one that still contains `<TODO>`; `pr-verify` blocks on it.
- **Docs**: required on every implementation or bug-fix PR (PD-03-008) —
  one that closes a `Task`, `Feature`, or `Bug` issue, or changes `.py`
  files. This is the scope `create-pr`, `pr-triage`, `pr-execute`, and
  `pr-verify` apply. A single line beginning `Docs:` records
  whether the PR's change is described anywhere in reader-facing `docs/`.
  `create-pr` writes the placeholder `Docs: pending check-docs-sync`, and the
  caller replaces it with the line `check-docs-sync` reports, in one of three
  final forms:
  - `Docs: updated <page>, <page>` — the `docs/` pages this PR updated, as
    repo-relative paths.
  - `Docs: no docs impact — <reason>` — no `docs/` page describes the changed
    behavior. The reason names why (for example "internal refactor, no
    described interface changed" or "spec pages regenerate from YAML").
  - `Docs: deferred to #N` — a multi-page rewrite deferred to a `type:Concern`
    issue that lists the affected pages (PD-03-007). The issue may be open or
    already closed as planned; it must exist. An updated-and-deferred PR
    carries both: `Docs: updated <page>; deferred to #N`.

  The session that opened the PR is not done while the placeholder remains,
  and `pr-triage` treats a missing or placeholder `Docs:` line as a FAIL
  (PD-03-009). `pr-execute` refreshes the line when its fixes change described
  behavior.
- **Verification**: required for any PR that modifies `.py` files. Include
  the actual total test count and the number of new tests added. Tick off
  acceptance criteria from the issue when they are listed.

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
