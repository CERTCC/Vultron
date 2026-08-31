---
status: accepted
date: 2026-08-12
deciders: Allen D. Householder
consulted: []
informed: []
---

# Re-express the Legacy Case-State Invariants and Keep the Hypercube as Reference

## Context and Problem Statement

`vultron/core/case_states/` is the original implementation of the MPCVD
state-based model (CMU/SEI-2021-SR-021). It encodes the case-state (CS) rules as
**six-character strings and regular expressions** — `"vfdpxa"`, `"v..P.."` —
validated by `validations.py` and analysed by `hypercube.py` (a networkx /
numpy / pandas model that enumerates states, transitions, histories, and scores
them). The protocol implementation has since moved to typed enums (`CS`,
`CS_vfd`, `CS_pxa`), `pytransitions` machines, and per-machine dimension objects
(ADR-0036). The two worlds do not talk to each other.

The legacy module holds rules the current models do not enforce anywhere. The
most consequential is `is_valid_history`, which makes validity a **causal**
property of an entire event sequence rather than a point-in-time state check or
a wall-clock timestamp comparison — exactly what CONCERN #2181 asked for.
`VFDPXA` and `VFDXAP` visit only valid states, yet only the first is a case
history any real case could have produced; nothing in the current code can tell
them apart.

Two questions had to be settled together (issue #2237, which blocks #2236):

1. Which legacy rules are still valid, which have been superseded, and which are
   wrong — and how should the survivors be expressed against the current models?
2. What is the legacy module's status: keep, retire, or archive?

Answering (2) required first checking the issue's stated premise that the module
is "completely orphaned". **It is not.** There are exactly two live importers
outside its own tree:

- `vultron/core/use_cases/query/action_rules.py` imports
  `vultron.core.case_states.patterns.potential_actions.action`, reached from the
  live `actors_get_action_rules` FastAPI endpoint.
- `vultron/core/states/cs.py` imports `ensure_valid_state` from
  `validations.py` and decorates four string helpers with it.

The second is the load-bearing one: the *current* CS enum module depends on the
*legacy* validator, so "retire the legacy module" is not a delete — it is a
migration.

## Decision Drivers

- The rules, not the code, are the asset. The issue's own framing: treat
  `case_states/` as the **specification of record**, and prefer a deliberate
  line-by-line rewrite over `import and use`.
- Re-expression must be provably faithful. A rewrite that silently admits a
  different rule set is worse than no rewrite, because it looks authoritative.
- Real case histories are usually **incomplete**; a rule family that only
  validates all six events is not usable on live cases.
- Cross-machine rules (RM/EM × CS emit guards) belong to #2236, not here.
- `hypercube.py` pulls in networkx, numpy and pandas. Nothing on the protocol
  path should acquire that dependency weight.
- The 500-line module guideline (CS-18-001): `cs.py` is already over the
  guideline, so new code goes in a sibling module. `cs_invariants.py` itself
  lands over it too; it is kept whole deliberately, because the rule family is a
  single closed set of invariants whose only natural split — predicates apart
  from the tables they read — would put a rule and its enforcement in different
  files. Splitting is revisited if a second rule family lands here.

## Considered Options

- **A. Import and delegate** — have the current models call
  `validations.is_valid_transition` / `is_valid_history`, converting enums to
  strings at the boundary.
- **B. Re-express the surviving rules against the current enums; keep the legacy
  module as the analytical model and as the test oracle.**
- **C. Re-express and retire** — rewrite, then delete `validations.py` and
  `hypercube.py` in this change.
- **D. Archive the whole tree** — move `case_states/` out of `vultron/` to
  `docs/` or a research repo, and rebuild any needed rule from the SEI report.

## Decision Outcome

Chosen option: **B — re-express the surviving rules in current idiom; keep the
legacy module, demoted to reference model and test oracle.**

### The rule inventory

Every rule in `validations.py` and the graph construction in `hypercube.py` was
assessed. No rule was found to be **wrong**; the verdicts split between *still
valid* and *superseded by structure*.

| Legacy rule | Verdict | Where it now lives |
|---|---|---|
| `is_valid_state`: `vF` and `fD` are impossible → 32 valid states | Still valid, but **structural** | `CS_vfd` has only 4 members, so the impossible combinations are unrepresentable. Expressed as a ratchet test, not a runtime predicate. CSB-17-001 |
| `is_valid_transition`: Hamming distance 1 | Still valid, unenforced | `cs_transition_event()`, CSB-17-002 |
| `is_valid_transition`: monotone (no UC→lc), same dimension | Still valid, partly enforced per-dimension | Delegated to `is_valid_vfd_transition` / `is_valid_pxa_transition`; compound-level check in `is_valid_cs_transition()`, CSB-17-002 |
| `TRANSITION_RULES[1]`: `...pX. → ...PX.` | Still valid | `required_next_cs_events()`. Partly covered by CSB-13-001 (entry cascade); CSB-17-003 generalises it to every successor of a `pX` state |
| `TRANSITION_RULES[0]`: `v..P.. → V..P..` | Still valid, asserted by SM-09-001 as a persistence-time normalization but with no CS-behavior rule of its own | `required_next_cs_events()`, CSB-17-003, which `refines` SM-09-001 by restating it as a trajectory rule |
| `is_valid_history`: causal event ordering (`V≺F≺D`, `P≺X`/`XP`, `V≺P`/`PV`) | Still valid — **the most valuable rule in the module** | `is_valid_cs_history()` / `is_valid_cs_history_prefix()` / `replay_cs_history()`, CSB-17-004 |
| `is_valid_pattern` and the whole `.`-wildcard regex pattern language | **Superseded** | Enum membership tuples (`VFD_VENDOR_AWARE`, `PXA_EXPLOIT_PUBLIC`, …) and the `is_*` predicates already do this, type-safely |
| `hypercube.py` scoring, tf-idf, pagerank, `DESIDERATA`, adjacency matrices | Out of scope — analytical, not normative | Stays in `hypercube.py`; no protocol path needs it |

The survivors are implemented in `vultron/core/states/cs_invariants.py` as
CSB-17, raising the current-idiom errors (`VultronInvalidStateTransitionError`,
`VultronValidationError`) rather than the legacy `CvdStateModelError` tree.

### Two re-expression choices worth recording

**Transitions delegate to the dimension machines instead of re-deriving
monotonicity.** `is_valid_cs_transition` identifies the single changed dimension
and hands the check to `is_valid_vfd_transition` / `is_valid_pxa_transition` —
the same tables `VfdDimension` / `PxaDimension` use. Monotonicity and the VFD
prerequisite chain then come for free and, more importantly, **cannot drift**
from what the dimension objects enforce. Only the two ephemeral rules are
genuinely new logic at the compound level.

**History validity is expressed as causal replay, not as ordering predicates.**
The legacy formulation compares permutation indices; the re-expression replays
the sequence through the transition rule from `CS.vfdpxa`. The two are provably
equivalent — for a permutation of `VFDPXA`, replay succeeds iff `V≺F`, `F≺D`,
`index(P)−index(X) ≤ 1`, and `index(V)−index(P) ≤ 1`, and the two ephemeral
rules can never be active simultaneously (one needs `P` set, the other needs it
unset). Replay was chosen because it **generalises to prefixes**: real cases are
in progress, and `is_valid_cs_history_prefix` validates what has happened so far
without demanding all six events. The index-comparison formulation cannot do
that. The equivalence is asserted directly in the tests, so the two formulations
cannot silently diverge.

### The legacy module's status: keep, demoted

`validations.py` and `hypercube.py` are **retained**, with a changed role:

- **Not** on the protocol path. `cs_invariants.py` is the runtime source of
  truth for CS validity. New code MUST NOT import `case_states.validations`.
- **Reference model.** `hypercube.py` remains the derivation of the 32/58/70
  figures and the home of the analytical tooling (scoring, desiderata, pagerank)
  that has no protocol counterpart and no reason to acquire one.
- **Test oracle.** `test/core/states/test_cs_invariants.py` compares the new
  implementation against the legacy string implementation over the whole space —
  64 candidate states, 32×32 candidate transitions, all 720 permutations. This
  is the strongest available evidence that the rewrite is faithful, and it only
  works while both implementations exist.

Retirement is therefore **deliberately deferred, not forgotten**, and is gated on
two migrations that are out of scope here:

1. `vultron/core/states/cs.py` must stop importing `ensure_valid_state`. Its four
   decorated string helpers (`vfd`, `pxa`, `state_string_to_enums`,
   `state_string_to_enum2`) need an enum-native validator.
2. `vultron/core/use_cases/query/action_rules.py` must stop importing
   `case_states.patterns.potential_actions` — which raises the separate question
   of whether the `actors_get_action_rules` endpoint should be served from the
   pattern language at all.

Option A was rejected because it would make the enum models depend on
string-and-regex validation permanently, and would let the legacy error tree leak
into protocol paths — the opposite of the issue's explicit instruction to prefer
rewriting. Option C was rejected because deleting the legacy module in the same
change that rewrites it destroys the only independent oracle proving the rewrite
correct, and because two live importers make it a migration rather than a
deletion. Option D was rejected for the same reason plus the loss of the
analytical model, which is genuinely useful and genuinely non-normative.

### Consequences

- Good: the `vP → VP` rule is now enforceable against the current enums for the
  first time. SM-09-001 already required it, but only at the persistence
  boundary and only with the legacy string-pattern module as its implementation;
  CSB-17-003 gives it a CS-behavior expression, and CSB-17-005 settles what it
  means for an in-progress history (a prefix may end in `vP`; a persisted state
  may not be `vP`).
- Good: history validity is available as a causal check on complete *and*
  partial histories, which is what CONCERN #2181 needs.
- Good: compound-transition validity cannot drift from the dimension objects,
  because it delegates to their tables rather than re-deriving them.
- Good: the equivalence tests fail loudly if either implementation changes,
  making the legacy module useful precisely as long as it is still present.
- Neutral: two implementations of the same rules coexist. Acceptable because one
  is explicitly non-normative and the tests pin them together.
- Good: `cs_invariants.py` is now wired into the BT write paths. Completed in
  #2479: `CreateParticipantStatusNode` enforces AC-3 compound-transition
  validation (`is_valid_cs_transition`) and AC-1 ephemeral-state promotion
  (`pXa→PXa`, `pXA→PXA`, `vP→VP`); `AppendCaseStatusToCaseNode` and
  `EmitCaseStatusUpdateNode` enforce AC-1 promotion for `CaseStatus` writes.
- Bad: the retirement of `case_states/` is now a recorded intention with two
  named prerequisites rather than a completed act, so it can still rot if those
  prerequisites are not tracked.

## Validation

- `test/core/states/test_cs_invariants.py` — exhaustive equivalence
  against the legacy implementation: the `CS` enum equals the legacy 32-state
  set; the new transition rule admits exactly the legacy 58 edges; the causal
  replay admits exactly the legacy 70 histories; and `is_valid_cs_history`
  agrees with the legacy result on all 720 permutations.
- Ephemeral-state coverage: the 12 `vP`/`pX` states are identified
  independently of the predicate under test, and each is asserted to have
  exactly one valid successor.
- Prefix coverage: every prefix of every valid history validates, and the
  causally impossible prefixes (`F` first, `XA`, `PA`) are rejected. The
  converse is pinned too — the accepted set is exactly the prefix-closure of
  the 70 valid histories, so no accepted prefix is a dead end (CSB-17-005).
- Input coercion: because `CSEvent` is a `StrEnum`, the single-letter strings of
  the legacy API are accepted on every entry point and produce identical
  verdicts; the bool-returning predicates answer `False` for non-events rather
  than raising.

## Pros and Cons of the Options

### A. Import and delegate to the legacy validators

- Good, because it is the smallest change and cannot diverge from the legacy
  rules by construction.
- Bad, because it makes the enum models permanently depend on string/regex
  validation and on the legacy `CvdStateModelError` tree.
- Bad, because it cannot express prefix validity — `is_valid_history` requires
  all six events, so live in-progress cases remain unvalidatable.
- Bad, because it contradicts the issue's explicit preference for a deliberate
  rewrite over `import and use`.

### B. Re-express; keep the legacy module as reference and oracle

- Good, because the current models gain the rules in their own idiom, with their
  own errors and their own types.
- Good, because the legacy implementation becomes an independent oracle that
  proves the rewrite faithful over the entire state space.
- Good, because replay-based history validity generalises to prefixes.
- Neutral, because two implementations coexist until the migration completes.
- Bad, because retirement becomes a tracked intention rather than a done deed.

### C. Re-express and retire the legacy module now

- Good, because it leaves exactly one implementation of the rules.
- Bad, because it destroys the only independent evidence that the rewrite is
  correct, at the moment that evidence is most needed.
- Bad, because two live importers make this a migration; `cs.py` itself depends
  on `validations.ensure_valid_state`.
- Bad, because it would discard the analytical model (scoring, desiderata,
  pagerank) that has no current-idiom replacement and needs none.

### D. Archive the whole `case_states/` tree out of `vultron/`

- Good, because it makes the non-normative status unmistakable.
- Bad, because it has all of C's problems plus the loss of the existing
  `test/core/case_states/` suite.
- Bad, because the `actors_get_action_rules` endpoint would break immediately.

## More Information

The "completely orphaned" premise in issue #2237 is incorrect and the correction
matters for the decision — see `plan/incoming/learnings/`. Cross-machine
(RM/EM × CS) emit-guard enforcement is #2236, which this issue blocks.

Source model: Householder, A. D., and Spring, J. *A State-Based Model for
Multi-Party Coordinated Vulnerability Disclosure (MPCVD)*, CMU/SEI-2021-SR-021,
<https://doi.org/10.1184/R1/16416771>.

Generated spec requirements: `cs-behavior.yaml` CSB-17-001 through CSB-17-004.
Related: ADR-0036 (dimension objects), CSB-13-001 (pX→PX entry cascade),
CSB-16-001/002 (write-boundary transition validation).
