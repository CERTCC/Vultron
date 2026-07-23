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
| `STOCHASTIC` | Probabilistic fuzzer classes (`UsuallySucceed`, `ProbablyFail`, …) | Opt-in for simulation / fuzz-testing scenarios |
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
| `AcquireExploitCallOutBundle` | Exploit acquisition | `create_acquire_exploit_tree`, `create_acquire_exploit_strategy_tree` |
| `AssignVulIdCallOutBundle` | Vulnerability ID assignment | `create_assign_vul_id_tree` |
| `CloseReportCallOutBundle` | Report closure | `create_close_report_tree` |

### Module layout

```text
vultron/demo/fuzzer/
  bundles/
    __init__.py     ← re-exports all bundle classes and singletons
    validation.py   ← ValidationCallOutBundle + singletons
    prioritization.py
    embargo.py
    publication.py
    report_to_others.py
    deploy_fix.py
    acquire_exploit.py
    assign_vul_id.py
    close_report.py
```

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
issue #PERSONALITY_ISSUE_PLACEHOLDER (type:Idea, to be created). The bundle
dataclass structure defined here is sufficient to support personality variants
without modification; no new mechanism is needed.

---

## Relationship to ADR-0025

ADR-0025 established the factory injection seam but left the question of
"how does running code choose which factory" explicitly open ("formed in sand,
not concrete"). This note fills that gap. ADR-0025 has been updated to reflect
the bundle/singleton/Protocol pattern as the resolved design. See
`docs/adr/0025-call-out-point-abstraction-layer.md` § "Bundle Selection
Mechanism (2026-07-23 amendment)".

Normative requirements: `specs/behavior-tree-integration.yaml` BT-21.
