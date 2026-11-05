---
title: "No requirement says a demo step must not be handed a placeholder, so the ratchet that now enforces it rests on a derivation"
type: learning
timestamp: "2026-11-05T00:05:00Z"
source: ISSUE-3887
signal: spec-gap
---

Task #3887 added a second check to
`test/architecture/test_demo_step_no_unbound_ratchet.py` that fails a demo
module when a name pre-initialised to `None` or `""` is assigned inside a
`demo_step`/`demo_check`/`demo_gate` body and then read after it with no guard.
The check carries `@pytest.mark.spec("EDF-06-005")`. Its triage found 34 live
instances under `vultron/demo/exchange/`.

The two requirements it cites do not state the rule it enforces:

- **EDF-06-005**: "An unmet causal gate MUST prevent execution of the steps that
  depend on it. Recording the failure and continuing to the dependent step is
  not sufficient."
- **DEMOCI-01-009**: "On failure, `demo_gate` MUST prevent execution of the
  steps that depend on the unmet precondition."

Both govern **control flow** — whether the dependent step runs. Neither says
anything about the **value** a dependent step receives when it does run. The
placeholder shape satisfies both as written: the gate records its failure, the
block exits, and the dependent step is a separate `with` that the gate never
claimed to stop. That is exactly why PR #3886 could add `demo_gate` to
`_GUARDED_CMS` and flag zero sites, and why #3887's summary calls the result
"the blind spot, not a clean bill".

So the rule the ratchet now enforces — *a step must not be handed a placeholder
standing in for a value an earlier step failed to produce* — is derived from
EDF-06-005's rationale ("a cascade of secondary failures that masks the first
one") rather than from any requirement statement. Three recurrences argue the
derivation is right: #2390, the review finding on #2726, and #3038. But a
ratchet whose subject is a value rather than a control path, citing two
requirements that are both about the control path, is a claim no reader can
check against the corpus.

Two further facts bear on where the gap should be closed:

- EDF-06-005 and DEMOCI-01-009 both carry `verification_debt` markers (#2575,
  #2573) for a whole-file backfill. #3887 deliberately did not flip either to
  `verification:`, because a static ratchet shows no step is *handed* a
  placeholder, which is narrower than either requirement's claim about
  execution. If the gap is closed by a new requirement, that requirement is the
  one the ratchet should cite and verify, and the two debt markers stay with
  their owners.
- The pre-push review of #3887 found the first version of the check could not
  see `post_to_trigger(..., body={"invite_id": invite_id})` — #3038's own line —
  because it looked only for a bare name as an argument. A requirement that
  named the shape in terms of *what reaches the next step* rather than *how the
  name is spelled at the call* would have made that narrowness visible as a
  conformance question instead of a reviewer's probe.

Open question for `/learn`: is this one new EDF-06 requirement ("a step that
depends on a value an earlier block produced MUST NOT run with a placeholder
standing in for it"), or a clarification to EDF-06-005 extending "prevent
execution" to cover being handed an unproduced value? The nesting-versus-guard
remedy is already written in `notes/demo-scenario-authoring.md` and
`vultron/demo/AGENTS.md` rule 9; what is missing is the normative statement
those two pieces of guidance implement.
