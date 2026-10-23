---
title: Leaf modules sitting at the BTND-07-004 500-line cap block documentation edits
type: learning
timestamp: "2026-07-30T22:05:00+00:00"
source: ISSUE-1777-b
signal: concern
---

`vultron/core/behaviors/sync/nodes/chain.py` was at 500 lines exactly — the
BTND-07-004 leaf-module cap. Issue #1777 AC-4 asked for an *audit* of
`_CASE_AUTHORED_SIGNATURES` / `_CANONICAL_PAYLOAD_SIGNATURES`, and simply
recording the audit findings as comments pushed the file to 514 lines and failed
`test_btnd07_structure.py::test_leaf_module_line_count`. The file also already
contained a `# noqa: E501  # fmt: skip` line cramming three tuples onto one
physical line, which is the same pressure showing up as a formatting hack.

**Why:** A file resting exactly at the cap makes any documentation or comment
addition a structural refactor. That creates pressure to either skip the
documentation or smuggle it in with formatting tricks — both worse than
splitting the module.

**How to apply:** When a task requires adding comments or docstrings to a leaf
module, check `wc -l` first. If it is within ~20 lines of 500, extract a
semantic concern into a sibling submodule (BTND-07-006) *before* writing the
documentation, rather than trimming prose to fit. Here the canonical-entry
validation concern moved to `sync/nodes/canonical_entry.py`, taking chain.py to
340 lines. Other leaf modules near the cap are worth a sweep — this will recur.

**Promoted**: 2026-07-31 — captured in `AGENTS.md` (leaf modules near 500-line cap pitfall).
Docs PR: <https://github.com/CERTCC/Vultron/pull/1900>0>0>0>0>.
