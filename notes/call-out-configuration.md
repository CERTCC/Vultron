---
title: "Call-Out Point Configuration System — Backend Selection Design"
status: active
description: >
  Design decisions for how running code selects backend factories for call-out
  point nodes in BT tree builders. Covers the three-mode model, domain bundle
  dataclasses, pre-built singletons, and extension points. Derived from the
  planning session for issue #1631.
related_specs:
  - specs/behavior-tree-integration.yaml
related_notes:
  - notes/coordination-agents.md
  - notes/bt-fuzzer-nodes.md
  - notes/configuration.md
relevant_packages:
  - vultron/core/behaviors
  - vultron/demo/fuzzer
  - vultron/demo/exchange
---

# Call-Out Point Configuration System — Backend Selection Design

## Background

ADR-0025 established the factory-based injection pattern for call-out points:
tree-building functions accept `CallOutBackendFactory` kwargs and default to
fuzzer/deterministic backends (BT-18-004). After #1151 delivered the exemplar
implementations, one design gap remained: **how does running code — a demo
scenario, a test fixture, or eventually a production actor — decide which
factory to inject for each call-out point?**

This note documents the decisions reached in the #1631 planning session.
The pattern is implemented by #1152 (FUZZ-08c).

---

## Three-Mode Model

There are three logical modes for call-out point backends:

| Mode | Backends used | When used |
|---|---|---|
| `DETERMINISTIC` | `AlwaysSucceed` / `AlwaysFail` (ceiling/floor of stochastic p) | Default for all demo and test scenarios |
| `STOCHASTIC` | Probabilistic fuzzer classes (`UsuallySucceed`, `ProbablyFail`, …) | Opt-in for simulation / fuzz-testing scenarios. Canonical entry point: `vultron/demo/fuzzer/stochastic_demo.py` (run via `python -m vultron.demo.fuzzer.stochastic_demo`). |
| `REAL` | Production implementations (data lookups, policy engines, agents) | Deferred to FUZZ-08d through FUZZ-08h |

**Test vs. demo** is a call-context distinction, not a mode distinction.
`DETERMINISTIC` backends are identical whether used in a pytest fixture or a
demo script.

### Default direction rule

The default for any tree builder is `DETERMINISTIC`. `STOCHASTIC` is always
opt-in.

Within `DETERMINISTIC`, the backend for each node is derived from its
stochastic counterpart by the **ceiling/floor rule**:

- If the fuzzer node's success probability `p > 0.5` → `AlwaysSucceed`
- If `p < 0.5` → `AlwaysFail`
- If `p == 0.5` → `AlwaysSucceed` (happy path; see below)

The `p == 0.5` tie-breaking default is `AlwaysSucceed` because the intended
use of the deterministic bundle is a **happy-path demonstration** in which the
protocol makes forward progress. Scenarios that need to exercise failure paths
should use a pessimistic bundle or inject an explicit `AlwaysFail` factory.

**Security-significant gate exception (ADR-0076, ADR-0025 amended):** For
call-out points whose permissive default enables unilateral state change or
embargo consequences — e.g., `CaseOwnerApprovesStatusUpdate` in
`StatusAdoptionGate` and `EmbargoTeardownAuthorizationGate` — the
DETERMINISTIC default MUST be `RequireCaseOwnerApproval`, not `AlwaysSucceed`,
regardless of stochastic p. The ceiling/floor rule applies only to
simulation-domain nodes where permissiveness is a prototype-stage convenience.
See RSH-07-001 and RSH-07-002.

Currently there are four `p=0.5` nodes (all default to `AlwaysSucceed`):

| Node | Domain | Rationale |
|---|---|---|
| `FollowUpOnErrorMessage` | Messaging | Happy path = can compose a follow-up |
| `WantToProposeEmbargo` | Embargo | Happy path = want to propose |
| `AllPartiesKnown` | Reporting to others | Happy path = all parties identified |
| `NotificationsComplete` | Reporting to others | Happy path = notifications done |

---

## Domain Bundle Dataclasses

Call-out factories are grouped into **domain bundles** — one frozen
`@dataclass` per domain area. Each bundle holds exactly the set of
`CallOutBackendFactory` fields consumed by the tree builders in that domain.
Two **pre-built singleton instances** are provided per domain:
`<DOMAIN>_DETERMINISTIC` and `<DOMAIN>_STOCHASTIC`.

### Structure pattern

