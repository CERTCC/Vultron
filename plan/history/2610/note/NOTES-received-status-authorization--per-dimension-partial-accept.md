---
source: NOTES-received-status-authorization--per-dimension-partial-accept
timestamp: '2026-10-20T20:17:13.521743+00:00'
title: 'Archived notes section: per-dimension partial accept (RSH-05)'
type: note
---

Superseded by whole accept or reject of a received status (RSH-09, ADR-0107 detail 5, #3741). Per-dimension partial accept, its carry-forward and the ledger override patch were removed; the rules that still hold are in `notes/received-status-authorization.md` § "Whole accept or reject (RSH-09, ADR-0107)".

---

## Per-dimension partial accept (RSH-05, ADR-0061)

`FilterParticipantStatusDimensionsNode` adjudicates `rm`, `vfd` and `pxa`
independently and publishes a *filtered* `ParticipantStatus` in which each
refused dimension carries the participant's current value forward. Refusing the
whole snapshot for one bad dimension would discard the accepted ones and skip
teardown. `FilterCsEmDimensionNode` → `FilterCsPxaDimensionNode` →
`FinalizeCsFilterNode` do the same for `CaseStatus`. Rules:

- **The filters are guards.** They are read-only (CLP-10-006), run before
  `GuardedCommitOrSkip`, and `FinalizeCsFilterNode` belongs in
  `precondition_guards`, never among the effects (CLP-10-009). A wholly refused
  regression therefore ends the tree before its effects; the RM gap note runs as
  a `refusal_effects` instead (CLP-10-022).
- **`em` is never adjudicated from a status.** EM is derived from the embargo
  register, so an asserted EM that differs from `case.em_state` is refused
  (RSH-09-005, ADR-0122).
- **Write the handoff keys on every tick and match them by object ID.** The
  py_trees blackboard is process-global and `BTBridge` restores only a few keys
  between runs, so a producer writes `None` before any early return
  (RSH-05-010, BT-17-003).
- **The ledger override is a field patch, not a replacement object**
  (RSH-05-009). `ledger_payload_object_override` names only the adjudicated
  fields, keyed by wire alias, and `CommitCaseLedgerEntryNode` merges them onto
  the sender's wire-shaped snapshot. Core cannot rebuild that wire shape
  (ADR-0009), so patching makes shape preservation structural. Producers declare
  `producer_type` and use only recognized aliases; the consumer hard-fails on an
  unknown alias and warns on an unknown producer (RSH-05-011 to RSH-05-014).
  Register a new producer in `_RECOGNIZED_OVERRIDE_PRODUCERS`.
- **One port name cannot be both input and output** of a py_trees node; the CS
  accumulator is written back through a second alias mapped to the same key.
- **`ValidateRMTransitionNode` stays all-or-nothing** when the append subtree
  runs standalone; it relaxes only when the blackboard says `rm` was refused
  upstream.
- **An omitted `caseStatus` is not a refusal.** The receiver's own values are
  carried forward; persisting the assertion verbatim would blank them. If
  carrying forward is the *only* change, nothing was learned and the status is
  refused in full (RSH-05-005).
- **A blocked dimension is not always a rewritten one.** `RM.CLOSED` restated at
  `RM.CLOSED` is blocked but discards nothing; the WARNING distinguishes
  `rewrote dimension(s)` from `blocked dimension(s) … with no change`.

### Cross-machine entailments (RSH-09-004)

Individually valid dimensions can still describe an impossible state (a ready
fix before the report was accepted; a deployed fix before a ready one). A final
pass evaluates RM↔VF, RM↔D (CSB-18-001) and VF↔D (CSB-17-001):

- **Refuse the dimension that moved.** Refusing the incumbent side carries the
  impossible value straight back. A dimension the sender omitted is never
  reported as refused.
- **Evaluate the effective state, not the assertion**, so a refused `vf` cannot
  license the `d` paired with it. This is not a defence for `rm`: a refused `rm`
  carries a value at or above the asserted one, so it can only accept more.
- **Emit, receive and replica-apply share one evaluator**,
  `composite_state_violations()` in
  `vultron/core/states/composite_state_invariants.py`. No path calls an
  individual `violation_*` function; the emit path reaches it through
  `participant_transition_violations()` (ADR-0086).
- **Re-evaluate after each refusal.** A refusal can retire a violation listed
  beside it (refusing `d` for RM↔D also clears VF↔D).
- **It is not a ladder check.** Non-adjacent forward advances stay legal
  (CSB-16-001), and an absent dimension is absent, not initial (ADR-0075).
- **RM↔VF and RM↔D are sound, not complete.** The real rule is a history
  property (the actor passed `RM.ACCEPTED`); `RM_STATES_CONSISTENT_WITH_FIX`
  approximates it with the states reachable from `ACCEPTED`, so `DEFERRED` and
  `CLOSED` stay in. Narrowing it would refuse a peer that accepts and reports a
  ready fix in one message. Tightening it needs RM history.
- **The guarantee is conditional.** If the incumbent state is already
  impossible, no per-dimension refusal can repair it; the pass logs and leaves
  it. Read that log line as evidence of a write that bypassed the pass.
