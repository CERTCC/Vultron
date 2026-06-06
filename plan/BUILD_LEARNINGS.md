## Implementation Notes

Longer-term notes can be found in `/notes/*.md`. This file is ephemeral
and will be reset periodically, so it's meant to capture more immediate
insights, issues, and learnings during the implementation process.

Append new items below any existing ones, marking them with the date and a
header.

### 2026-06-02 LOGGING-667 — Logging level tuning completion

The code-review agent identified two tree creation functions in receive_report_case_tree.py and validate_tree.py that were initially missed during the bulk update. The code-review agent correctly flagged this as a [BLOCKING] issue and provided clear evidence that all tree creation functions should be consistently at INFO level. After fixing those two functions, all tests and linters passed cleanly.

**Learning**: When bulk-updating logging levels across multiple files, use `grep` to verify consistency of the pattern before committing. The code-review agent's systematic approach caught what could have been an inconsistency in the merge.

### 2026-06-02 ISSUE-666 — Notes frontmatter and docs-build warning constraints

- `notes/*.md` frontmatter currently enforces `superseded_by` as a single
  non-empty string (not a YAML list), so split-note migrations should point
  `superseded_by` at one canonical successor and list sibling files in
  `related_notes` or body text.
- `.github/scripts/mkdocs-build-strict.sh` suppresses several known griffe
  false positives but still treats unknown-key warnings like `context` and
  `pytest` as real build failures.

### 2026-06-02 ISSUE-518 — Entrypoint docs drift in demo-facing text

- The canonical API deployment entrypoint is
  `vultron.adapters.driving.fastapi.main:app`, but demo-facing text can drift
  back to legacy module paths if not centrally referenced.
- We found stale `vultron.api.main:app` strings in demo exchange script output
  and notes. This task updated onboarding docs only; script help-text cleanup
  remains a separate follow-up candidate if those strings become user-facing
  blockers.

### 2026-06-02 ISSUE-663 — Case-actor-only broadcast guard

- `BroadcastStatusToPeersNode` needs the current executing actor to match the
  Case Manager before it should fan out participant status updates.
- Tests for the positive broadcast path need a third participant so the case
  manager has at least one non-sender peer to address.

### 2026-06-03 SCOPING — #699 (domain object migration) decomposed into 7 blocking sub-issues

`build` selected #699 ("Migrate domain objects from `wire/as2/vocab/objects/`
to `core/models/` and type `VultronActivity.object_` as discriminated union").
Scoping revealed the work is much larger than the original `size:L` estimate:

- The 7 wire types depend deeply on wire-only types (`as_Object`,
  `ActivityStreamRef[T]`, `as_NoteRef`, `as_Activity`, `VOCABULARY` registry).
- 134 files import from `vultron/wire/as2/vocab/objects/`.
- A clean move requires a parallel core class hierarchy first.

Per maintainer direction the right framing is: build a parallel core
hierarchy (analog of `as_Base`/`as_Object`), migrate domain logic into it
type-by-type, and make the wire layer a thin projection. **Key architectural
decision recorded for the ADR (#724):** refs (`FooRef` patterns) are a wire
concern — core fields hold full objects; the DataLayer hydrates on read; wire
projections handle ref-or-inline serialization at the boundary.

Sub-issues created (all blocking #699 in chain order, added to Project #24
with Schedule=Someday): #724 (foundation + ADR), #725 (Status), #726
(Embargo), #727 (Report/Record/LogEntry), #728 (Participant + roles), #729
(Case + supporting), #730 (Actor types — scope expansion). #699 itself
resized to size:S; it closes by typing `VultronActivity.object_` and removing
the `_STUB_OBJECT_MODEL_MAP` workaround once the chain lands.

No code changes in this session.

### 2026-06-05 ISSUE-808 — Orphan status scaffolding cleanup

`vultron/core/models/status.py` had no live importers anywhere in `vultron/`
or `test/`, so deleting the file was the smallest safe cleanup.

### 2026-06-05 ISSUE-799 — Rebase worktree branch to origin/main before opening PR

When creating a task branch inside a worktree slot (e.g. `wt/pinky`), always
check that the worktree branch is up to date with `origin/main` before branching.
In this session `wt/pinky` was behind `origin/main` by one commit; the naive
`git rebase origin/main` reported "already up to date" because the worktree tip
was the merge-base of `origin/main`, not its descendant. The fix:
`git merge-base origin/main <worktree-branch>` to diagnose, then
`git rebase origin/main` from the task branch after confirming the base is correct.