```python
from __future__ import annotations
from dataclasses import dataclass, field
import py_trees

from vultron.core.behaviors.call_out_point import CallOutBackendFactory


@dataclass(frozen=True)
class ValidationCallOutBundle:
    """Call-out backend bundle for the report validation workflow."""

    credibility_factory: CallOutBackendFactory = field(
        default_factory=lambda: _default_credibility_factory
    )
    validity_factory: CallOutBackendFactory = field(
        default_factory=lambda: _default_validity_factory
    )
    gather_info_factory: CallOutBackendFactory = field(
        default_factory=lambda: _default_gather_info_factory
    )


# Pre-built singletons (import once, use everywhere)
VALIDATION_DETERMINISTIC = ValidationCallOutBundle(
    credibility_factory=lambda n: AlwaysSucceed(n),
    validity_factory=lambda n: AlwaysSucceed(n),
    gather_info_factory=lambda n: AlwaysSucceed(n),
)
VALIDATION_STOCHASTIC = ValidationCallOutBundle(
    credibility_factory=lambda n: EvaluateReportCredibility(n),
    validity_factory=lambda n: EvaluateReportValidity(n),
    gather_info_factory=lambda n: GatherValidationInfo(n),
)
```

### Tree builder integration

Tree builders replace individual factory kwargs with a single typed bundle
parameter:

```python
def create_validate_report_tree(
    report_id: str,
    offer_id: str,
    captured: dict | None = None,
    call_out: ValidationCallOutBundle = VALIDATION_DETERMINISTIC,
) -> py_trees.behaviour.Behaviour:
    credibility_node = call_out.credibility_factory("EvaluateReportCredibility")
    validity_node    = call_out.validity_factory("EvaluateReportValidity")
    ...
```

Demo and test code imports the pre-built singleton:

```python
from vultron.demo.fuzzer.bundles.validation import VALIDATION_STOCHASTIC

tree = create_validate_report_tree(
    report_id=report.id,
    offer_id=offer.id,
    call_out=VALIDATION_STOCHASTIC,
)
```

### Domain areas

One bundle is defined per domain area (matching the `vultron/demo/fuzzer/`
sub-module layout):

| Bundle class | Domain | Tree builder(s) |
|---|---|---|
| `ValidationCallOutBundle` | Report validation | `create_validate_report_tree` |
| `PrioritizationCallOutBundle` | Report prioritization | `create_prioritize_subtree` |
| `EmbargoCallOutBundle` | Embargo management | `create_manage_embargo_tree` |
| `PublicationCallOutBundle` | Publication pipeline | `create_publication_tree`, `create_publish_artifact_tree` |
| `ReportToOthersCallOutBundle` | Reporting to others | `create_report_to_others_tree` |
| `DeployFixCallOutBundle` | Fix deployment | `create_deploy_fix_tree` |
| `DeployMitigationCallOutBundle` | Mitigation deployment | `create_deploy_mitigation_tree` |
| `AcquireExploitCallOutBundle` | Exploit acquisition | `create_acquire_exploit_tree`, `create_acquire_exploit_strategy_tree` |
| `AssignVulIdCallOutBundle` | Vulnerability ID assignment | `create_assign_vul_id_tree` |
| `CloseReportCallOutBundle` | Report closure | `create_close_report_tree` |
| `StatusAuthorizationCallOutBundle` | Received-side status authorization | `add_participant_status_tree`, `add_case_status_tree` |

### PrioritizationCallOutBundle fields

| Field | Node replaced | p (stochastic) | Deterministic default |
|---|---|---|---|
| `evaluate_priority_factory` | `EvaluateCasePriority` | 1.0 → `AlwaysSucceed` | `AlwaysSucceed` (always engage; SSVC deferred — PROTO-05-001) |
| `on_accept_factory` | `OnAccept` | 1.0 → `AlwaysSucceed` | `AlwaysSucceed` |
| `on_defer_factory` | `OnDefer` | 1.0 → `AlwaysSucceed` | `AlwaysSucceed` |
| `enough_info_factory` | `EnoughPrioritizationInfo` | 0.75 → `AlwaysSucceed` | `AlwaysSucceed` (Phase 2 reserved) |
| `gather_info_factory` | `GatherPrioritizationInfo` | 0.90 → `AlwaysSucceed` | `AlwaysSucceed` (Phase 2 reserved) |

`evaluate_priority_factory` is the production SSVC seam (PROTO-05-001). In DETERMINISTIC
mode it resolves `AlwaysSucceed` so all cases are engaged. In STOCHASTIC mode it uses the
`EvaluateCasePriority` fuzzer node. A real SSVC evaluator would implement
`CallOutBackendFactory` and be passed here — no other code change required.

### Module layout (corrected 2026-07-29, issue #1793)

The bundle **dataclasses**, the `CallOutBackendFactory` Protocol, the
deterministic `AlwaysSucceed`/`AlwaysFail` nodes, and the
`<DOMAIN>_DETERMINISTIC` singletons are **core-owned**. Only the probabilistic
`WeightedBehavior` fuzzer nodes and the `<DOMAIN>_STOCHASTIC` singletons are
simulation artifacts. Core tree builders default to the core DETERMINISTIC
singleton and never import from `vultron/demo/` (enforced by
`test/architecture/test_core_no_demo_imports.py`).

