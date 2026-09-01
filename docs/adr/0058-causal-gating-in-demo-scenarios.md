---
status: accepted
date: 2026-08-11
deciders: Vultron maintainers
consulted: CONCERN-2181, Epic #2136 bug triage history
informed: Vultron contributors, demo scenario authors
---

# Gate Demo Scenario Steps on Causal Preconditions, Not Temporal Order

## Context and Problem Statement

Vultron's multi-actor demo scenarios are written as temporal sequences: a phase
function calls step A, then step B, then step C. But the system underneath is
asynchronous — a trigger endpoint returns HTTP 202 and the protocol effect is
committed later by a `BackgroundTasks` job on a different container. Writing
"A and then B" when the truth is "B is only possible because A completed" makes
every step boundary a race.

This is not a theoretical concern. Of the nineteen sub-issues of Epic #2136
("Demo CI: restore green main"), seven were the same defect in a different
scenario: a step proceeded before the event that would enable it had propagated.
Two more were partially this. Each was fixed locally — a wait inserted here, a
different observable polled there — and the shared cause was never addressed, so
the next scenario rediscovered it. Bug #2178's own triage comment states the
diagnosis plainly: *"the demo treated async causal steps as sequential (x then y)
rather than causally linked (x therefore y)."*

Three symptoms show the problem is structural rather than a run of bad luck:

1. **The specs duplicated the workaround instead of stating the rule.** Seven
   scenario-specific requirements (DEMOMA-06-006, -11-009, -12-004, -19-005,
   -19-009, -21-003, -21-004) each say "poll here before proceeding" for one
   scenario. DEMOMA-11-009 states the general rule correctly but is scoped to
   FVCV-handoff alone.

2. **The gates did not gate.** Both `demo_step` and `demo_check` record the
   failure and continue — "no re-raise", by their own docstrings and by
   DEMOCI-01-003. So a precondition written with `demo_check` is advisory: it
   reads like a gate in review and does nothing at runtime, and the dependent step
   proceeds on state that was never established. The concrete instance is the
   `RM.VALID`-before-`engage-case` gate added by the #2134 fix on the
   `fix/demo-ci` branch, whose regression test passes only because it patches
   `demo_check` out with `contextlib.nullcontext`. That test idiom is not
   isolated: seven demo test modules on `main` patch these context managers out
   the same way, so no test in the suite exercises their real control flow.

3. **Which observable proves the cause landed was guesswork.** The gate before
   `validate-report` in `run_invite_path_rm_triage` was re-picked three times in
   one week: a ledger `submit_report` entry, then a `VultronOfferRecord` object,
   then a ledger `add_report_to_case` entry.

The question this ADR answers: what should the demo harness be required to
observe before advancing, and where should that requirement live?

## Decision Drivers

- The same defect class must not be able to recur in the next scenario written.
- The prototype's observability is limited: an actor having *processed* a
  delivery leaves no completion record, so not every precondition is directly
  observable.
- Demo CI must keep reporting every failure in a run (DEMOCI-01-003), so a fix
  cannot simply convert gates into hard aborts.
- Nine scenario modules totalling roughly 9,700 lines already exist; a solution
  requiring all of them to be rewritten in a new form is unlikely to be finished.
- ADR-0037 and ADR-0059 (buffer pre-genesis ledger entries) already moved one
  class of ordering problem into actor-side buffering. A harness rule must not
  contradict that.

## Considered Options

- **Causal gates in shared helpers, plus domain narratives as a conformance
  oracle** — state the rule once, express preconditions with a gating primitive
  that actually stops dependent work, and check the intended causal chain against
  the observed one.
- **Keep per-scenario polling with tuned timeouts** — the status quo: continue
  adding scenario-specific wait requirements and raising timeouts as CI reveals
  races.
- **Push all ordering into the actors** — extend the ADR-0037/0055 buffering
  approach until the harness never needs to sequence around delivery at all.
- **Declarative scenario dependency graph with static validation** — replace
  imperative phase functions with declared causal edges validated before a run.

