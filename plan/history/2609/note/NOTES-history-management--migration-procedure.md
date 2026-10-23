---
source: NOTES-history-management--migration-procedure
timestamp: '2026-09-17T17:25:21.536038+00:00'
title: Migration Procedure
type: note
---

**Archived:** 2026-09-17
**Reason:** (a) one-time move completed
**Superseded by:** plan/history/

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
