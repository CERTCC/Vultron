---
name: review-priorities
description: >
  Audit and update Project #24 ("Vultron Planning") in one guided workflow.
  Delegates to check-priority-status for the read-only audit, reviews the
  findings with you, then delegates to update-priorities (tier moves, promote
  triage, add to board, archive Epics) and calve-epics (epic roadmap shaping)
  for any changes. Use when you want to review where the project stands and
  make any necessary board updates in a single session.
---

# Review Priorities

Guided coordinator over the granular board skills. It runs the audit, helps you
interpret it, then applies whatever changes you decide on — without
re-implementing any of them. Think of it as `pr-ship` for the board:
`check-priority-status` → review → `update-priorities` / `calve-epics`, all in
one pass.

> **Single source of truth.** This skill does **not** carry its own copy of
> board constants or API mutations. The audit lives in `check-priority-status`;
> tier moves / promote / archive live in `update-priorities`; epic roadmap
> shaping lives in `calve-epics`; board IDs are resolved by name via
> `.agents/skills/shared/board-id.sh` (see `.agents/skills/shared/README.md`).
> If you need a constant, resolve it there — do not hardcode one here.

## When to use which board skill

| You want to… | Run |
|---|---|
| Just see where things stand (no changes) | `check-priority-status` |
| Apply specific tier moves you already know you want | `update-priorities` |
| Shape the epic roadmap (route / calve / recrystallize) | `calve-epics` |
| Audit **and** decide **and** apply, in one session | `review-priorities` (this) |

## Quick Start

Run the review-priorities skill. It will:

1. **Audit** — invoke `check-priority-status` and capture its report.
2. **Review with you** — surface the significant findings (empty tiers, stale
   items, triage backlog, off-board issues, blocked Now items) in plain text.
3. **Update** — for any change you choose, invoke the owning skill
   (`update-priorities`, `calve-epics`) to apply it live. Loop until done.
4. **Commit** — only if a delegated action wrote a file (e.g. an
   `archive-history` entry). Pure board moves are live and need no commit.

## Workflow

### Phase 1 — Audit (delegate)

Invoke the `check-priority-status` skill. It queries Project #24 by Schedule
tier, resolves live issue/PR state and formal blockers, and prints the full
report (summary, per-tier progress, coverage audit, health check). Capture
that output — it is the input to Phase 2.

Do not re-query the board here; `check-priority-status` **is** the audit.

### Phase 2 — Review Findings

Summarize the findings that likely warrant action, before asking for any
change. Example:

```text
📊 Board status:
  Now:     3 Epics (12 open sub-issues, 2 blocked)
  Next:    2 Epics (8 open sub-issues)
  Later:   1 Epic  (4 open sub-issues)
  Someday: 7 items (triage needed)

⚠ 14 open issues not yet on board
⚠ 3 stale items (>1 week inactive)
```

Offer your read on what might need updating, but make no changes yet.

### Phase 3 — Update Loop (delegate)

Ask, via `ask_user`, what to do. For any action other than "exit", invoke the
owning skill — do not inline the GraphQL mutation here.

```text
What would you like to do?
  [A] Move item(s) between Schedule tiers        → update-priorities
  [B] Promote Triage items to Now/Next/Later     → update-priorities
  [C] Add an off-board issue to the board        → update-priorities
  [D] Reshape the epic roadmap                    → calve-epics
  [E] Archive a completed Epic                    → update-priorities
  [F] No changes, exit
```

- `update-priorities` owns the move / promote / add-to-board / archive
  mechanics and their (resolved, never hardcoded) constants.
- `calve-epics` owns epic roadmap shaping: routing uncovered leaves onto the
  epic they match, calving a new epic off an over-accumulated theme, or
  recrystallizing a muddled forest. It gates epic creation on a human
  confirming the design-grain fracture line, then delegates mechanics to
  `create-epic` and `manage-github-issue`. **Never mint an epic inline here.**

Loop back to this menu after each action until the user chooses exit.

### Phase 4 — Commit (if needed)

Board changes (Schedule field updates) take effect immediately via API — no
file commit is needed for pure scheduling changes.

If a delegated action wrote a file under `plan/history/` (via
`archive-history`) or modified notes, invoke the `commit` skill.

## Notes

- **Review-first**: Always audit before updating. Findings inform decisions.
- **User control**: No automatic changes — you decide each update.
- **No duplication**: This skill coordinates; it never re-implements the audit,
  the mutations, or epic shaping. When board mechanics change, only
  `check-priority-status`, `update-priorities`, `calve-epics`, and `shared/`
  need editing.
- **Undo**: Board moves reverse by moving the item back; closed Epics reopen
  with `gh issue reopen`.