## Decision Outcome

Chosen option: **causal gates in shared helpers, plus domain narratives as a
conformance oracle.**

The rule is stated once, at the conceptual layer that already governs demo
scripts (`EDF-06`), and generalized across scenarios in `DEMOMA-22`. Concretely:

- A step that depends on an asynchronous effect is gated on positive evidence
  that the effect was **committed by the actor that produces it**, read from
  **that actor's own container**. Elapsed time, step position, and an HTTP 202
  return are not evidence.
- Gating on an observable that resolves *synchronously* during the triggering
  request is prohibited — that observable proves the cause started, not that it
  finished. This is the #2134 defect.
- A causally derived object (one created by a received-side use case forwarding a
  new activity) is discovered by scanning the recipient's state for semantic
  properties — type, target, object — never by polling for the sender's original
  identifier. This is the #2178 defect.
- Preconditions are expressed with a new `demo_gate` context manager that
  accumulates the failure exactly as `demo_check` does but additionally stops the
  steps that depend on it. `demo_check` stays advisory. This resolves the tension
  with DEMOCI-01-003 by separating reporting from control flow rather than
  choosing between them.
- Waits that are irreducibly temporal — liveness probes, embargo deadlines,
  transport backoff — are identified as temporal and are not counted as causal
  gates.

Each scenario additionally gets a narrative page under `docs/topics/scenarios/`
describing the case's progress in CVD domain terms with each step's antecedent
named, carrying a machine-readable list of causal edges. The invariant harness
asserts every declared edge appears in the observed case ledger with the
antecedent's `log_index` preceding the consequent's. Because `log_index` order is
causal order (ADR-0079, CLP-14-001) and the harness already reads per-scenario ledger dumps,
this needs no new instrumentation.

The narrative is the part of this decision that does work the gates cannot. A
gate enforces that *the harness waited for the right thing*. The narrative
states, independently of the implementation, *what the protocol is supposed to
cause* — so it can disagree with the code. That is what makes it an oracle
rather than a restatement.

