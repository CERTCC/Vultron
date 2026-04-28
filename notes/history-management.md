---
title: "History Management: Chunked Per-Entry Files"
status: active
description: >
  Design decisions and implementation guidance for the chunked history file
  system. Replaces the monolithic append-only plan/*HISTORY.md pattern with
  per-entry write-once files under plan/history/, managed by the
  append-history CLI tool.
related_specs:
  - specs/history-management.yaml
related_notes:
  - notes/append-only-file-handling.md
  - notes/plan-history-management.md
  - notes/plan-organization.md
---

# History Management: Chunked Per-Entry Files

## Overview

This note captures the design decisions behind `specs/history-management.yaml`
(IDEA-26042702) and provides implementation guidance for the `append-history`
tool and the migration from monolithic `plan/*HISTORY.md` files.

---

## Decision Table

| Question | Decision | Rationale |
|---|---|---|
| Which history files are in scope? | All `*HISTORY.md` files, including any future additions | Uniform treatment avoids per-file special cases |
| Where do history files live? | `plan/history/` subdirectory | Separates archive from active planning; prevents agents from reading history during orientation |
| Chunking granularity? | Monthly (YYMM suffix in directory name) | Recent history is most relevant; monthly chunks keep the current month manageable |
| File structure per entry? | Individual write-once files: `plan/history/YYMM/<type>/<entry-id>.md` | Clean git diffs (new file added, not existing file edited); enables YAML frontmatter per entry |
| Month-level navigation? | Auto-generated `plan/history/YYMM/README.md` rebuilt by the tool on every append | Agents can read one file for the month's summary instead of opening every entry |
| Top-level static README? | Yes — `plan/history/README.md` explains legacy files and the transition date | Documents the migration boundary for future readers |
| Legacy file migration? | Move monolithic files to `plan/history/` top level as static archives | Cannot be split retroactively without manual effort; grandfathered content preserved |
| Tool interface? | `uv run append-history <type>` — stdin by default, `--file <path>` alternative | Matches project tooling (parallel to `spec-dump`); piping is the most common agent use case |
| Date determination? | Always use current system clock | No agent decision-making about which month file to target |
| Type validation? | `HistoryEntryType` StrEnum in `vultron/metadata/history/types.py` | Adding a new type requires only one line change |
| Module location? | `vultron/metadata/history/` — sibling of `vultron/metadata/specs/` | Both are project-management metadata tools; co-location signals intent |
| Agent context boundary? | `plan/history/` is explicitly excluded from default "read plan context" | Prevents agents from spending context tokens on historical archive during orientation |
| Skill updates? | `build`, `ingest-idea`, `learn` skills must use `append-history` for writes | Skills that directly append to history files must be updated to use the tool |

---

## Directory Layout

```text
plan/
  history/
    README.md                         ← static: explains legacy files + migration date
    IMPLEMENTATION_HISTORY.md         ← legacy archive (moved here, not split)
    IDEA-HISTORY.md                   ← legacy archive (moved here, not split)
    PRIORITY_HISTORY.md               ← legacy archive (moved here, not split)
    2604/
      README.md                       ← auto-generated index for April 2026
      idea/
        IDEA-26042702.md              ← chunked history entry
      implementation/
        TASK-BTND5.md
      priority/
        PRIORITY-26042601.md
    2605/
      README.md
      implementation/
        TASK-CC.md
```

---

## Entry File Format

Each entry file has a YAML frontmatter block followed by a Markdown body:

```markdown
---
title: "Chunked history files (IDEA-26042702)"
type: idea
date: 2026-04-28
source: IDEA-26042702
---

## IDEA-26042702 "History" files should be chunked by time…

<full original idea text>

**Processed**: 2026-04-28 — design decisions captured in
`specs/history-management.yaml` (HM-01 through HM-05) and
`notes/history-management.md`.
```

---

## `append-history` Tool

### Location

```text
vultron/metadata/history/
  __init__.py
  types.py          ← HistoryEntryType StrEnum
  cli.py            ← main() entry point
  readme_gen.py     ← README.md regeneration logic
```

### pyproject.toml registration

```toml
[project.scripts]
append-history = "vultron.metadata.history.cli:main"
```

### CLI Signature

```text
append-history <type> [--file <path>]
```

- `<type>`: one of `idea`, `implementation`, `priority` (or any future
  `HistoryEntryType` value)
- Content is read from stdin by default; `--file <path>` reads from a file

### Usage Examples

```bash
# From stdin (most common agent use case)
cat /tmp/entry.md | uv run append-history idea

# From file
uv run append-history implementation --file /tmp/task-summary.md

# Inline (short entries)
echo "## TASK-FOO completed..." | uv run append-history implementation
```

### Behaviour Sequence

1. Parse `<type>` against `HistoryEntryType`; exit 1 on unknown type.
2. Read content from stdin or `--file <path>`.
3. Determine current month: `datetime.date.today().strftime("%y%m")` → `YYMM`.
4. Parse the content's YAML frontmatter to extract `<entry-id>` (the `source`
   field, falling back to a timestamp-based name if absent).
5. Create `plan/history/YYMM/<type>/` if missing.
6. Write content to `plan/history/YYMM/<type>/<entry-id>.md`.
7. Regenerate `plan/history/YYMM/README.md` from all entry frontmatter in
   that month's directory.
8. Print the written file path to stdout.

---

## README Generation

The `plan/history/YYMM/README.md` is a summary table:

```markdown
# History: April 2026

| Date | Type | Source | Title |
|------|------|--------|-------|
| 2026-04-28 | idea | IDEA-26042702 | "History" files should be chunked… |
| 2026-04-27 | implementation | TASK-BTND5 | Generalize Participant BT Nodes |
```

Sorted by date descending, then type. Generated by scanning
`plan/history/YYMM/**/*.md` (excluding `README.md`) and reading frontmatter.

---

## Migration Procedure

1. Create `plan/history/` directory.
2. Move `plan/IMPLEMENTATION_HISTORY.md` → `plan/history/IMPLEMENTATION_HISTORY.md`.
3. Move `plan/IDEA-HISTORY.md` → `plan/history/IDEA-HISTORY.md`.
4. Move `plan/PRIORITY_HISTORY.md` → `plan/history/PRIORITY_HISTORY.md`.
5. Write `plan/history/README.md` explaining the legacy files and migration date.
6. Update `AGENTS.md`, `notes/append-only-file-handling.md`,
   `notes/plan-history-management.md`, `.agents/skills/build/SKILL.md`,
   `.agents/skills/ingest-idea/SKILL.md`, `.agents/skills/learn/SKILL.md`,
   and `.agents/skills/study-project-docs/SKILL.md`.
7. Delete `tools/migrate_spec_md_to_yaml.py` (vestigial script).

---

## Agent Context Boundary

During the standard orientation phase (`study-project-docs` Step 2), agents
read `plan/*.md`. The `plan/history/` subdirectory is **explicitly excluded**
from this step.

Agents SHOULD read `plan/history/` only when:

- Investigating a regression introduced in a recently completed task.
- Extracting lessons from prior implementation work (the `learn` skill).
- Auditing what was shipped in a given time window.

When accessing historical entries, prefer reading the monthly README first
(`plan/history/YYMM/README.md`) to identify which entry files are relevant,
then open only the specific files needed.

---

## Skill Update Summary

| Skill | What changes |
|---|---|
| `build` | Replace direct append to `plan/IMPLEMENTATION_HISTORY.md` with `uv run append-history implementation` |
| `ingest-idea` | Replace direct append to `plan/IDEA-HISTORY.md` with `uv run append-history idea` |
| `learn` | Remove direct reads of `plan/*HISTORY.md`; rely on `study-project-docs` for plan context |
| `study-project-docs` | Add explicit note that Step 2 covers `plan/*.md` only, NOT `plan/history/` |

---

## Relation to IDEA-26042801

IDEA-26042801 (build skill notes vs. history distinction) is closely related.
The `append-history` tool introduced here is the mechanism by which the `build`
skill will write *status* entries (what was done) to history, keeping
`IMPLEMENTATION_NOTES.md` (or its successor) focused on *learnings*. The two
ideas are designed to be implemented together: this spec provides the
infrastructure; IDEA-26042801 provides the usage policy for the `build` skill.

---

## Testing Pattern

```python
# test/metadata/test_append_history.py
import subprocess
from pathlib import Path

def test_append_creates_entry_file(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    content = "---\ntitle: Test\ntype: idea\ndate: 2026-04-28\nsource: IDEA-TEST\n---\n\nBody."
    result = subprocess.run(
        ["uv", "run", "append-history", "idea"],
        input=content,
        text=True,
        capture_output=True,
    )
    assert result.returncode == 0
    entry_files = list(Path("plan/history").rglob("*.md"))
    assert any("IDEA-TEST" in f.name for f in entry_files)

def test_append_regenerates_readme(tmp_path, monkeypatch):
    # After append, plan/history/YYMM/README.md should exist
    ...

def test_invalid_type_exits_nonzero():
    result = subprocess.run(
        ["uv", "run", "append-history", "bogus_type"],
        input="content",
        text=True,
        capture_output=True,
    )
    assert result.returncode != 0
```
