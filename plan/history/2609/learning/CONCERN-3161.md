---
source: CONCERN-3161
timestamp: '2026-09-22T14:15:32.897294+00:00'
title: BTBridge.execute_with_setup restores only managed_keys; /activity and context_data
  keys can leak across nested executions
type: learning
---

`BTBridge.execute_with_setup` restores only its `managed_keys` (`datalayer`, `trigger_activity_factory`, `sync_port`, `wire_render_port`, and `ledger_payload_object_override`) to their pre-execution state in its `finally` block. Other keys that `setup_tree` writes — the `/activity` key (when `activity is not None`) and any `**context_data` keys (e.g. `/case_id`, `/log_entry`) — are not snapshotted or restored. Because `_BT_GLOBAL_LOCK` is a reentrant `RLock`, nested `execute_with_setup` calls are a real, supported pattern. If a nested call ever passes `activity=` or a `**context_data` key that collides with a key the outer execution is still relying on, the inner `setup_tree` overwrites the outer value and the inner `finally` does not restore it. Currently latent — no existing nested call site passes `activity=` or `**context_data`.

**Resolved**: 2026-09-22 — implementation tracked in #3510 (extend managed_keys with `["activity"] + list(context_data.keys())` before previous_values is snapshotted; actor_id intentionally excluded).
Docs PR: <https://github.com/CERTCC/Vultron/pull/3509>.
Notes: `notes/bt-pitfalls.md` § "Execution-Scoped Hand-off Keys Are Reset by the Bridge, Not by a Node".
