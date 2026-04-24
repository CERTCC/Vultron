---
title: Bugfix Workflow — Implementation Notes
status: active
description: >
  Design decisions and implementation patterns for the test-first bugfix
  workflow.
related_specs:
  - specs/bugfix-workflow.md
---

# Bugfix Workflow — Implementation Notes

Design decisions, implementation patterns, and examples for the bugfix skill
requirements in `specs/bugfix-workflow.md`.

---

## Decision Table

| Question | Decision | Rationale |
|----------|----------|-----------|
| Should deeper root-cause analysis be a new phase or woven into Phase 2? | New Phase 2b — a distinct gate | Keeps Phase 2 focused on basic alignment; Phase 2b is a conditional follow-up that fires only when scope hasn't already been addressed. |
| When should Phase 2b fire? | Only if Phase 2 has not already surfaced broader scope | Avoids redundant questions when the user has already indicated the issue is larger. |
| What should Phase 2b questions reference? | Specific code paths and invariants found by the agent | Open-ended questions invite unhelpful "I don't know" answers; grounded questions drive useful answers. |
| When Phase 2b surfaces multiple issues, what happens to them? | Each filed as a new `BUG-YYMMDDXX` in `plan/BUGS.md` | Keeps current run focused; new bugs surface for future runs without being lost. |
| Where should fixed bugs be archived? | `plan/IMPLEMENTATION_HISTORY.md` | Bug fixes are implementation history; a single history file avoids proliferating files. |
| Should fixed bugs leave a tombstone in `BUGS.md`? | No — remove entirely | `BUGS.md` is a work queue; closed items in a work queue are noise. History belongs in the history file. |
| What if a bug was already marked fixed but never archived? | Archive it the next time any agent opens `BUGS.md` | Cleanup is opportunistic to avoid permanent debt accumulation. |

---

## Phase 2b — Pattern

After the four standard Phase 2 questions, check whether scope has already
been broadened. If not, ask one targeted question:

```text
"My working theory for the root cause is [specific code path / invariant /
data flow]. Does this look like an isolated defect, or might it be a symptom
of a deeper issue in [module / design pattern]?"
```

If the user says "deeper issue":

```text
"I can see at least [N] related concerns:
  1. [issue A]
  2. [issue B]
Which should this fix address? I'll file the others as new bugs."
```

If the user says "just the surface fix":

> Proceed directly to Phase 3.

---

## Escalation — Pattern

When filing newly discovered bugs during analysis:

```markdown
## BUG-YYMMDDXX — <short title> — NEW

**Symptoms:** <one sentence>

**Root cause (hypothesis):** <what was observed during analysis of BUG-X>

**Components involved:**
- `path/to/module.py`

**Resolution steps:** (to be determined)
```

Reference them in the commit message:

```text
fix: <short description of confirmed fix>

Addresses BUG-YYMMDDXX.
Also filed: BUG-YYMMDDZZ (related issue discovered during analysis).

Co-authored-by: Copilot <223556219+Copilot@users.noreply.github.com>
```

---

## Bug Archive Format (IMPLEMENTATION_HISTORY.md)

Append bug fix summaries at the **end** of `plan/IMPLEMENTATION_HISTORY.md`.
Use the same section format as build-skill completions:

```markdown
## BUG-YYMMDDXX — <title> (FIXED YYYY-MM-DD)

**Symptoms**: <one sentence describing observed vs expected behaviour>

**Root cause**: <concise technical explanation>

**Fix**: <what was changed and why>

**Components changed**:
- `path/to/file.py`
- `test/path/to/test_file.py`

**Lessons learned** (optional): <any insights for future work>
```

---

## Skill Integration Notes

### `plan/BUGS.md` lifecycle

```text
New bug filed  →  open entry in BUGS.md
                       ↓
              Agent confirms + scopes fix (Phase 2 + 2b)
                       ↓
              Fix implemented, tests pass
                       ↓
              Summary appended to IMPLEMENTATION_HISTORY.md
                       ↓
              Entry REMOVED from BUGS.md (no tombstone)
```

### Already-fixed stragglers

When an agent opens `BUGS.md` and finds entries with `Status: FIXED`:

1. For each such entry, append an archive entry to
   `IMPLEMENTATION_HISTORY.md` using available information from the bug body.
2. Remove the entry from `BUGS.md`.
3. If this is an incidental cleanup (not the main task), include it in the
   commit for the main task under a "housekeeping" note.

### Relationship to grill-me

Phase 2b is not a full grill-me session; it is one targeted question that
escalates into a brief structured exchange only if the user confirms a deeper
issue. Reserve full grill-me for architectural decisions, not individual bugs.

### Layer and import rules

These requirements govern agent skill `SKILL.md` files and `plan/` documents
only — they have no impact on `vultron/` source code layers.
