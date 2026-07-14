---
title: Domain sweep audit verification pattern for call-out point completeness
type: learning
timestamp: 2026-07-14
source: ISSUE-1177
---

For FUZZ-08h-style completeness audits, the effective verification sequence is:

1. Grep all demo/fuzzer Python classes via AST parse to get a flat inventory
   of implemented nodes.
2. Cross-reference against catalog `New-arch cross-ref:` lines — any entry
   with `*(to be implemented)*` or a closed-issue reference is a gap.
3. Grep `CallOutBackendFactory` in all tree builder files to verify factory
   injection is present in every domain tree.
4. Grep `register_key` across demo/fuzzer nodes to surface all blackboard keys,
   then scan for naming conflicts (same key name, different semantic meaning
   in the same domain).
5. Run `pytest test/core/behaviors/report/ test/core/behaviors/embargo/
   test/demo/fuzzer/ test/fuzzer/` as the domain-scoped fast gate.

The audit is cheap once linters and tests are green — the catalog is the ground
truth; the code is what needs to match it.
