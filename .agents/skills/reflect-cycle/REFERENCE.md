---
title: reflect-cycle Reference
---

# Reflect Cycle — Reference

Router that sequences the reflection-half skills with a human-confirmation stop
between each. Owns no domain logic of its own — it only assesses inputs, orders
phases, and dispatches.

## Architecture

```text
reflect-cycle (router)
  ├─ Assess phase inputs (read-only, parallel checks)
  ├─ Propose sequence via ask_user (user may trim phases)
  └─ Loop: dispatch ONE phase → phase runs to completion (grill + PR) →
           return here → ask_user (next / skip / stop)

Dispatched skills (each independently invokable, each owns its mechanics):
  learn → update-plan → [decision-audit] → review-priorities
```

Contrast with `pr-ship`: that runs its sub-skills unattended in one pass
because none has a mid-pipeline human gate. Every phase here does, so the loop
re-confirms between phases and never chains on its own.

## Phase Gate Checks

Run these in parallel before proposing the sequence. All are read-only.

### Incoming learnings (gates `learn`)

```bash
find plan/incoming/learnings -maxdepth 1 -name '*.md' ! -name '.gitkeep' | wc -l
```

Non-zero → `learn` has input.

### Open Concern issues (also gates `learn`)

```bash
gh issue list --repo CERTCC/Vultron --state open --limit 200 \
  --json number,title,issueType \
  --jq '[.[] | select(.issueType.name == "Concern")] | length'
```

Non-zero → `learn` has Concern input even if the learnings dir is empty.

### Triage backlog (informs `review-priorities` as closer)

```bash
bash .agents/skills/shared/query-now-epics.sh   # context on current Now work
# Someday/triage count comes from check-priority-status, invoked by review-priorities
```

### decision-audit recency (gates `decision-audit`)

There is no queue for this; it is periodic. Propose it when:

- recent learnings or PRs touched a premise recorded in an ADR or spec group, or
- it has not run in several reflection cycles.

Default to **off** — include only with a stated reason. Check recent history:

```bash
uv run show-history --month "$(date +%y%m)" 2>/dev/null | grep -i 'decision-audit' || echo "no recent decision-audit"
```

(Do not call `date` inside a workflow script — this command is for interactive
use in the skill run only.)

## Dispatch Loop (pseudocode)

```python
sequence = propose_sequence(gate_checks)          # e.g. [learn, update-plan, review-priorities]
sequence = ask_user_to_trim(sequence)             # user may drop decision-audit, etc.

for phase in sequence:
    choice = ask_user(
        question=f"Next phase: {phase}. Proceed?",
        choices=["Proceed", f"Skip {phase}", "Stop reflect-cycle"],
    )
    if choice == "Stop reflect-cycle":
        break
    if choice.startswith("Skip"):
        continue
    invoke_skill(phase)          # runs to completion, incl. its grill-me and PR
    report_one_line_result(phase)
    # loop returns here; next iteration re-confirms before the following phase
```

The `ask_user` **before** each dispatch is mandatory — it is the gate that
keeps this a router, not an autopilot.

## Ordering (load-bearing)

1. `learn` first — writes specs/notes/AGENTS.md from build learnings + Concerns.
2. `update-plan` next — gap-analyzes those specs/notes against code, files
   GitHub Issues for gaps. Must follow `learn`.
3. `decision-audit` (optional) — before ranking, catch stale ADR/spec-group
   premises so you do not schedule work built on a bad assumption.
4. `review-priorities` last — schedules the issues the middle phases created.

Do not reorder. `review-priorities` before `update-plan` would rank a board
that is missing the new gap issues.

## PR Isolation

`learn` and `decision-audit` each open their own docs-only PR (labels
`specs-notes` and the decision-audit default respectively). Let each phase
create its PR before dispatching the next, so two phases' doc edits do not share
a branch. `update-plan` and `review-priorities` do not open PRs (they create
issues / apply live board changes), so no branch isolation is needed for them.

## What this skill must NOT do

- Do not run two phases without a user confirmation between them.
- Do not re-implement any phase's logic — dispatch the real skill.
- Do not open its own PR — each dispatched phase owns its own.
- Do not mutate specs, notes, issues, or the board directly.
