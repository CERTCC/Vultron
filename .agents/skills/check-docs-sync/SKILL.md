---
name: check-docs-sync
description: >
  Three-question docs-sync check: identifies docs/ pages that need updating
  after an implementation or bug-fix change, applies small updates inline
  (PD-03-007) behind a blocking lint-docs gate, offers write-docs for large
  multi-page rewrites, and files a type:Concern issue when those are deferred.
  Invoked after the PR is pushed (while CI runs), by build (Phase 8), bugfix
  (Phase 4 finalize), and learn (Phase 8).
---

# Skill: Check Docs Sync

Verify that `docs/` is in sync with the current implementation changes.
Normative requirement: `specs/project-documentation.yaml` **PD-03-007**.

## When to invoke

After the PR is pushed (CI starts in the cloud), while CI runs in parallel
locally. Apply any small docs updates and commit them before the finalize steps
(archive-history, learnings). Invoked by `build` (Phase 8), `bugfix` (Phase 4
finalize), and `learn` (Phase 8) for consistency.

Prose rules for every page this skill touches live in
[`../shared/docs-style-guide.md`](../shared/docs-style-guide.md), made normative
by `specs/diataxis-requirements.yaml` DF-09-001. This skill does not restate
them — it enforces them via the `lint-docs` gate in Step 3.

## Procedure

### Step 1 — Identify changed areas

```bash
git diff origin/main...HEAD --name-only
```

Look at the changed files and identify the functional areas affected:

- `vultron/` changes → protocol behavior, wire layer, adapters, BT nodes
- `specs/` changes → specification requirements (PD, CM, ARCH, etc.)
- `notes/` changes → design notes and durable insights
- `.agents/skills/` changes → agent skill pipelines

### Step 2 — Three-question docs-sync check

For each changed area, answer three questions:

**Q1 — Does this change introduce or modify behavior, interfaces, or
architecture described in `docs/`?**

Scan `docs/` for pages covering the changed area:

- `docs/topics/` — protocol behavior descriptions
- `docs/reference/` — API and data model reference
- `docs/developer/` — developer guides and architecture
- `docs/explanation/` — conceptual explanations
- `docs/how-to/` — procedural how-to guides

If no relevant `docs/` page exists and none is needed, answer "no" and
move to the next area.

**Q2 — What specific `docs/` pages need to be created or updated?**

List each page with a short description of what needs to change (add a
section, update a code example, new page covering X, etc.).

**Q3 — Small or large update?**

Apply the heuristic:

| Required update | Disposition |
|---|---|
| Edit to one or more existing pages | **Small** — do now |
| Add a single new page | **Small** — do now |
| Rewrite a single existing page | **Small** — do now |
| Simultaneously rewrite multiple pages completely | **Large** — file Concern |

When in doubt, lean toward **Small** and do it now. The Concern path is for
genuine multi-page rewrites that would bloat the PR beyond its original scope.

### Step 3 — Apply small updates

For each small update:

1. Write the change to the target `docs/` file.
2. Invoke `lint-docs` on the changed pages. This is a **blocking gate**: it
   fixes mechanical style findings in place, and any finding it reports must be
   resolved before proceeding. If it escalates a quadrant misclassification,
   act on the recommendation it gives or hand the page to `write-docs`.
3. Invoke `format-markdown` to lint the updated file before building.
4. Invoke `build-docs` to validate the build passes, tee-ing output to a temp
   file so full context is available on failure:

   ```bash
   UV_NO_SYNC=1 uv run mkdocs build --strict 2>&1 | tee /tmp/mkdocs-build.log | tail -20
   # On failure with insufficient tail output: grep /tmp/mkdocs-build.log
   ```

5. Fix any linting or build errors before proceeding.

For a new page, or a full rewrite of an existing one, invoke `write-docs` with
`mode: inline` instead of writing the page directly. It handles quadrant
classification, concept ordering, nav wiring, and term registration, and leaves
the result in this branch for the caller to commit.

### Step 4 — Offer write-docs, then file a Concern

For each large update (multi-page rewrite needed), **offer `write-docs` before
deferring**. PD-03-007 prefers an inline update, so the Concern is the fallback,
not the default. Recommend one course and ask for confirmation:

> "`docs/topics/process_models/em/` needs three pages rewritten after this
> embargo-consent change. I recommend invoking `write-docs` now with
> `mode: inline` — the pages are adjacent and the change is mechanical, so it
> adds roughly 200 lines to this PR rather than a week of context reconstruction.
> Alternatively I file a Concern and defer. Proceed with `write-docs`?"

If the user accepts, invoke `write-docs` with `mode: inline` and skip the rest
of this step. If the user declines, or the scope genuinely exceeds this PR,
invoke the `new-item` skill to file a `type:Concern` issue. Provide these
details as context:

- **Type**: Concern
- **Title**: `docs: update <area> pages after <change>`
- **Context**: what implementation change requires the docs update
- **Required docs updates**: each page that needs updating with what to change
- **Source**: PD-03-007 — implementation PR must include docs updates or a
  linked Concern; deferred only when multiple pages require simultaneous rewrite
- **Deferred from PR**: `<PR_URL>` (fill in after the PR opens)
- **Suggested label**: `size:M`

`new-item` handles duplicate detection, parent epic selection, and creation.

Record the Concern issue number for inclusion in the PR description:
`Docs deferred: #<N>` (add to the PR body after the PR opens).

### Step 5 — Report

Return a summary of what was done:

- List each `docs/` page updated inline (file path + short description of what changed)
- List each Concern issue filed for large updates: issue number, title, and 1–2
  sentences describing what the concern entails and why the update was deferred
- If no `docs/` updates were needed, state that explicitly

## Constraints

- Only update `docs/` — do not modify code, tests, or `specs/`.
- Always invoke `lint-docs` and then `build-docs` after each inline `docs/`
  update; do not skip either. `lint-docs` is a blocking gate (DF-09-001).
- Small updates MUST be applied in the same PR, not deferred (PD-03-007).
- Offer `write-docs` before filing a Concern for a large update. Deferring
  without offering the inline path first inverts PD-03-007's preference.
- File a Concern issue for every large update that is not done inline; never
  silently skip.
- Cite PD-03-007 in every Concern issue body.
