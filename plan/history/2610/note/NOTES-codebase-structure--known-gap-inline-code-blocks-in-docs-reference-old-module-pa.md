---
source: NOTES-codebase-structure--known-gap-inline-code-blocks-in-docs-reference-old-module-pa
timestamp: '2026-10-02T16:25:54.312695+00:00'
title: 'Known Gap: Inline Code Blocks in `docs/` Reference Old Module Paths'
type: note
---

**Archived:** 2026-10-02
**Reason:** confusion-resolved — no docs/ page outside ADRs references vultron.as_vocab any more
**Superseded by:** vultron.wire.as2.vocab (current module paths in docs/)

---

## Known Gap: Inline Code Blocks in `docs/` Reference Old Module Paths

Several Python inline code examples in `docs/` reference old module paths
(e.g., `vultron.as_vocab.*`) that were moved to `vultron.wire.as2.vocab.*`
during the P60-1 package relocation. Run `mkdocs build` to surface errors,
then update the affected code blocks.

---
