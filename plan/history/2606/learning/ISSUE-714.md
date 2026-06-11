---
source: ISSUE-714
timestamp: '2026-06-11T18:37:53.187598+00:00'
title: Decomposed BT nodes must preserve alternate context seams
type: learning
---

## 2026-06-10 ISSUE-714 — Decomposed BT nodes must preserve alternate context seams

- When replacing a god node with leaf-node sequences, preserve all original
  input seams (`case_id` from blackboard and `case_obj`-derived context).
- If downstream leaves rely on blackboard keys, add explicit fallback reads
  from staged objects/status context to avoid regressing valid call paths.

**Promoted**: 2026-06-11 — captured in `notes/bt-integration.md` §
"Decomposed BT Nodes Must Preserve Alternate Context Seams".
Docs PR: <https://github.com/CERTCC/Vultron/pull/900>.