```text
vultron/core/behaviors/call_out/     ← core-owned seam
  __init__.py       ← re-exports CallOutBackendFactory, AlwaysSucceed, AlwaysFail
  protocol.py       ← CallOutBackendFactory Protocol (canonical home)
  nodes.py          ← deterministic AlwaysSucceed / AlwaysFail
  bundles/
    __init__.py     ← re-exports all bundle classes + <DOMAIN>_DETERMINISTIC
    validation.py   ← ValidationCallOutBundle + VALIDATION_DETERMINISTIC
    prioritization.py
    embargo.py
    publication.py
    report_to_others.py
    deploy_monitoring.py  ← DeploymentMonitoringBundle (shared base)
    deploy_fix.py         ← DeployFixCallOutBundle + DEPLOY_FIX_DETERMINISTIC
    deploy_mitigation.py  ← DeployMitigationCallOutBundle + DEPLOY_MITIGATION_DETERMINISTIC
    acquire_exploit.py
    assign_vul_id.py
    close_report.py
    status_authorization.py   ← StatusAuthorizationCallOutBundle + STATUS_AUTHORIZATION_DETERMINISTIC

vultron/demo/fuzzer/                  ← simulation-only
  base.py           ← WeightedBehavior family (incl. its own AlwaysSucceed/Fail)
  bundles/
    __init__.py     ← re-exports bundle classes + both DETERMINISTIC/STOCHASTIC
    validation.py   ← VALIDATION_STOCHASTIC (+ re-exports core dataclass/default)
    ...             ← one per domain, STOCHASTIC singletons only
```

> **History**: the original 2026-07-23 design placed the dataclasses and
> `<DOMAIN>_DETERMINISTIC` singletons under `vultron/demo/fuzzer/bundles/` and
> had core tree builders import them — a core→demo inversion that violated
> BT-16-001. Issue #1793 moved the core-owned pieces into
> `vultron/core/behaviors/call_out/` and added the boundary ratchet. `vultron.core.behaviors.call_out_point` remains as a
> backward-compatible re-export shim of the Protocol.

---

## CallOutBackendFactory as a Protocol

The `CallOutBackendFactory` type alias is promoted to a `typing.Protocol` so
static type checkers (mypy, pyright) can verify that a new backend callable
matches the expected signature:

```python
# vultron/core/behaviors/call_out_point.py
from typing import Protocol, runtime_checkable

import py_trees


@runtime_checkable
class CallOutBackendFactory(Protocol):
    """Protocol for call-out point backend factories.

    A factory must accept a single ``name: str`` argument (the BT node's
    display name) and return a ``py_trees.behaviour.Behaviour`` that honours
    the call-out point's declared blackboard contract (BT-18-001 through
    BT-18-004).
    """

    def __call__(self, name: str) -> py_trees.behaviour.Behaviour:
        ...
```

Any callable that satisfies this signature (including plain lambdas and module-
level functions) is a valid backend. No registration, inheritance, or decorator
is required. Static type checking via pyright/mypy is the validation mechanism.

---

## Extensibility

To add a new backend for a call-out point:

1. Implement a callable matching `CallOutBackendFactory` — a function or class
   that accepts `name: str` and returns a `py_trees.behaviour.Behaviour`
   honouring the blackboard contract (BT-18-001 through BT-18-004).
2. Instantiate the domain bundle with the new factory in the relevant field:

   ```python
   my_bundle = ValidationCallOutBundle(
       credibility_factory=MyRealCredibilityEvaluator,
   )
   ```

3. Pass the bundle to the tree builder.

No central registry, decorator, or base class is required for the backend
itself. The bundle dataclass enforces completeness (all fields must be
supplied; unspecified fields use the bundle class defaults).

### Future: YAML/CLI configuration surface

YAML or CLI configuration of call-out backends is deferred to the production
path (FUZZ-08d through FUZZ-08h or a follow-on production-config issue). The
production configuration surface will map domain names + mode strings to bundle
singletons or factory class paths. The bundle dataclass structure defined here
is the natural target for that mapping.

---

## Future: Personality / Bias Bundles

The three-mode model (deterministic / stochastic / real) is the foundation;
personality variants are a future layer on top. A **personality bundle** is
a domain bundle instantiated with factories that have a *biased* probability
distribution, allowing actor-level behavioural differences in multi-actor
simulation:

```python
# Example (not yet implemented)
PESSIMISTIC_EMBARGO = EmbargoCallOutBundle(
    want_to_propose_embargo_factory=lambda n: AlwaysFail(n),      # never proposes
    current_embargo_acceptable_factory=lambda n: UsuallyFail(n),  # rarely accepts
    ...
)
```

