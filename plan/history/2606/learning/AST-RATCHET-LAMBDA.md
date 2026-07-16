---
source: AST-RATCHET-LAMBDA
timestamp: '2026-06-22T19:32:24.572826+00:00'
title: _walk_own_scope must guard ast.Lambda
type: learning
---

When implementing an AST-based scope walker to detect calls only in a
function's *own* scope (not nested scopes), guard `ast.Lambda` in addition
to `ast.FunctionDef` and `ast.AsyncFunctionDef`. A `lambda` body is a
separate execution scope — mutations inside it do not belong to the enclosing
`execute()`. Without the guard, `fn = lambda: self._dl.save(x)` inside
`execute()` produces a false positive. The fix is one line:
`isinstance(child, (ast.FunctionDef, ast.AsyncFunctionDef, ast.Lambda))`.
Add a synthetic test specifically for the lambda case to catch regressions.

**Promoted**: 2026-06-22 — archive only (too implementation-specific for
durable guidance).
Docs PR: <https://github.com/CERTCC/Vultron/pull/1112>.
