---
title: "Call-Out Point Configuration System — Backend Selection Design"
status: active
kind: guidance
description: >
  How running code selects backend factories for call-out point nodes in BT
  tree builders: the three-mode model and its ceiling/floor default rule, domain
  bundles and singletons, the security-significant gate verdicts, STOCHASTIC
  bundles for production-only domains, and why a data-producing capability's
  default must write its declared outputs.
related_specs:
  - specs/behavior-tree-integration.yaml
  - specs/behavior-tree-node-design.yaml
  - specs/received-status-handling.yaml
  - specs/em-behavior.yaml
  - specs/case-proposal.yaml
  - specs/prototype-shortcuts.yaml
related_notes:
  - notes/bt-pitfalls.md
  - notes/bt-integration.md
  - notes/bt-canonical-reference.md
  - notes/coordination-agents.md
  - notes/call-out-simulation-plan.md
  - notes/configuration.md
  - notes/received-status-authorization.md
  - notes/embargo-lifecycle.md
  - notes/protocol-asks.md
relevant_packages:
  - vultron/core/behaviors/call_out
  - vultron/demo/fuzzer
  - vultron/demo/exchange
---

# Call-Out Point Configuration System — Backend Selection Design

ADR-0025 makes tree builders accept `CallOutBackendFactory` backends (BT-18-004).
This note covers how running code (a demo, a test fixture, a deployment) picks
which backend each call-out point gets. Normative requirements: BT-23. The
fuzzer node catalog is `docs/developer/reference/bt-fuzzer/index.md`.

---

## Three-Mode Model

| Mode | Backends used | When used |
|---|---|---|
| `DETERMINISTIC` | `AlwaysSucceed` / `AlwaysFail` (ceiling/floor of stochastic p) | Default for every tree builder, demo, and test |
| `STOCHASTIC` | Probabilistic fuzzer classes (`UsuallySucceed`, `ProbablyFail`, …) | Opt-in simulation; entry point `python -m vultron.demo.fuzzer.stochastic_demo` |
| `REAL` | Production implementations (data lookups, policy engines, agents) | Injected by a deployment |

Test vs. demo is a call-context distinction, not a mode: `DETERMINISTIC`
backends are identical in a pytest fixture and a demo script.

### Default direction rule

The default for any tree builder is `DETERMINISTIC`; `STOCHASTIC` is always
opt-in. Within `DETERMINISTIC`, each backend follows the **ceiling/floor rule**
on its stochastic counterpart's success probability `p`:

- `p > 0.5` → `AlwaysSucceed`
- `p < 0.5` → `AlwaysFail`
- `p == 0.5` → `AlwaysSucceed`, because the deterministic bundle is a happy-path
  demonstration in which the protocol makes forward progress. A scenario that
  needs a failure path injects an explicit `AlwaysFail` factory.

