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
