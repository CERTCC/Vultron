---
source: BASE-HOOK-1005
timestamp: '2026-06-22T19:35:48.187729+00:00'
title: Base BT hook methods must document their no-op default
type: learning
---

`BTBridge` provides optional `setup_blackboard_hook()` and
`teardown_blackboard_hook()` extension points. If a subclass overrides only
one of them, the remaining default is a silent no-op. Document this in the
base class docstring so implementors know a missing override is intentional.
Without the docstring, code reviewers flag the absent override as a potential
bug. Add `# no-op by design` comments in any subclass that intentionally
does not override one side.

**Promoted**: 2026-06-22 — archive only.
Docs PR: <https://github.com/CERTCC/Vultron/pull/1112>.
