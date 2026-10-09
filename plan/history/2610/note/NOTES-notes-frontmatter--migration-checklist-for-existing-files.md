---
source: NOTES-notes-frontmatter--migration-checklist-for-existing-files
timestamp: '2026-10-02T16:20:19.332767+00:00'
title: Migration Checklist for Existing Files
type: note
---

**Archived:** 2026-10-02
**Reason:** delivered — every notes/*.md carries frontmatter; checklist cited retired specs/*.md
**Superseded by:** NF-06-001, NF-06-002; notes/notes-frontmatter.md schema

---

## Migration Checklist for Existing Files

For each `notes/*.md` file (except `README.md`), add a frontmatter block with:

1. `title`: copy from the `# H1` heading
2. `status`: choose from `active | draft | superseded | archived` based on
   the file's current relevance
3. `description`: paste or paraphrase the first paragraph or "Load when" line
4. `related_specs`: list any `specs/*.md` files explicitly cross-referenced
5. `related_notes`: list any other `notes/*.md` files cross-referenced
6. `relevant_packages`: list any Python packages central to the topic

Most files warrant `status: active`. Files that have been explicitly replaced
should use `status: superseded` with `superseded_by` pointing to the replacement.

---