This enables scenarios such as a "recalcitrant embargo negotiator" paired
with a "cooperative embargo negotiator" to explore interaction dynamics.

Personality/bias bundles are tracked as a separate design question in
issue #1646 (type:Idea). The bundle
dataclass structure defined here is sufficient to support personality variants
without modification; no new mechanism is needed.

---

## Production-Only Domains: STOCHASTIC Bundle Without Fuzzer Nodes

(ISSUE-1843, 2026-07-30)

Some call-out domains are **production-only patterns** with no legacy simulator
counterpart — the call-out seams did not exist in the old `vultron/bt/`
simulation and no named probabilistic fuzzer classes were written for them.
`StatusAuthorizationCallOutBundle` (ADR-0046, #1843) is the first such domain.

**How to build the STOCHASTIC singleton for a production-only domain**:

Use the **generic `WeightedBehavior` subclass whose success rate equals the
`p` implied by the DETERMINISTIC ceiling**:

- DETERMINISTIC ceiling is `AlwaysSucceed` (p → 1.0): use `AlmostAlwaysSucceed`
  (p = 0.90) for the STOCHASTIC singleton.
- DETERMINISTIC ceiling is `AlwaysFail` (p → 0.0): use `AlmostAlwaysFail` for
  the STOCHASTIC singleton.

**Rationale**: `AlmostAlwaysSucceed` (p = 0.90) matches the p = 0.90
convention used by other Evaluator call-outs (e.g., report credibility/validity)
and aligns with the ceiling/floor rule already established for all other
domains. It still occasionally exercises the reject/block path during fuzz
runs — which a literal mirror of DETERMINISTIC (both `AlwaysSucceed`) would
not.

**Contrast with domains that have fuzzer node counterparts**: For domains with
existing named simulator nodes (e.g., `EvaluateReportCredibility`), the
STOCHASTIC singleton wires those named classes directly. Only for production-
only domains does the generic `AlmostAlwaysSucceed`/`AlmostAlwaysFail`
fallback apply.

<!-- Source: ISSUE-1843; user confirmed the AlmostAlwaysSucceed choice -->

---

## Relationship to ADR-0025

ADR-0025 established the factory injection seam but left the question of
"how does running code choose which factory" explicitly open ("formed in sand,
not concrete"). This note fills that gap. ADR-0025 has been updated to reflect
the bundle/singleton/Protocol pattern as the resolved design. See
`docs/adr/0025-call-out-point-abstraction-layer.md` § "Bundle Selection
Mechanism (2026-07-23 amendment)".

Normative requirements: `specs/behavior-tree-integration.yaml` BT-23.

---

## Multi-Actor In-Process Simulation

The three-mode model and STOCHASTIC bundles are the foundation for the
**fully-fuzzed in-process simulation scenario** tracked in issue #1178 (see
spec `DEMOMA-18`).

### Design decisions (from #1178 planning)

**In-process delivery via direct DataLayer injection** was chosen over two
alternatives:

- *ASGIEmitter loopback* — more realistic wire path, but requires spinning up
  a FastAPI ASGI application per actor and routing inbound AS2 JSON through
  the full HTTP pipeline; significant setup overhead for a simulation tool.
- *In-memory message queue* — closest to the conceptual worker model in
  `notes/event-driven-control-flow.md`, but requires new infrastructure
  (a queue type + delivery scheduler) with no benefit over direct injection
  for an in-process simulation.

Direct injection: when actor A's BT emits an activity to actor B, the
simulation controller intercepts A's outbox and directly calls B's dispatcher
with the activity object. No network, no serialisation round-trip. The full
trigger→BT→outbox→peer-inbox cascade is exercised within the single Python
process.

**Finder + Coordinator + Vendor (3 actors)** was chosen as the minimum
meaningful configuration. FV (2 actors) omits coordinator role interactions;
FCV (3) covers the core multi-party CVD pattern exercised by existing
deterministic scenario demos.

**Fresh in-memory DataLayer per iteration** ensures each iteration is an
independent probabilistic sample. Persisting state across iterations would
cause later runs to depend on earlier ones.

**Multi-container variant deferred** — a future Idea under a new "stochastic
demos" Epic should scope a containerised fuzz scenario once container reset
and STOCHASTIC bundle configuration via environment variables are designed.

### Termination model

The simulation controller drives each iteration forward by:

1. Calling a trigger on one actor (Finder submits report).
2. Processing each outbox emission as an inbound activity on the target actor.
3. Repeating until all actors reach `RM.CLOSED` or no state change occurs
   over a configurable number of rounds (stall detection).

A tick-count-only limit was rejected because many use-case BTs only activate
on incoming activities; "ticks" have no direct meaning in the event-driven
prototype. Progress is measured by RM state advancement across actors.
