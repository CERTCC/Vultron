---
title: "A pytest-timeout stack names the victim, not the culprit — and the spec registry was the cost"
type: learning
timestamp: "2026-08-12T00:00:00Z"
source: ISSUE-2239-timeout-stack
signal: tooling-issue
---

Validating the ISSUE-2239 branch, the full suite aborted at 82% with a
`+++ Timeout +++` stack dump, no `N passed / M failed` summary, and exit 1. Two
things about that were misleading enough to record:

1. **The reported test moves.** `timeout = 5` with `timeout_method = "thread"`
   in `pyproject.toml` kills the whole process; the stack is dumped wherever the
   alarm happened to fire, so the named test is whichever one was running, not
   necessarily the expensive one. Across runs it landed in
   `test_docs_render.py`, `test_decision_audit_inventory.py`, and
   `test_pcr_late_joiner.py` (#2270). Diagnosing from the test name leads
   nowhere; timing the shared call in the stack does.

2. **A 5-run A/B beats one run.** With `specs/` stashed the flaky test passed
   0/5 failures; with the branch's two spec-file additions it failed 2/5. That
   looks causal and is not — the same test was already 3.5–4.3 s against a 5 s
   ceiling on clean `main`. Eight new spec entries out of 2355 (0.3%) only moved
   it across a line it was already sitting on.

Where the cost actually was, measured per stage:

| Stage | Time |
|---|---|
| `yaml.safe_load` of all `specs/*.yaml` (1.18 MB) | 2.73 s |
| `SpecFile.model_validate` for every file | 0.024 s |
| `load_registry()` total, uncached, per call | 3.44 s |

`pyyaml` silently falls back to the pure-Python `SafeLoader`; this environment
ships `libyaml`. Selecting `yaml.CSafeLoader` when present (identical
SafeLoader semantics) took `load_registry()` from 3.44 s to 0.35 s and the flaky
test from 2/5 to 0/5. Two lines, in
`vultron/metadata/specs/registry.py`.

Two durable takeaways: **when a validation step is 100× cheaper than the parse
step in front of it, check which loader the parser picked** — the 10× is free
and applies to every `yaml.safe_load` of a large file in this repo. And the
underlying fragility is untouched: any test doing real work is one slow
container away from aborting the session while `timeout_method = "thread"` is
global, which is #2270's actual fix (parented to #2089).

**Promoted**: 2026-08-17 — captured in docs/reference/codebase/TESTING.md (pytest-timeout cluster — prior session update).
Docs PR: <https://github.com/CERTCC/Vultron/pull/2330>0>0>0>0>0>0>0>0>0>.
