---
title: DEMOCI-04 invariant-harness job needs Dependabot guard from DEMOCI-02-004
type: learning
timestamp: "2026-07-24"
source: ISSUE-1656
signal: spec-gap
---

DEMOCI-04-001 through 04-003 specify the structure of the new
`invariant-harness` job (separate job, `needs: demo`, `if: always()`), but
do not carry forward the Dependabot exclusion requirement from DEMOCI-02-004.

Without the guard, a Dependabot PR skips the `demo` job (correct) but then
runs the `invariant-harness` job, which immediately fails because
`actions/download-artifact` finds no `*-case-logs` artifact — producing six
spurious failing status checks on every Dependabot PR.

Fix applied in PR #1666:

```yaml
if: always() && !startsWith(github.head_ref, 'dependabot/')
```

**Spec update**: DEMOCI-04-005 added to `specs/demo-ci.yaml` (v1.3.0) in
PR #1666 to require the same Dependabot exclusion.
