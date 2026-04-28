---
name: build
description: >
  Completes the highest-priority pending implementation task: loads project
  context, selects the next task, implements it, validates, updates plan
  history, and commits. Use when the user asks to continue planned
  implementation work or turn the next prioritized item in the implementation
  plan into a completed changeset.
---

# Skill: Build

## Quick start

1. Invoke the `study-project-docs` skill to load all specs and read project
   context.
2. Select the highest-priority unchecked task that can be completed in one run.
3. Verify the current implementation in `vultron/` and `test/` before coding.
4. Implement only the selected task, then run the required validation.
5. If validation succeeds, update plan/history files, stage changes, and commit.

## Inputs

- `repo_root` (optional, default `.`): repository root containing the plan,
  specs, source, and tests.

## Workflow

### Phase 1 - Review context

Invoke the `study-project-docs` skill. It loads all specs, reads all plan/,
docs/adr/, notes/, and AGENTS.md files, and scans vultron/ and test/.

### Phase 2 - Select work

1. Identify the highest-priority unchecked task in
   `plan/IMPLEMENTATION_PLAN.md`.
2. Use `plan/PRIORITIES.md` as authoritative, but account for prerequisites,
   blockers, dependencies, and whether the work fits in a single run.
3. Small trivial tasks at the same priority may be grouped when that avoids
   wasteful context switching.

### Phase 3 - Verify before coding

1. Search `vultron/` and `test/` to confirm the current implementation.
2. Do not assume missing functionality; verify it in code.
3. If a blocking prerequisite is discovered, you may add **at most one**
   minimal prerequisite entry to `plan/IMPLEMENTATION_PLAN.md` only when all of
   the following are true:
   - it is strictly necessary for the selected task
   - it is labeled `auto-added`
   - it includes a short title, one-line justification, and one-line
     acceptance criterion
   - the rationale is recorded in `plan/BUILD_LEARNINGS.md`
   - the commit message is prefixed `plan: add prerequisite`
4. If more than one prerequisite is required, or the prerequisite change is
   non-trivial, update `plan/BUILD_LEARNINGS.md` with details and stop.

### Phase 4 - Implement

1. Implement only the selected task.
2. Follow project conventions and keep the change focused.
3. Add or update tests for new or changed behavior.
4. Reuse existing helpers and keep the implementation DRY.
5. Sub-agents may help with implementation, but main-agent validation is
   mandatory.

### Phase 5 - Validate

1. Invoke the `format-code` skill, then `run-linters`, then `run-tests`.
2. Do not skip or delegate validation.
3. If incidental bugs are discovered, add them to `plan/BUGS.md` with clear
   reproduction notes and do not pursue them unless they block the current task.

### Phase 6 - Finalize

1. Append a completion summary to `plan/history/` using the `append-history`
   tool:

   ```bash
   cat <<'EOF' | uv run append-history implementation
   ---
   title: <short task title>
   type: implementation
   date: <YYYY-MM-DD>
   source: <TASK-ID>
   ---

   ## <TASK-ID> — <title>

   <completion summary: what was done, outcome, artifacts>
   EOF
   ```

2. Delete the completed task from `plan/IMPLEMENTATION_PLAN.md` entirely.
   Do not leave tombstones, `[x]` checkboxes, or one-line summaries — the
   task details belong in HISTORY, not in PLAN.
3. Record **observations, open questions, and constraints** discovered during
   implementation in `plan/BUILD_LEARNINGS.md`. Use a dated header per entry
   (e.g., `### 2026-04-28 LABEL — Short description`). Do **not** write
   completion summaries here — those belong in `uv run append-history
   implementation` (step 1 above).
4. Invoke the `commit` skill with a clear, specific message.

## Constraints

- Preserve focus on a single task, or a tightly related set of trivial tasks.
- Do not modify unrelated tasks.
- Do not skip validation.
- Each run starts in a fresh context.
- The single-prerequisite exception is narrow and does not authorize broader
  plan edits.
