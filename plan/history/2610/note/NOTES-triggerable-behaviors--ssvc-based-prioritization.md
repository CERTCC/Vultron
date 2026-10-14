---
source: NOTES-triggerable-behaviors--ssvc-based-prioritization
timestamp: '2026-10-12T19:34:28.067053+00:00'
title: SSVC-Based Prioritization
type: note
---

**Archived:** 2026-10-12
**Reason:** untracked future design — no open issue plans SSVC evaluation; the prototype uses a stub policy and the evaluator seam already exists
**Superseded by:** PROTO-05-001; `vultron/core/behaviors/report/prioritize_tree.py` (EvaluateCasePriority call-out seam), `vultron/core/behaviors/report/policy.py`

---

## SSVC-Based Prioritization

The "evaluate priority" node in `rm_prioritization_bt.md` is a judgment
call that in a full implementation maps to SSVC
(Stakeholder-Specific Vulnerability Categorization) evaluation.

Proposed implementation path:

1. **Collect case data**: Gather known facts about the vulnerability
   (report content, case state, embargo status, participant roles).
2. **Evaluate decision points**: For each SSVC decision point (e.g.,
   Exploitation, Automatable, Impact), either:
   - Apply a rule-based evaluator if the answer can be derived from
     structured case data.
   - Prompt a human or LLM evaluator: present the case context and ask
     the evaluator to select the best answer from the allowed values, with
     reasoning. The prompt SHOULD instruct the evaluator to "select all
     answers that cannot be ruled out" to err on the side of caution.
3. **Apply decision table**: Feed the selected decision point values into
   an SSVC `DecisionTable` to produce a prioritization outcome.
4. **Map to RM state**: For the prototype, map the SSVC outcome to
   binary `engage` / `defer`. In a full implementation the a full SSVC
   outcome set (e.g., *Defer*, *Scheduled*, *Out-of-Cycle*, *Immediate*, or
   others; different SSVC models have different outcome sets) MAY be
   supported.

The `engage-case` / `defer-case` triggers directly correspond to this
engage/defer binary. The "accept" and "defer" placeholder nodes in
`rm_prioritization_bt.md` represent internal priority queue actions
(not the protocol messages). They should succeed unconditionally in
the prototype.

**See also**: `notes/bt-fuzzer-nodes.md` (SSVC-adjacent fuzzer nodes),
`specs/prototype-shortcuts.yaml` PROTO-05-001 (prioritization stub policy).
