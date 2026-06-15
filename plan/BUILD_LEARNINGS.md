## Implementation Notes

Longer-term notes can be found in `/notes/*.md`. This file is ephemeral
and will be reset periodically, so it's meant to capture more immediate
insights, issues, and learnings during the implementation process.

Append new items below any existing ones, marking them with the date and a
header.

### 2026-06-11 OUTBOX-873-TEST-COVERAGE — make acceptance criteria explicit in one file

Issue #873 found that most delivery-path coverage already existed but was split
across sections/files. Adding explicit tests in
`test/adapters/driving/fastapi/test_outbox.py` for direct `to` extraction and
malformed bare-string `object_` integrity checks keeps OX-08/OX-09 validation
discoverable in the canonical outbox test module and reduces ambiguity during
future outbox refactors.

### 2026-06-11 NODES-SPLIT — VulnerabilityCase.case_statuses has a default initial CaseStatus

`VulnerabilityCase.case_statuses` is auto-populated with one `CaseStatus`
(em_state=EM.NONE, UUID id) when the object is created. Tests that check
`len(case.case_statuses) == 1` after a single append will fail with `2`.
Use `initial_count + 1` pattern or check only SUCCESS status.

### 2026-06-11 OUTBOX-874-HELPER-EXTRACTION — split protocol invariants from flow wiring

The outbox handler became easier to reason about after extracting nested
protocol checks into explicit helper functions (`_coerce_reference_value`,
`_prepare_activity_object_for_delivery`, `_recover_typed_inline_object_from_dict`,
etc.). Keeping the main delivery function focused on sequence-level orchestration
reduces churn risk when adding future outbox requirements while preserving
existing OX/MV invariants.

### 2026-06-11 SYNC — Isolated two-app replication harness for CaseLogEntry

For SYNC happy-path replication integration coverage (#901), the most stable
test seam is two isolated FastAPI apps created with `create_isolated_actor_app`
plus a shared `_TestASGIRouter` wired as each app's emitter fallback and as the
module-level default emitter. This setup exercises outbox -> ASGI delivery ->
inbox processing with distinct actor-scoped DataLayers and avoids real HTTP
retry delays.

### 2026-06-11 SYNC-902-MISMATCH-TEST-SEAM — mismatch assertions need dispatch-level injection

For predecessor-mismatch coverage (#902), injecting `Announce(CaseLogEntry)`
through `post_actor_inbox` can mask mismatch behavior because nested object
persistence can make `CheckLogEntryAlreadyStored` short-circuit before hash
validation. A stable test seam is `handle_inbox_item(...)` with a typed
activity object, then normal outbox-driven replay from the CaseActor.

### 2026-06-11 NODES-SPLIT-883 — mirror flat-to-subpackage splits in tests

When converting a behavior area from `nodes.py` to `nodes/`, preserve
`from ...nodes import ...` import paths with an explicit `nodes/__init__.py`
re-export list, and move node-level tests into `test/.../nodes/` with
per-submodule files. Keep tree composition tests in the parent workflow test
module so node behavior and tree wiring remain independently reviewable.

### 2026-06-12 CASE-LOG-925-RATCHET — guard hash-chain fields before comparing

When implementing the local hash-chain invariant for JSONL case-log replicas,
assert that `entryHash` and `prevLogHash` fields are non-empty before
comparing them. Missing fields produce `"" == ""` false positives that mask
serializer or schema-migration bugs. Add an explicit presence assertion
before every chain comparison.

### 2026-06-11 OX-10-004-STUB-GUARD — keep stub adapters under explicit test

`ProdHttpDeliveryAdapter` is intentionally unimplemented and must fail fast
with a spec-linked `NotImplementedError`. A dedicated adapter-level unit test
prevents future placeholder edits from silently downgrading the fail-fast
signal into a no-op module.

### 2026-06-15 SYNC-789 — BTBridge must carry sync_port when BTs commit ledger entries

When a use-case's BT contains \`CommitCaseLedgerEntryNode\`, the \`BTBridge\`
that runs that BT **must** be constructed with \`sync_port=\` set.
\`CommitCaseLedgerEntryNode\` reads \`sync_port\` from the py_trees blackboard
and silently skips the \`Announce(CaseLedgerEntry)\` fan-out (SYNC-2) with
\`Status.SUCCESS\` when the key is absent — no error, no warning loud enough to
catch in unit tests.

**Pattern to follow**: Any semantic whose use case runs a BT containing
\`CommitCaseLedgerEntryNode\` must be placed in
\`_SYNC_AND_TRIGGER_PORT_SEMANTICS\` (if it also needs \`trigger_activity\`) or
\`_SYNC_PORT_SEMANTICS\` (if it only needs sync). The use-case \`**init**\`
must also accept \`sync_port\` and pass it to \`BTBridge(sync_port=sync_port)\`.

**How to diagnose**: Look for
\`"sync_port not injected; skipping fan-out for '...'"`(DEBUG level) in
container logs, or for replicas with zero \`CaseLedgerEntry\` records when
the authority has committed entries. This is never a timeout/race — the
fan-out simply does not run.

**Affected semantics fixed**: \`SUBMIT_REPORT\`, \`ENGAGE_CASE\`, \`DEFER_CASE\`
(all moved to \`_SYNC_AND_TRIGGER_PORT_SEMANTICS\` in PR #944).

### 2026-06-12 RENAME-934 — pytest mark registration must mirror class/file renames

When renaming a pytest mark (e.g., `case_log_invariants` → `case_ledger_invariants`),
update **both** `pyproject.toml` markers AND any `.github/workflows/` YAML files that
reference the mark by name. A renamed mark in test files without a corresponding
workflow update causes `pytest` to select 0 tests and exit with code 5 (no tests
collected), failing CI even though the rename itself is correct.

### 2026-06-12 USE-CASE-SPLIT-881 — flat-to-subpackage test migration pattern

When migrating flat test files into per-submodule subdirectories, the existing
test classes map cleanly onto the semantic clusters already established by the
source split. Removing the old flat files and creating new per-submodule files
(rather than leaving both) avoids duplicate test collection and keeps the
layout strictly mirrored. The parent `conftest.py` fixtures are automatically
inherited via pytest's upward conftest search, so only the vocabulary
registration side-effect import needs copying into each new subdirectory
conftest.

### 2026-06-15 RM-TERMINAL-GUARD-928 — treat CLOSED as terminal before same-state check

`ValidateRMTransitionNode` must evaluate terminal-state rules before its
`current == new` short-circuit. If equality is checked first, repeated
`CLOSED -> CLOSED` updates are treated as successful no-ops at validation time
but still flow through append/broadcast/log-cascade paths as new status IDs.
Guarding terminal `RM.CLOSED` first prevents duplicate closure cascades and
keeps `close_case` retries from creating new canonical ledger entries.