**Resolved: nested-block scoping model** (PR #2348). The `demo_gate` context
manager is implemented in `vultron/demo/utils.py` and validated by 14 unit
tests in `TestDemoGate`. The scoping question the ADR left open — "whether by
phase function, by nested block, or by an explicit sentinel" — is answered:
**nested block**. Python's native exception unwinding exits the `with` body on
failure; dependent steps follow the precondition assertion inside the same
block. No sentinel variable, no return value, no modified calling convention.

The causal-edge schema for scenario narratives (`docs/topics/scenarios/`) was
finalised in PR #2204. The schema and its update-together rule are documented
in `docs/topics/scenarios/index.md`, which is the authoritative source.

### Consequences

- Good, because the rule lives in one place, so a new scenario inherits it
  instead of rediscovering it.
- Good, because `demo_gate` makes a failed precondition stop the work that
  depends on it, which removes the cascade of secondary failures that buried the
  real cause in #2180 and #2195.
- Good, because the narrative check fails when the demo and the intended
  protocol disagree, which no existing invariant detects.
- Good, because it composes with ADR-0037/0055 rather than competing: where the
  actor buffers, the harness needs no gate, and some of the 26
  `wait_for_case_on_container` sites may now be removable.
- Bad, because migrating nine scenarios and roughly 20 gate call sites is
  substantial mechanical work, and the timeout constants are hand-tuned per site.
- Bad, because some preconditions are not observable today. "The receiver
  processed activity X" has no completion record, so those gates remain
  inferential — they observe a downstream effect and assume the antecedent
  caused it.
- Bad, because narratives are a new artifact class that can rot; DEMOMA-22-006
  requires updating them with the flow they describe, which is a review burden.

## Validation

- `spec-lint` enforces the requirement structure and ADR cross-references.
- The invariant harness enforces DEMOMA-22-005 per scenario: declared causal
  edges must appear in the observed ledger in causal order.
- A migration audit confirms every scenario's asynchronous boundaries use
  `demo_gate` and that no scenario module defines its own polling loop
  (DEMOMA-22-002).
- The `demo_gate` regression tests must exercise the real context manager. A test
  that patches it out with `nullcontext` does not validate gating behaviour —
  that is exactly how the current gap went unnoticed.

## Pros and Cons of the Options

### Keep per-scenario polling with tuned timeouts

- Good, because it requires no new mechanism and no migration.
- Good, because it is how the current scenarios already work, so it is proven to
  produce a green run when the timeouts are large enough.
- Bad, because it is the status quo that produced seven instances of the same
  bug, and it scales the defect with the number of scenarios.
- Bad, because timeouts encode load assumptions, so the suite gets slower and
  flakier as scenarios are added.
- Bad, because it leaves "which observable proves the cause landed" as a
  per-author judgement call.

### Push all ordering into the actors

- Good, because it fixes the production protocol, not just the demo — which the
  pre-genesis buffering decision on `fix/demo-ci` showed is sometimes the real
  defect.
- Good, because a harness that never needs to sequence is the simplest harness.
- Neutral, because it is already the chosen approach for the specific case of
  pre-genesis ledger entries.
- Bad, because it cannot cover the harness's own ordering obligations. A demo
  still has to know that an actor must reach `RM.VALID` before it can engage a
  case; buffering does not make that step unnecessary.
- Bad, because it treats every ordering assumption as a protocol defect, which
  over-generates protocol work for what are sometimes genuine harness errors.

### Declarative scenario dependency graph with static validation

- Good, because declared edges could be validated before a run rather than
  during it, catching an authoring error without spending CI time.
- Good, because it makes causality the primary structure of a scenario rather
  than a constraint layered onto it.
- Bad, because it is a large new mechanism replacing nine working scenario
  modules, for a prototype whose scenario set is still changing.
- Bad, because static validation cannot check the part that actually breaks —
  whether the running system honours the declared edge.
- Neutral, because the causal-edge list adopted here is a step toward it: if the
  edge declarations prove valuable, promoting them from documentation to the
  scenario's primary structure remains open.

## More Information

The narrative artifact came from a specific observation during planning: the
concern's own framing — "B does Y **because** A did X" — is a statement about the
CVD process, not about Python. Writing that statement down in domain terms gives
both the demo and the reader the same causal spine, and makes the places where
the demo has no reason for its ordering visible.

One claim in CONCERN-2181 is contradicted by the evidence and is recorded here so
it is not inherited. The concern states that "the underlying protocol state
machines and BT nodes ... are likely already correct. The gap is in the *demo
harness* ... not in the actor logic itself." Post-concern evidence shows the same
causal gap exists in the protocol layer: #2169's fan-out race is server-side and
a client-side demo wait cannot prevent it, #2186 was consequently fixed in the
protocol (the pre-genesis buffering ADR on `fix/demo-ci`), and #2194 — a
bare-string `Accept.object_` that trips the
AKM-03-001 outbox gate so the activity is never delivered — is squarely an actor
logic bug. The pattern this ADR addresses is real and well-attested, but it is
not exclusively a harness problem, and this decision does not green Epic #2136 on
its own: #2194 and #2195 are delivery and serialization defects that causal
gating would not have prevented.

Related decisions: ADR-0037 (buffer out-of-order ledger entries), ADR-0059
(buffer pre-genesis ledger entries — the production-side counterpart of this
decision), ADR-0041 (`log_index` order is causal order), ADR-0052 (demo CI job
structure).

Source concern: CONCERN-2181. Evidence: the Epic #2136 sub-issues ISSUE-2120,
ISSUE-2134, ISSUE-2135, ISSUE-2141, ISSUE-2169, ISSUE-2178, ISSUE-2180, and
ISSUE-2186.

Generated spec requirements: `event-driven-control-flow.yaml` EDF-06-001 through
EDF-06-007; `multi-actor-demo.yaml` DEMOMA-22-001 through DEMOMA-22-006;
`demo-ci.yaml` DEMOCI-01-007.
