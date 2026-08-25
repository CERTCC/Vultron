---
name: reflect-cycle
description: >
  Guided router for the reflection half of the development cycle — folding what
  the build process learned back into durable docs, plans, and priorities. Runs
  learn → update-plan → decision-audit → review-priorities as a sequence of
  phases, but STOPS between each phase because every one contains a human gate
  (a grill-me interview and/or its own PR). Use after a batch of build/bugfix
  work, when you want to consolidate learnings and re-rank what's next, or say
  "close the loop" / "reflect on recent work".
---

# Skill: Reflect Cycle

The mirror image of `build`/`pr-ship`: those turn plans into shipped code; this
turns shipped code back into refined plans. It sequences the four reflection
skills so you do not have to remember the order or the hand-offs — but it is a
**router, not an autopilot**.

> **Why this stops between phases (read first).** Unlike `pr-ship`, this macro
> must **not** run straight through. Each phase it dispatches contains a human
> gate the design put there on purpose:
>
> - `learn` and `decision-audit` each run a `grill-me` interview and open their
>   own docs-only PR.
> - `review-priorities` is interactive per board change.
>
> Collapsing those gates into one unattended run would defeat their purpose.
> This skill therefore dispatches **one phase, then returns here** to confirm
> before dispatching the next. It never chains a second phase on its own.

## The reflection sequence

```text
learn            → promote build learnings into specs/notes/AGENTS.md   (grill + PR)
   ↓
update-plan      → gap analysis specs/notes vs. code → new GitHub Issues
   ↓
decision-audit   → hunt stale/wrong ADRs & spec groups before they bite (grill + PR)  [periodic]
   ↓
review-priorities→ re-rank the board now that new issues exist           (interactive)
```

Not every session needs all four. `learn` and `update-plan` are the common
pair after a build batch; `decision-audit` is periodic (not every cycle);
`review-priorities` runs last, once new issues from the middle phases exist.

## Quick Start

Run the reflect-cycle skill. It will:

1. **Assess** which phases are worth running this session (see Phase Gate
   Logic) and print a short plan.
2. **Confirm** the sequence with you via `ask_user`, letting you drop phases
   you do not want (e.g. skip `decision-audit`).
3. **Dispatch one phase**, then **stop and return here**. After that phase
   completes (including any PR it opened), re-confirm before dispatching the
   next.
4. Repeat until the confirmed sequence is done or you exit.

## Phase Gate Logic

Before proposing the sequence, check what actually has input. Run these read
checks in parallel (see REFERENCE.md for exact commands):

| Phase | Include when… |
|---|---|
| `learn` | `plan/incoming/learnings/` has unprocessed `.md` files, **or** open `type:Concern` issues exist |
| `update-plan` | Always a reasonable follow-up after `learn`; also run periodically to realign issues with code |
| `decision-audit` | Periodic — propose it if it has not run recently, or if recent learnings touched an ADR/spec-group premise. Default to **off** unless there is a reason |
| `review-priorities` | Include as the closer whenever any earlier phase created new issues, or the board has a triage backlog |

Present the assembled sequence as the default; let the user trim it.

## Dispatch Model

**One phase per dispatch, then stop.** This is the core rule.

1. Announce the next phase and why.
2. Invoke that skill and let it run to completion — including its `grill-me`
   interview and any PR it opens. Do **not** interrupt a phase mid-flight.
3. When the phase returns, come back here. Print a one-line result and the
   remaining sequence.
4. Ask via `ask_user`: proceed to the next phase / skip it / stop.
5. Only on explicit confirmation, dispatch the next phase.

Never dispatch two phases without a user confirmation between them, even in
autopilot or background mode.

## Ordering Constraints

- `update-plan` runs **after** `learn` (it consumes the specs/notes `learn`
  wrote) and **before** `review-priorities` (which schedules the issues
  `update-plan` files). This ordering is load-bearing — do not reorder.
- `decision-audit`, when included, slots **after** `update-plan` and **before**
  `review-priorities`: catch stale decisions before you rank work that might
  build on them.
- Each of `learn` and `decision-audit` opens its **own** PR. Let each land (or
  at least be created) before starting the next phase, so their docs changes do
  not tangle on one branch.

## When NOT to use this

- Single learning to promote, nothing else → just run `learn`.
- Just want to re-rank the board → run `review-priorities` directly.
- You want a report, not changes → use `velocity-report` / `project-report` /
  `requirements-retrospective` (those mutate nothing).
- Turning one external Idea into a plan → `plan-issue`, not this.

## Relationship to dev-status

`dev-status` is the whole-cycle entry point: it looks at every queue (including
build and PR work) and recommends a single next skill. `reflect-cycle` is
narrower — it drives only the reflection phases, end to end. A common pattern:
`dev-status` recommends `learn`; if you know you want the full consolidation
pass, run `reflect-cycle` instead of `learn` alone.