> **The ceiling/floor rule fixes the status direction only.** For a capability
> that declares output ports, the ceiling is a *contract-honouring* backend — one
> that writes type-conformant values to every declared port — not a bare
> `AlwaysSucceed` (BT-23-013). See
> [A data-producing capability's default must write its outputs](#a-data-producing-capabilitys-default-must-write-its-outputs).

**Security-significant gate exception (BT-23-012, ADR-0076):** a call-out
point whose permissive default would enable unilateral state change or embargo
consequences defaults to the conservative backend regardless of `p`. See the
next section.

---

## Security-Significant Gate Audit

> A gate qualifies as **security-significant** when its permissive backend
> would let a party **other than the Case Owner** *unilaterally* cause
> **canonical case-state adoption** or **embargo teardown** on the **received
> side** — not merely operational inconvenience. (BT-23-012)

Every new gate owes this section a written verdict.
`test/core/behaviors/call_out/test_security_significant_defaults.py` discovers
bundle singletons reflectively, so it proves a verdict was applied, not that it
was reasoned.

### Qualifying gates (default conservative)

| Gate | Bundle field | Default |
|---|---|---|
| `StatusAdoptionGate` (`CaseOwnerApprovesStatusUpdate`) | `status_adoption_gate_factory` | `RequireCaseOwnerApprovalNode` (RSH-07-001) |
| `EmbargoTeardownAuthorizationGate` | `embargo_teardown_authorization_gate_factory` | `RequireCaseOwnerApprovalNode` (RSH-07-002) |

`STATUS_AUTHORIZATION_PERMISSIVE` is the explicit opt-in override; the FastAPI
inbox adapter wires it for the two inbound status semantics
(`vultron/adapters/driving/fastapi/inbox_port_factories.py`), so the
trusted-deployment posture is visible in code (RSH-07-003).

**Posture vs. mechanism.** The table fixes the *posture* (these gates default
to the floor). The *mechanism*, `RequireCaseOwnerApprovalNode`, is an interim
stub that returns `FAILURE` unconditionally; RSH-07-004 (ADR-0080) replaces it
with a conversation-state routing subtree and forbids an unconditional-`FAILURE`
default. When that lands, keep both rows and rewrite
`test_status_gates_conservative_default_blocks` to assert the security property
rather than the `FAILURE` tick.

### Look-alike gates that do NOT qualify (default stays permissive)

Do not "harden" these when auditing for `AlwaysSucceed` on an
authorization-flavored gate:

- **`CaseOwnerApprovesEmbargoResponse`**
  (`case_owner_approves_embargo_response_factory`,
  `embargo/response_decision_tree.py`) — received-side, but accept-by-default is
  required by EMB-15-001, and entering an embargo is the protective direction.
  A blocking default would violate EMB-15-001 and route non-owners to the
  reject arm, reducing embargo protection.
- **`EmbargoExitPolicyGuard`** (`embargo_exit_policy_guard_factory`,
  `embargo/terminate_active_embargo_tree.py`) — authorizes exit, but it is a
  trigger-side seam for the actor's own voluntary exit, behind a fail-closed
  reason Selector (every `exit_embargo_*` reason factory defaults `AlwaysFail`),
  and EMB-14-002 frames it as an optional veto. A blocking default would kill
  EMB-14's voluntary-exit path. The received-side teardown path is covered by
  `EmbargoTeardownAuthorizationGate`.
- **`CaseProposalCallOutBundle.evaluate_proposal_factory`**
  (`EvaluateCaseProposal`, CP-05-002) — admitting a proposal creates a *new* case
  owned by the proposer; no existing case's state or embargo is touched. The
  permissive default also keeps an unconfigured deployment admitting
  unconditionally, as it did before the seam existed (BT-23-001, BT-23-011).
  The seam exists for admission policy a deployment injects (#3399).

### Remaining gates

Every other bundle field (validation, prioritization, ID assignment, exploit
acquisition, fix/mitigation deployment and monitoring, closure, publication,
actor discovery, the remaining embargo evaluators) is a local operational
decision with no way to impose case state or an embargo consequence on another
party. The ceiling/floor rule governs them (BT-23-002/006/007).

---

## Domain Bundles

Call-out factories are grouped into one frozen dataclass per domain area,
holding exactly the `CallOutBackendFactory` fields that domain's tree builders
consume. Each domain has two pre-built singletons, `<DOMAIN>_DETERMINISTIC` and
`<DOMAIN>_STOCHASTIC`, and a tree builder takes one typed `call_out:` bundle
parameter defaulting to the deterministic singleton. The bundle list lives in
`vultron/core/behaviors/call_out/bundles/__init__.py`.

**Layering rule (BT-16-001):** the bundle dataclasses, the
`CallOutBackendFactory` Protocol (`call_out/protocol.py`), the deterministic
`AlwaysSucceed`/`AlwaysFail` nodes, and the `<DOMAIN>_DETERMINISTIC` singletons
are core-owned under `vultron/core/behaviors/call_out/`. Only the probabilistic
`WeightedBehavior` nodes and the `<DOMAIN>_STOCHASTIC` singletons live under
`vultron/demo/fuzzer/`. Core never imports from `vultron/demo/`
(`test/architecture/test_core_no_demo_imports.py`). New code imports the
Protocol from `vultron.core.behaviors.call_out`, not the
`call_out_point` re-export shim.

### Adding a backend

A backend is any callable matching `CallOutBackendFactory`: it takes
`name: str` and returns a `py_trees.behaviour.Behaviour` that honours the
call-out point's blackboard contract (BT-18-001 through BT-18-004). No
registry, decorator, or base class is needed; pyright/mypy check the
signature. Instantiate the domain bundle with the new factory in its field
(unspecified fields keep the bundle defaults) and pass the bundle to the tree
builder.

`PrioritizationCallOutBundle.evaluate_priority_factory` is the production SSVC
seam (PROTO-05-001): a real SSVC evaluator is passed there with no other code
change.

---

## Production-Only Domains: STOCHASTIC Bundle Without Fuzzer Nodes

A domain with no legacy simulator counterpart (e.g.
`StatusAuthorizationCallOutBundle`, ADR-0046) has no named fuzzer classes. Its
STOCHASTIC singleton uses the generic `WeightedBehavior` subclass nearest the
DETERMINISTIC ceiling:

- ceiling `AlwaysSucceed` → `AlmostAlwaysSucceed` (p = 0.90)
- ceiling `AlwaysFail` → `AlmostAlwaysFail`

p = 0.90 matches the other Evaluator call-outs and still occasionally exercises
the reject path during fuzz runs, which a literal `AlwaysSucceed` mirror would
not. Domains with named simulator nodes wire those classes directly.

---

## Capabilities Grounded in External Versioned Standards Are One Call-Out Unit

When a capability is grounded in an external, independently-versioned
specification (e.g. CNA Operational Rules), model the whole capability as one
Evaluator call-out point, not one per criterion. The substitution unit is the
rules edition; N call-outs would make adopting a new edition N factory changes.
See BTND-05-007.

## Automation Potential and Call-Out Point Shape Are Orthogonal

Assign shape using the ADR-0024 seam-structure decision tree only — not by how
automatable the step looks. See BT-18-005, BT-18-006.

---

## A Data-Producing Capability's Default Must Write Its Outputs

A backend that returns `SUCCESS` while writing none of its declared output keys
violates BT-18-002. For a capability whose declaration names output ports, a
bare `AlwaysSucceed` does exactly that, so it is not a legal DETERMINISTIC
default whatever the ceiling rule says about direction (BT-23-013).
`AlwaysSucceed` is shape-blind and cannot write outputs it cannot enumerate,
which is why BT-18-012 puts the declaration in core.

The gap is silent: a downstream gate declares the key
`PortInformation(..., required=False)` and returns `FAILURE` when it is absent,
so the arm becomes a no-op and the tree still goes green.

**Diagnostic**: if a data-gated arm never fires in DETERMINISTIC mode, check
whether the capability's default writes its declared ports before looking at the
gate. Distrust a test that hand-writes a capability's output key before ticking
a **whole tree** — it usually compensates for a non-conforming default. Hand-writing
the key is fine in a unit test of the *gate* alone. `test_publication_tree.py`
shows both.

The STOCHASTIC side has the same obligation (BT-18-003). The shape base classes
write a zero-value instance per declared port; the generic
`AlmostAlwaysSucceed`/`AlmostAlwaysFail` used for production-only domains is as
shape-blind as `AlwaysSucceed` and needs the same contract-honouring treatment
on a data-producing capability.
