# Wiring a Capability into the Reference Implementation

{% include-markdown "../includes/not_normative.md" %}

!!! note "Scope of this page"

    This guide is for developers who want to replace a call-out stub in the
    Vultron reference implementation with real logic — a data lookup, a
    decision engine, an LLM (large language model) call, or any service that
    can answer the protocol's question at that point.

    For the conceptual model — what call-out points are, what the five
    capability shapes mean, and why the reference implementation uses fuzzer
    stubs during development — see
    [Capability Model](../topics/capability_model/index.md).
    For the overall reference implementation architecture, see
    [Reference Implementation Architecture](../topics/reference_architecture.md).

---

## Background

The reference implementation's [behavior trees](../topics/behavior_logic/index.md) (BTs) contain **call-out
points** — nodes where the protocol cannot determine the correct next action
autonomously and must request a decision, fact, or side-effect from an
external service. During development and simulation, each call-out point is
filled by a **fuzzer node**: a stub that returns a random SUCCESS or FAILURE
based on a probability. In production, you replace a fuzzer node with a
**real capability backend** that applies actual business logic.

The three-step process is:

1. **Identify** the call-out point you want to implement (find the fuzzer node, read its blackboard contract).
2. **Implement** a backend factory that satisfies the `CallOutBackendFactory` Protocol.
3. **Wire** the backend by passing it through the domain bundle to the tree builder.

---

## Step 1 — Identify the call-out point

### Find the fuzzer node

Every call-out point in the reference implementation has a corresponding
fuzzer node in `vultron/demo/fuzzer/`. Browse by domain:

| Domain | Fuzzer module |
|---|---|
| Report validation | `vultron/demo/fuzzer/report_management/validate.py` |
| Report prioritization | `vultron/demo/fuzzer/report_management/prioritize.py` |
| Embargo management | `vultron/demo/fuzzer/embargo.py` |
| CVE / Vulnerability ID assignment | `vultron/demo/fuzzer/report_management/assign_vul_id.py` |
| Fix development | `vultron/demo/fuzzer/report_management/develop_fix.py` |
| Fix deployment | `vultron/demo/fuzzer/report_management/deploy_fix.py` |
| Exploit acquisition | `vultron/demo/fuzzer/report_management/acquire_exploit.py` |
| Publication | `vultron/demo/fuzzer/report_management/publication.py` |

The [Capability Model](../topics/capability_model/index.md) page lists every
known integration point by domain and shape.

Each fuzzer node's docstring tells you:

