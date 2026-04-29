---
name: condense-agents-md
description: >
  Condense AGENTS.md files that have grown too large by migrating content to
  per-directory AGENTS.md files and notes/ references. Use when root AGENTS.md
  exceeds ~400 lines, or when asked to clean up, condense, or restructure
  AGENTS.md.
---

# Skill: Condense AGENTS.md

## Purpose

Root AGENTS.md files grow over time as pitfalls accumulate. This skill trims
them by migrating content to two destinations:

1. **Per-directory `AGENTS.md`** — subsystem-specific rules land in the
   directory they govern (e.g., `test/AGENTS.md`, `specs/AGENTS.md`).
2. **`notes/` references** — pitfall write-ups that already have (or should
   have) a canonical `notes/` file are replaced by a single-line pointer.

Target: root `AGENTS.md` ≤ 400 lines.

## Workflow

### Phase 1 — Audit

```bash
bash .agents/skills/condense-agents-md/scripts/audit.sh AGENTS.md
```

Shows: each `##`/`###` section, its line count, the running total, and the
excess over the 400-line target.

### Phase 2 — Categorize

For every section over-budget, classify it using the rules in
[REFERENCE.md](REFERENCE.md):

| Label | Meaning |
|---|---|
| `KEEP` | Essential orientation — stays in root |
| `MOVE:path/AGENTS.md` | Subsystem-specific — move to that file |
| `REF:notes/x.md` | Already in notes/ — replace with one-liner |
| `NEW-NOTE:notes/x.md` | No existing home — create new notes/ file, then REF |

### Phase 3 — Plan and get approval

Present the migration table (section → action → destination → rationale) to
the user via `ask_user`. Do **not** modify any files before approval.

### Phase 4 — Execute

For each migration:

- **REF / NEW-NOTE**: append content as a new `##` section at the bottom of
  the target notes/ file (create with frontmatter if new — see
  [REFERENCE.md](REFERENCE.md)); replace the root section with a one-liner:
  `See [notes/x.md](notes/x.md) for <topic>.`
- **MOVE**: append content to the per-directory AGENTS.md (create if needed);
  remove the section from root entirely.
- **KEEP**: leave untouched.

### Phase 5 — Validate and commit

1. `wc -l AGENTS.md` — verify within target.
2. `./mdlint.sh` — lint all modified markdown files.
3. Commit: `docs: condense AGENTS.md — migrate <N> sections`.

## Hard rules

- **Never delete content** — always move to a destination.
- Keep the `## Common Pitfalls` heading in root as a short index of one-liners.
- When appending to an existing notes/ file, update its frontmatter
  (`related_notes`, `related_specs`) to reflect the new content.
- New notes/ files MUST include the required frontmatter (`title`,
  `status: active`). See [REFERENCE.md](REFERENCE.md) for the template.
