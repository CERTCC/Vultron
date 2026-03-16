## Implementation Notes

Longer-term notes can be found in `/notes/*.md`. This file is ephemeral
and will be reset periodically, so it's meant to capture more immediate
insights, issues, and learnings during the implementation process.

Add new items below this line

---

### 2026-03-16 — Refresh #34 findings

**P75-2c and P75-3 complete**: All handler use cases and trigger-service use
cases now live in `core/use_cases/`. The handler adapter layer is reduced to a
no-op `_shim.py`. The dispatcher is a formal driving port. Pattern objects use
`Pattern` suffix. Test count: 887 passed.

**TECHDEBT-13 and TECHDEBT-14 complete**: V-24 resolved; `vultron_types.py`
split into per-type modules. All violations V-01 through V-24 resolved.

**TECHDEBT-15 (new)**: `test_remove_embargo` remains flaky due to py_trees
blackboard global state. Spec TB-06-006 requires deterministic tests. Fix:
`autouse` fixture clearing `py_trees.blackboard.Blackboard.storage` in
`test/wire/as2/vocab/conftest.py`.

**UseCase interface standardization needed before P75-4**: Per
`notes/use-case-behavior-trees.md`, define `UseCase[Req, Res]` Protocol with
`execute()` method (P75-4-pre) before wiring up CLI/MCP adapters (P75-4).

**ActivityEmitter port gap**: `core/ports/emitter.py` does not exist yet.
Per `notes/architecture-ports-and-adapters.md`, this is the outbound driven
port ("Emit") counterpart to the inbound driving port `core/ports/dispatcher.py`
("Dispatch"). Added as OX-1.0 preceding the OUTBOX-1 tasks.

**Docs gaps confirmed**: `docker/README.md` lists obsolete individual demo
services (DOCS-1). `docs/reference/code/as_vocab/` references old
`vultron.as_vocab.*` paths (DOCS-2). Both captured as actionable tasks.

---

### 2026-03-16 — P75-4-pre complete

**UseCase Protocol now defined**: `UseCase[Req, Res]` lives in
`vultron/core/ports/use_case.py`. `UnknownUseCase` is the reference
implementation; the old function wrapper delegates to it.

**CRITICAL constraint for P75-4**: P75-4 MUST refactor every use case it
touches to the class interface (`__init__(self, dl: DataLayer)` +
`execute(self, request) -> result`). Do NOT leave behind a mix of old-style
`fn(event, dl)` callables alongside new class-based use cases within a single
migration batch. The old-style callable wrapper on `unknown` is a temporary
bridge; it must be removed once the dispatcher supports class-based use cases.

If necessary, expand `Req` and `Res` type variables to be a consistent 
Pydantic model envelope (e.g., `UseCaseRequest` and `UseCaseResponse`) to  
accommodate the fact that some use cases may require multiple input 
parameters or multiple output values. This will future-proof the interface  
and ensure it can handle more complex use cases without needing another 
refactor. 
