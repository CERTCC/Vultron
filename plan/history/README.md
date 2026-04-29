# plan/history — Project History Archive

This directory is the archive for all project history records.

## Structure

```text
plan/history/
  README.md                    ← this file
  IMPLEMENTATION_HISTORY.md    ← legacy archive (pre-2026-04-28)
  IDEA-HISTORY.md              ← legacy archive (pre-2026-04-28)
  PRIORITY_HISTORY.md          ← legacy archive (pre-2026-04-28)
  YYMM/                        ← monthly directory (e.g., 2604/)
    README.md                  ← auto-generated index for that month
    idea/
      IDEA-XXXXXXXX.md         ← per-entry write-once files
    implementation/
      TASK-XXXXX.md
    learning/
      LEARN-XXXXXX.md
    priority/
      PRIORITY-XXXXXX.md
```

## Legacy Files

The three files at the top level of this directory
(`IMPLEMENTATION_HISTORY.md`, `IDEA-HISTORY.md`, `PRIORITY_HISTORY.md`) are
**legacy archives**. They were created as monolithic append-only files before
the structured per-entry format was adopted on **2026-04-28**.

These files are retained for historical reference and are no longer modified.
All new history entries are written as individual files under monthly
subdirectories using the `append-history` tool.

## Adding New History Entries

Use the `append-history` CLI tool — do **not** append to the legacy files:

```bash
# Write a new idea history entry (reads from stdin)
echo "..." | uv run append-history idea

# Write from a file
uv run append-history implementation --file /path/to/summary.md
```

See `specs/history-management.yaml` (HM-01 through HM-05) and
`notes/history-management.md` for the full specification and design details.

## Agent Context Note

`plan/history/` is **not** part of the default agent orientation context.
Agents reading `plan/` during their startup phase should read only `plan/*.md`
(the active planning files). Read `plan/history/` only when specifically
investigating historical changes or extracting lessons from prior work.

When investigating history, start with the monthly `README.md` index (e.g.,
`plan/history/2604/README.md`) to identify relevant entry files before opening
individual entries.