- **What decision or fact it represents** ("Assess whether the report's
  source and content are credible").
- **Input category** — `Human decision`, `Environmental check`, or
  `System integration`.
- **Automation potential** — `High`, `Medium`, or `Low`.
- **Success probability** — which probability class the stub uses, and
  therefore what the production default (the deterministic ceiling or floor)
  will be.

### Read the blackboard contract

The fuzzer node's docstring contains a **blackboard contract** section
(BT-18-001). This contract lists the keys the node reads from and writes to
the shared BT blackboard:

```python
class EvaluateReportCredibility(EvaluatorCallOutPoint, AlmostAlwaysSucceed):
    """Assess whether the report's source and content are credible.

    ...

    Blackboard contract (BT-18-001):
      Input keys:  (none — evaluates report context from caller's DataLayer)
      Output keys: report_credibility_verdict: str  (SUCCESS only)
    ...
    """

    output_keys = {"report_credibility_verdict": str}
```

Your backend must honor this contract: read any declared input keys from the
blackboard and write any declared output keys on SUCCESS. The tree will fail
unexpectedly if you skip a required write.

---

## Step 2 — Implement a backend factory

### The `CallOutBackendFactory` Protocol

A backend factory is any callable that satisfies the
`CallOutBackendFactory` Protocol:

```python
from vultron.core.behaviors.call_out import CallOutBackendFactory

class CallOutBackendFactory(Protocol):
    def __call__(self, name: str) -> py_trees.behaviour.Behaviour: ...
```

The factory accepts a single `name: str` argument (the BT node's display
name) and returns a `py_trees.behaviour.Behaviour`. Any callable that matches
this signature is valid — a plain function, a lambda, or a class with
`__call__`. No registration, inheritance, or decorator is required.

### Implementing as a `py_trees.behaviour.Behaviour` subclass

Subclass `py_trees.behaviour.Behaviour` and implement both `setup()` and
`update()`. The `setup()` method runs once when the tree is first started —
it registers the blackboard keys your node will write. The `update()` method
runs on every BT tick.

!!! warning "Blackboard access requires `setup()`"

    py_trees does **not** create `self.blackboard` automatically. You must
    call `self.attach_blackboard_client()` in `setup()` and register each
    key before `update()` can use them. Skipping this raises `AttributeError`
    on the first tick.

```python
import py_trees
from py_trees.common import Access, Status


class MyCredibilityEvaluator(py_trees.behaviour.Behaviour):
    """Real credibility evaluator backed by a reputation scoring service.

    Blackboard contract (BT-18-001):
      Input keys:  (none — queries reputation service using DataLayer context)
      Output keys: report_credibility_verdict: str  (SUCCESS only)
    """

    def __init__(self, name: str) -> None:
        super().__init__(name=name)

    def setup(self, **kwargs) -> None:
        # Register every blackboard key this node writes before update() runs.
        self.blackboard = self.attach_blackboard_client(name=self.name)
        self.blackboard.register_key(
            "report_credibility_verdict", access=Access.WRITE
        )

    def update(self) -> Status:
        verdict = my_reputation_service.evaluate(...)
        if verdict.credible:
            self.blackboard.report_credibility_verdict = verdict.summary
            return Status.SUCCESS
        return Status.FAILURE


# This function is the CallOutBackendFactory.
def my_credibility_factory(name: str) -> py_trees.behaviour.Behaviour:
    return MyCredibilityEvaluator(name)
```

### Implementing as a factory function (no blackboard writes)

When your backend has no blackboard output keys — for example, a binary
yes/no condition check that only needs to return SUCCESS or FAILURE — a
plain module-level function and a minimal class are sufficient:

```python
import py_trees
from py_trees.common import Status


class _CredibilityCheck(py_trees.behaviour.Behaviour):
    """Backend that consults a reputation service. No blackboard writes."""

    def update(self) -> Status:
        score = my_reputation_service.score_reporter(reporter_id=...)
        return Status.SUCCESS if score >= 0.5 else Status.FAILURE


def my_credibility_factory(name: str) -> py_trees.behaviour.Behaviour:
    return _CredibilityCheck(name=name)
```

Use this pattern only when the call-out point's blackboard contract declares
no output keys. If you need to write output keys, use the full
`setup()` + `attach_blackboard_client()` pattern above.

### What to return

| Condition | Return | Blackboard writes |
|---|---|---|
| Decision approved, fact retrieved, artifact created | `SUCCESS` | Write all declared output keys |
| Decision denied, fact unavailable, error | `FAILURE` | None required |

Avoid returning `RUNNING` from a call-out backend. Call-out points in the
reference implementation are designed to be answered synchronously in the
current tick; returning `RUNNING` will suspend the parent `Sequence`
indefinitely with no visible error until you inspect the tree manually.

---

## Step 3 — Wire the backend via the domain bundle

### Domain bundles

Call-out factories are grouped into **domain bundles** — one frozen
`@dataclass` per domain area. Each bundle holds exactly the set of
`CallOutBackendFactory` fields consumed by the tree builders in that domain.
The bundle lives in `vultron/core/behaviors/call_out/bundles/`.

To wire in your backend, instantiate the appropriate bundle with your factory
in the relevant field. Fields you do not specify keep their default
(deterministic `AlwaysSucceed` or `AlwaysFail` as appropriate):

```python
from vultron.core.behaviors.call_out.bundles.validation import (
    ValidationCallOutBundle,
)

my_bundle = ValidationCallOutBundle(
    credibility_factory=my_credibility_factory,
    # validity_factory and gather_info_factory remain deterministic defaults
)
```

### Passing the bundle to a tree builder

Pass the bundle to the tree builder that constructs the behavior tree for
that domain:

```python
from vultron.core.behaviors.report.validate_tree import (
    create_validate_report_tree,
)

tree = create_validate_report_tree(
    report_id=report.id_,
    offer_id=offer.id_,
    call_out=my_bundle,
)
```

The tree builder uses `my_bundle.credibility_factory("EvaluateReportCredibility")`
to create your node at tree-build time. No further wiring is needed.

### Where to keep your bundle

If your backend is deployed in a real actor, create your bundle once at
startup (or in a configuration layer) and pass it to every tree-builder call.
A convenient pattern is a module-level singleton:

```python
# myproject/behaviors/bundles.py

from vultron.core.behaviors.call_out.bundles.validation import (
    ValidationCallOutBundle,
)

MY_VALIDATION_BUNDLE = ValidationCallOutBundle(
    credibility_factory=my_credibility_factory,
)
```

This keeps your production bundle separate from the reference implementation's
deterministic defaults and makes it easy to swap during testing.

---

## Worked example: `EvaluateReportCredibility`

This section shows the full end-to-end process for the
`EvaluateReportCredibility` call-out point.

### 1. Locate the fuzzer node

Open `vultron/demo/fuzzer/report_management/validate.py`:

```python
class EvaluateReportCredibility(EvaluatorCallOutPoint, AlmostAlwaysSucceed):
    """Assess whether the report's source and content are credible.

    Semantic function:
        Condition — assess whether the report's source and content are
        credible (i.e., likely to describe a real vulnerability).
        Credibility criteria may include reporter reputation, technical
        plausibility, and SSVC exploitation status.

    Blackboard contract (BT-18-001):
      Input keys:  (none — evaluates report context from caller's DataLayer)
      Output keys: report_credibility_verdict: str  (SUCCESS only)

    Input category: Human decision.

    Success probability: 0.90 (AlmostAlwaysSucceed).

    Automation potential: Medium — SSVC exploitation status, reporter
    reputation scoring, and technical plausibility checks can be
    partially automated; final credibility determination typically
    requires human analyst review.
    """

    output_keys = {"report_credibility_verdict": str}
```

Key facts to carry into your implementation:

- **Shape**: Evaluator (returns a decision, no content artifact).
- **Input**: None from the blackboard — your backend queries its own data source.
- **Output**: Must write `report_credibility_verdict: str` on SUCCESS.
- **Default**: `AlmostAlwaysSucceed` (p = 0.90) → deterministic ceiling is `AlwaysSucceed`.

### 2. Implement the backend

```python
# myproject/behaviors/credibility.py
import py_trees
from py_trees.common import Access, Status


class ReputationServiceCredibilityEvaluator(py_trees.behaviour.Behaviour):
    """Credibility evaluator backed by an internal reporter reputation service.

    Blackboard contract (BT-18-001):
      Input keys:  (none)
      Output keys: report_credibility_verdict: str  (SUCCESS only)
    """

    def __init__(self, name: str) -> None:
        super().__init__(name=name)

    def setup(self, **kwargs) -> None:
        # Register every blackboard key this node writes before the first tick.
        self.blackboard = self.attach_blackboard_client(name=self.name)
        self.blackboard.register_key(
            "report_credibility_verdict", access=Access.WRITE
        )

    def update(self) -> Status:
        from myproject.services import reputation_service

        score = reputation_service.score_reporter(reporter_id=...)
        threshold = 0.5

        if score >= threshold:
            self.blackboard.report_credibility_verdict = (
                f"credible (score={score:.2f})"
            )
            return Status.SUCCESS
        return Status.FAILURE


def reputation_credibility_factory(name: str) -> py_trees.behaviour.Behaviour:
    return ReputationServiceCredibilityEvaluator(name)
```

### 3. Wire the backend

```python
# myproject/behaviors/bundles.py
from vultron.core.behaviors.call_out.bundles.validation import (
    ValidationCallOutBundle,
)
from myproject.behaviors.credibility import reputation_credibility_factory

MY_VALIDATION_BUNDLE = ValidationCallOutBundle(
    credibility_factory=reputation_credibility_factory,
)
```

### 4. Pass the bundle to the tree builder

```python
from vultron.core.behaviors.report.validate_tree import (
    create_validate_report_tree,
)
from myproject.behaviors.bundles import MY_VALIDATION_BUNDLE

tree = create_validate_report_tree(
    report_id=report.id_,
    offer_id=offer.id_,
    call_out=MY_VALIDATION_BUNDLE,
)
```

The reference implementation's validation workflow now calls
`ReputationServiceCredibilityEvaluator` instead of the stochastic fuzzer node.
The rest of the tree — state transitions, embargo checks, ledger writes — is
unchanged.

---

## Reference

- **[Capability Model](../topics/capability_model/index.md)** — the five capability shapes and the full catalog of known call-out points
- **[Reference Implementation Architecture](../topics/reference_architecture.md)** — the hexagonal boundary, inbox pipeline, and behavior-tree model
- **`vultron/core/behaviors/call_out/`** — `CallOutBackendFactory` Protocol, `AlwaysSucceed`/`AlwaysFail`, and all domain bundle dataclasses
- **`vultron/demo/fuzzer/`** — probabilistic fuzzer nodes (one per call-out point) and `STOCHASTIC` bundle singletons
- **ADR-0024** — capability shape taxonomy
- **ADR-0025** — call-out point abstraction layer and factory-injection pattern
