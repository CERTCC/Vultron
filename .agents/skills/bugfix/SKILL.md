---
name: bugfix
description: >
  Fix a bug using test-first development. Invokes the BUGFIX.md prompt
  workflow but gates implementation on confirmed shared understanding with
  the user. Use when the user asks to fix a bug or run the bugfix workflow.
---

# Skill: Bugfix (with clarification gate)

This skill wraps the project's `@.github/prompts/BUGFIX.md` workflow and adds
a mandatory clarification step before any code is written. No implementation
work begins until both the agent and the user agree on what bug is being fixed
and why.

## Phase 1 — Identify the Bug

1. Open `plan/BUGS.md` and read all open entries.
2. Select the highest-priority open bug according to the priority ordering in
   `plan/BUGS.md` (and cross-referenced with `plan/PRIORITIES.md` if present).
3. Summarise the selected bug for the user:
   - Bug ID / title
   - One-sentence description of the observed vs. expected behaviour
   - The file(s) / component(s) most likely involved

## Phase 2 — Clarify (BLOCKING)

Before writing any code or tests, use the `ask` tool to verify shared
understanding with the user. Ask **one question at a time**. Continue asking
until every open question is resolved. Do **not** skip this phase even if the
bug description looks unambiguous.

Mandatory questions (ask each one in turn; stop early if the user signals
sufficient clarity):

1. **Confirm the selected bug**: "I'm planning to work on [bug title]. Is that
   the right bug to address right now, or would you prefer a different one?"

2. **Confirm reproduction scenario**: "My understanding of the bug is
   [description]. Does that match what you're seeing?" — If no, ask the user
   to describe it in their own words and update your understanding accordingly.

3. **Confirm expected behaviour**: "The fix should make [expected behaviour]
   happen. Is that correct?" — Probe for edge-cases if any are unclear.

4. **Confirm scope**: "Do you want this fix scoped to [identified
   files/component], or are there other areas that should change?" — Ask about
   related tests, docs, or migration concerns.

5. **Open questions**: If any assumption is still unclear after the four
   questions above, continue asking until it is resolved.

**Do not proceed to Phase 2b until the user has explicitly confirmed or
corrected each point.** If the user provides a correction, restate your updated
understanding and ask them to confirm before moving on.

## Phase 2b — Root Cause Depth (BLOCKING)

After Phase 2 alignment is confirmed, check whether the user has already
indicated a broader underlying issue. If not, ask one more targeted question
before locking in scope:

> "My working theory for the root cause is [specific code path / invariant /
> data flow you identified]. Does this look like an isolated defect, or might
> it be a symptom of a deeper issue in [module / design pattern]?"

- If the user says **isolated defect**: proceed to Phase 3.
- If the user says **deeper issue**: ask which of the related concerns this
  fix should address, then file the remaining concerns as new bugs in
  `plan/BUGS.md` (see Constraints). Confirm the narrowed scope before
  proceeding.

See `specs/bugfix-workflow.md` BFW-02-001 through BFW-02-004 and
`notes/bugfix-workflow.md` for question templates and escalation patterns.

**Do not proceed to Phase 3 until Phase 2b scope is confirmed.**

## Phase 3 — Implement (follows BUGFIX.md)

Once shared understanding is confirmed, follow `@.github/prompts/BUGFIX.md`
starting at step 3 ("Verify Before Changes"):

1. **Verify Before Changes** — Search `vultron/` and `test/` to confirm the
   bug exists as understood. Do not assume; confirm via code search.

2. **Reproduce with a Failing Test** — Add or modify a test that fails due to
   the bug. Confirm the test fails before implementing the fix.

3. **Implement the Fix** — Modify only the code required to resolve the bug.
   Follow all project conventions (formatting, linting, layer rules).

4. **Iterate** — Run validation; refine until all relevant tests pass. Any
   incidental bugs discovered go into `plan/BUGS.md`; do not pursue them now.

5. **Finalize**
   - Append a completion summary (bug ID, symptoms, root cause, fix) to
     `plan/IMPLEMENTATION_HISTORY.md` using the template in
     `notes/bugfix-workflow.md`.
   - Remove the bug's entry entirely from `plan/BUGS.md`. Do not leave a
     tombstone, `FIXED` marker, or closed-notice — see `specs/bugfix-workflow.md`
     BFW-04-002.
   - If any other bugs in `plan/BUGS.md` are already marked fixed, archive and
     remove them opportunistically (BFW-04-004).
   - Capture lessons learned in `plan/IMPLEMENTATION_NOTES.md`.
   - `git add` and commit with a clear, specific message. Reference any new
     bugs filed during Phase 2b analysis (e.g., `Also filed: BUG-YYMMDDXX`).

## Constraints

- **Implementation is blocked** until Phase 2 AND Phase 2b both produce
  confirmed shared understanding. This is non-negotiable.
- Follow test-first discipline; never fix before the failing test exists.
- Do not work on implementation-plan tasks while bugs remain.
- Do not pursue incidental bugs discovered during implementation; file them
  in `plan/BUGS.md` instead.
- When Phase 2b surfaces additional issues, file each as `BUG-YYMMDDXX` and
  implement only the confirmed-scope fix in the current run.
- `plan/BUGS.md` MUST contain only open bugs; remove fixed entries entirely.
- Run `uv run black vultron/ test/ && uv run flake8 vultron/ test/` before
  committing.
- Run the full test suite exactly once per validation cycle:
  `uv run pytest --tb=short 2>&1 | tail -5`
- Each run operates in a fresh context; do not carry forward assumptions from
  previous sessions.
