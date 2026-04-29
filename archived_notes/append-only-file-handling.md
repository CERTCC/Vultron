---
title: Append-Only History File Handling
status: superseded
superseded_by: specs/history-management.yaml
description: >
  Implementation guidance for agents writing to plan/*HISTORY.md append-only
  files; canonical append procedure and prohibited patterns.
  Superseded by specs/history-management.yaml (HM-01 through HM-05) and
  the append-history CLI tool introduced on 2026-04-28.
related_specs:
  - specs/project-documentation.yaml
  - specs/history-management.yaml
---

# Append-Only History File Handling

> **⚠️ SUPERSEDED** — This document describes the manual append procedure
> that was used before the `append-history` tool was introduced on
> 2026-04-28. Use `uv run append-history <type>` instead.
> See `specs/history-management.yaml` and `notes/history-management.md`.

---

Implementation guidance for agents writing to `plan/*HISTORY.md` files.
Formal requirements: `specs/project-documentation.yaml` PD-05-001 through
PD-05-005.

---

## Decision Table

| Question | Decision | Rationale |
|---|---|---|
| Which files are covered? | `plan/IMPLEMENTATION_HISTORY.md`, `plan/IDEA-HISTORY.md`, `plan/PRIORITY_HISTORY.md` | These are the only append-only log files in `plan/` |
| Where do new rules live? | Extended `specs/project-documentation.yaml` (PD-05 section) | Natural extension of existing PD-02 append-only rules |
| Canonical write tool? | `view_range(tail)` + `edit` + `tail` verification | Avoids shell escaping pitfalls; verification catches corruption |
| Existence guard pattern? | `touch <file>` then append unconditionally | `touch` is a safe idempotent no-op; avoids ls→branch decision tree |
| Full-file read before appending? | **Prohibited** | Wastes tokens; creates opportunity to insert at wrong location |
| Existence check before appending? | **Prohibited** (use `touch` guard instead) | Unnecessary complexity; `touch` handles both cases |

---

## Anti-Patterns to Avoid

### Anti-Pattern 1: Insert at Specific Location

```text
# ❌ PROHIBITED
view(plan/IDEA-HISTORY.md)             # reads entire file
# ... agent "understands structure" ...
edit(old_str="## IDEA-26040903", new_str="## IDEA-NEW\n...\n## IDEA-26040903")
# ^ inserts before an existing entry instead of appending at end
```

This anti-pattern occurs because agents read the file, understand its
structure, and then try to insert the new entry at a "semantically correct"
location (e.g., in chronological order, or before the last entry). But
append-only means always at the end — there is no correct location other than
the very end of the file.

### Anti-Pattern 2: Existence Check Decision Tree

```text
# ❌ PROHIBITED
bash("ls plan/IDEA-HISTORY.md 2>/dev/null && echo EXISTS || echo NOT FOUND")
# → if NOT FOUND: bash("cat > plan/IDEA-HISTORY.md <<EOF ... EOF")
# → if EXISTS: bash("cat >> plan/IDEA-HISTORY.md <<EOF ... EOF")
```

This pattern adds unnecessary complexity and is error-prone (the `cat <<EOF`
form has shell quoting issues). A simple `touch` handles both branches
uniformly.

### Anti-Pattern 3: Full File Read Before Appending

```text
# ❌ PROHIBITED
view(plan/IMPLEMENTATION_HISTORY.md)   # reads 3000+ lines unnecessarily
# ... wastes context window ...
edit(... appends at end ...)
```

There is no need to read the entire file to append. Only the tail is needed
to locate the end.

---

## Canonical Append Pattern

```text
# ✅ CORRECT: Canonical append procedure

# Step 1 — ensure file exists (no-op if already present)
bash("touch plan/IDEA-HISTORY.md")

# Step 2 — write new entry to temp file, then append
# Option A: write content to a temp file first, then cat-append
bash("""
cat > /tmp/new_entry.md << 'ENDOFENTRY'
---

## IDEA-NEW title

Body of the new entry.

**Processed**: 2026-04-23 — ...
ENDOFENTRY
cat /tmp/new_entry.md >> plan/IDEA-HISTORY.md
""")

# Option B: use Python for content with shell-special characters
bash("""python3 -c "
content = '''
---

## IDEA-NEW title

Body of the new entry.

**Processed**: 2026-04-23 — ...
'''
with open('plan/IDEA-HISTORY.md', 'a') as f:
    f.write(content)
" """)

# Step 3 — verify the entry was written correctly
bash("tail -30 plan/IDEA-HISTORY.md")
```

**Why NOT `view_range` + `edit` for appending?** The `edit` tool requires
`old_str` to match *exactly one occurrence* in the file. History files
contain repeated structural patterns (e.g., `**Processed**: YYYY-MM-DD`,
separator lines `---`, heading markers `## IDEA-`). If `old_str` matches more
than once, the edit silently fails. Using `cat >>` or Python `open(file, 'a')`
avoids this uniqueness problem entirely.

**Why a temp file (Option A) vs Python (Option B)?** Option A (heredoc +
`cat >>`) works well when the content has no shell-special characters.
Option B (Python) is the safe fallback when the content contains backticks,
dollar signs, single quotes, or other characters that would be misinterpreted
by the shell heredoc.

**Why `touch` in Step 1?** `cat >>` and Python `open('a')` will both create
the file if it does not exist, so Step 1 is technically redundant. It is
included as an explicit, readable intent declaration — making clear that
"ensure file exists" is a deliberate step, not an afterthought.

---

## Append-Only Files in This Project

| File | Purpose |
|---|---|
| `plan/IMPLEMENTATION_HISTORY.md` | Completed implementation tasks archive |
| `plan/IDEA-HISTORY.md` | Processed ideas archive |
| `plan/PRIORITY_HISTORY.md` | Priority change history |

All three files follow the same append-only contract: new entries go at the
end, old entries are never modified, and the canonical append procedure
(PD-05-004) applies to all of them.

---

## Testing Pattern

There are no automated tests for agent file-handling behavior; compliance is
enforced through specification and code review. When reviewing agent work
involving `plan/*HISTORY.md` files, verify:

1. New entry appears at the **end** of the file (not inserted mid-file).
2. No existing entries were modified.
3. No `ls`/`test -f` existence-check command was issued before the append.
4. The full file was not read (look for `view(plan/*HISTORY.md)` without
   a `view_range` argument — that is the anti-pattern).
