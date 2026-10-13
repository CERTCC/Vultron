---
source: NOTES-behavioral-conformance-specs--intent-over-letter
timestamp: '2026-10-12T23:47:28.557662+00:00'
title: 'Behavioral conformance specs: intent over letter (superseded by agentic-workflow)'
type: note
---

Archived from `notes/behavioral-conformance-specs.md` by #4497 (notes sweep): the
spec-versus-issue conflict rule is superseded by `notes/agentic-workflow.md`
§ "Spec Text Conflicts With Code" (the material test, and `## Spec amended` in the
PR body). The closing BT gate-placement remark is not a spec-authoring rule; its
lesson belongs with the behavior-tree pitfalls (`notes/bt-pitfalls.md`).

---

## Intent Over Letter: When Spec Text and Issue Body Conflict

(ISSUE-1272, 2026-07-10)

When a spec entry and its associated GitHub issue body conflict with each
other, or when either conflicts with established architectural principles,
implement the **observable intent** — what the system must *do from the
outside* — then **correct the spec entry** in the same PR rather than
silently complying with a stale requirement.

Specifically:

- If the spec mechanism (e.g. "MUST NOT invoke `create_receive_report_case_tree`")
  contradicts the architectural pattern (BT-first, thin use-cases), reword
  the spec to describe the outcome, not the mechanism.
- If the issue body contains a factual error about the codebase (e.g., "the
  BT already has access to ActorConfig through the blackboard" when it actually
  threads via constructor arg), note the correction in a PR comment and implement
  the correct path.
- Use `AskUserQuestion` to surface genuine design forks — divergences where
  both interpretations are architecturally valid.

Neither specs nor issue text constrain the *right* solution; they steer
away from bad ones. The spec is authoritative once corrected; the issue
text is ephemeral.

Also: **BT gate placement matters.** The idempotency idiom
`Selector(Sequence(guard, work), Success)` **masks** downstream FAILURE.
When a downstream FAILURE must still propagate (e.g., case creation can
genuinely fail), use `Sequence[gate, existing_Selector]` instead so the
gate fails-safe without swallowing real failures.

---
