---
title: review-priorities Reference
---

# Review Priorities — Reference

`review-priorities` is a thin coordinator. It owns no board mechanics and no
constants of its own — it sequences the granular board skills and helps you
interpret the audit between them.

## Architecture

```text
review-priorities (coordinator)
  ├─ Phase 1: Invoke check-priority-status  (read-only audit)
  │  └─ Output: Status report (by tier, per Epic, coverage, health)
  ├─ Phase 2: Summarize significant findings for the user
  ├─ Phase 3: Interactive update loop (ask_user per action)
  │  ├─ Move item between tiers        → invoke update-priorities
  │  ├─ Promote triage item            → invoke update-priorities
  │  ├─ Add off-board issue to board   → invoke update-priorities
  │  ├─ Reshape epic roadmap           → invoke calve-epics
  │  └─ Archive completed Epic         → invoke update-priorities
  └─ Phase 4: Commit iff a delegated action wrote a file
```

The design mirrors `pr-ship` over `pr-triage`/`pr-execute`/`pr-verify`: the
coordinator adds the review-and-decide layer; the granular skills remain
independently invokable and hold the implementation.

## Where the constants and mechanics live

Do **not** duplicate any of these into this skill.

| What | Canonical home |
|---|---|
| Board node/field/option/issue-type IDs | resolve by name via `.agents/skills/shared/board-id.sh` (see `shared/README.md`) |
| Move item between tiers (GraphQL mutation) | `update-priorities` |
| Promote triage / add to board | `update-priorities` |
| Archive a completed Epic | `update-priorities` → `archive-history` |
| Board audit queries | `check-priority-status` |
| Epic roadmap shaping (route / calve / recrystallize) | `calve-epics` → `create-epic` + `manage-github-issue` |

> **Never hardcode board IDs.** They are server-generated and rotate when the
> Schedule field's options are edited. Resolve them at runtime via
> `board-id.sh`; a pasted literal drifts stale. This has caused a real
> mis-scheduling bug before.

## Phase 1: Audit

Invoke `check-priority-status`; capture its report. It provides items per tier,
per-Epic sub-issue progress, coverage (on-board vs. off-board), triage count,
stale items (>7 days), and orphaned PRs. This skill adds nothing to the query
set — if the audit is missing something, fix it in `check-priority-status`.

## Phase 2: Summarize Findings

Surface significant findings in plain text before asking for any action (empty
tiers, overcrowded Now, triage backlog, off-board issues, blocked Now items,
stale items). Recommend, do not act.

## Phase 3: Interactive Update Loop

Use `ask_user` for every choice — never ask in plain prose.

```python
while True:
    action = ask_user(
        question="What would you like to do?",
        choices=[
            "Move item(s) between Schedule tiers (Recommended)",
            "Promote Triage items to Now/Next/Later",
            "Add an off-board issue to the board",
            "Reshape the epic roadmap (route / calve / recrystallize)",
            "Archive a completed Epic",
            "No changes, exit",
        ],
    )
    if action == "No changes, exit":
        break
    # Delegate to the owning skill — do NOT inline the mutation:
    #   move / promote / add-to-board / archive  → update-priorities
    #   reshape epic roadmap                     → calve-epics
```

### Reshape the Epic Roadmap

Invoke the `calve-epics` skill — it owns the route / calve / recrystallize
judgment and gates epic creation on human confirmation of the design-grain
fracture line. `calve-epics` delegates the mechanics to `create-epic` (epic
creation + sub-issue wiring + board placement) and `manage-github-issue`
(re-parenting). Do **not** invoke `create-epic` directly from this workflow, and
never mint an epic inline.

Each delegated skill collects its own parameters (which issue, which tier, epic
details) and applies the change live. Loop back to the menu after each.

## Phase 4: Commit (if needed)

Board changes (Schedule field updates) happen live via API — no file commit
needed. If a delegated action wrote a file under `plan/history/` (via
`archive-history`) or modified notes, invoke the `commit` skill.

## Error Handling

Delegated skills own their own error handling (auth failures, item-not-on-board
offers to add it first, etc.). This coordinator only needs to stop cleanly if
`check-priority-status` cannot produce a report — without the audit there is
nothing to review.
