---
description: >
  Wire a capability into the reference implementation, replacing a call-out
  stub with real backend logic.
stakeholder_type: [platform-developer, project-contributor]
level: 400
page_type: how-to
subject: implementation
---

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
filled by a **fuzzer node**: a stub that answers *yes* or *no* at random, based on a probability.
In production, you replace a fuzzer node with a **real capability backend** that applies actual business logic.

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
| Embargo management | `vultron/demo/fuzzer/embargo/` |
| CVE / Vulnerability ID assignment | `vultron/demo/fuzzer/report_management/assign_vul_id/` |
| Fix development | `vultron/demo/fuzzer/report_management/develop_fix.py` |
| Fix deployment | `vultron/demo/fuzzer/report_management/deploy_fix.py` |
| Exploit acquisition | `vultron/demo/fuzzer/report_management/acquire_exploit.py` |
| Publication | `vultron/demo/fuzzer/report_management/publication/` |

The [Capability Model](../topics/capability_model/index.md) page lists every
known integration point by domain and shape.

Each fuzzer node's docstring tells you the following:

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
      Output keys: report_credibility_verdict: str  (yes only)
    ...
    """

    contract = CallOutContract(outputs={"report_credibility_verdict": str})
```

The `contract` class attribute is the capability declaration.
It names the output keys a *yes* answer carries, and the refusal keys a *no* answer carries.
Every declaration has a refusal reason key; it is `call_out_refusal_reason` unless the capability names its own.
Your backend must honor this contract: a *yes* answer carries a value for every declared output key, and nothing else.
The seam refuses a *yes* that omits a declared key, so the omission is named at your backend and not at a later node.

---

## Step 2 — Implement a backend

### A backend answers yes, no or error

Every call-out backend gives one answer for each call: a fixed verdict and the data its capability declares for that verdict ([ADR-0183](../adr/0183-a-call-out-backend-answers-yes-no-or-error-and-the-seam-turns-the-answer-into-tree-behaviour.md)).

| Verdict | When to give it | Data it carries | What the tree sees |
|---|---|---|---|
| *yes* | The backend decided in favor, fetched the fact, made the artifact, or confirmed the side effect. | A value for every declared output key. | The seam writes the outputs, and the node succeeds. |
| *no* | The backend made a decision against the request. | A human-readable reason, and any declared refusal fields. | The seam writes the reason and fields to the refusal keys, and the node fails. |
| *error* | The backend could not decide or act. | Diagnostics for the logs. | The seam raises an error that names the node; the message is not judged and stays in holding to be tried again. |

Your backend never writes its declared keys itself and never chooses a `Status`.
The seam, `SynchronousCallOut`, is the only place that turns an answer into tree behavior.
The domain bundle puts every backend it hands out behind the seam, so you do not wire the seam yourself.

### When to answer error instead of no

Answer *no* only for a decision your backend made about this request.
A recorded *no* is permanent: the tree acts on it as a decision, and a later delivery of the same message does not ask again.

Answer *error* in each of these cases:

1. The service that makes the decision cannot be reached, or does not answer in time.
2. The backend's credential is rejected.
3. The backend started a side effect but cannot confirm that it happened.
4. Any other case where the backend cannot tell what the answer is.

An *error* leaves the message in holding.
The next delivery asks again, and its answer is the decision.
A backend that answers *no* for an outage turns that outage into a permanent refusal.

### Subclass `CallOutBackend`

Subclass `CallOutBackend`, set `contract`, and implement `answer()`.
`answer()` returns a `CallOutAnswer`, which you build with `CallOutAnswer.yes()`, `CallOutAnswer.no()` or `CallOutAnswer.error()`.
Do not override `update()`: the base class holds your answer for the seam.

```python
from typing import ClassVar

from vultron.core.behaviors.call_out import (
    CallOutAnswer,
    CallOutBackend,
    CallOutContract,
)


class MyCredibilityEvaluator(CallOutBackend):
    """Real credibility evaluator backed by a reputation scoring service.

    Blackboard contract (BT-18-001):
      Input keys:  (none — queries reputation service using DataLayer context)
      Output keys: report_credibility_verdict: str  (yes only)
      Refusal keys: call_out_refusal_reason: str  (no only)
    """

    contract: ClassVar[CallOutContract] = CallOutContract(
        outputs={"report_credibility_verdict": str}
    )

    def answer(self) -> CallOutAnswer:
        try:
            verdict = my_reputation_service.evaluate(...)
        except ConnectionError as exc:
            # The service is unreachable: no decision was made.
            return CallOutAnswer.error(f"reputation service: {exc}")
        if verdict.credible:
            return CallOutAnswer.yes(
                {"report_credibility_verdict": verdict.summary}
            )
        return CallOutAnswer.no(f"reporter not credible: {verdict.summary}")


# This class is the CallOutBackendFactory: it takes the node name.
my_credibility_factory = MyCredibilityEvaluator
```

A backend that reads its own input keys or needs the actor's DataLayer can attach a blackboard client or combine `CallOutBackend` with a ports base class.
It still answers through `answer()`.

### A binary backend

When the call-out point's contract declares no output keys, a *yes* carries no data:

```python
class _CredibilityCheck(CallOutBackend):
    """Backend that consults a reputation service. Binary answer."""

    def answer(self) -> CallOutAnswer:
        score = my_reputation_service.score_reporter(reporter_id=...)
        if score >= 0.5:
            return CallOutAnswer.yes()
        return CallOutAnswer.no(f"reputation score {score:.2f} is below 0.5")
```

### The `CallOutBackendFactory` Protocol

A backend factory is any callable that satisfies the `CallOutBackendFactory` Protocol:

```python
from vultron.core.behaviors.call_out import CallOutBackendFactory

class CallOutBackendFactory(Protocol):
    def __call__(self, name: str) -> py_trees.behaviour.Behaviour: ...
```

The factory accepts a single `name: str` argument (the BT node's display name) and returns a `CallOutBackend`.
A `CallOutBackend` subclass is itself a valid factory, and so is a plain function or a lambda that returns one.
The seam refuses a factory product that is not a `CallOutBackend`, when the tree is built.

### Answer within the time budget

Your backend answers in the same tick it is called, and it must also answer fast.
Each actor sets a call-out time budget, `call_out_time_budget` in the `actor:` section of its configuration, with a default of 5 seconds.
The budget is local to the actor and no peer sees it, so two deployments may set different values.

The seam measures how long your backend took to answer.
When it took longer than the budget, the seam discards the answer, whatever its verdict, and raises `CallOutBudgetExceededError`.
The error names the node and the budget, and the bridge reports it as an internal error, so the message stays in holding to be tried again.

The seam does not interrupt your backend: it runs on the tree's own thread, so the seam can only measure the time after your backend returns.
A slow backend still holds the worker for as long as it takes, on every call.
So never make an unbounded blocking call, such as a network request with no timeout, in your backend.
Give every outside call a timeout shorter than the budget, and answer *error* when it expires.

Work that cannot finish within the budget is not a call-out point:

- A question that needs another actor in the case to decide is a protocol ask: the tree sends the request, ends, and acts on the reply when it arrives ([ADR-0080](../adr/0080-protocol-asks-not-suspended-behaviors.md)).
- Work that runs for a long time, or watches for a condition, is a call-in: an outside process does the work and calls Vultron when it has a result (see [the Sentinel call-in pattern](../topics/capability_model/index.md#the-sentinel-call-in-pattern)).

### What the seam refuses

The seam raises `CallOutContractError`, which the bridge reports as an internal error, when a backend does any of the following:

- returns `RUNNING` (BT-18-011): the reference implementation has nowhere to suspend a tick (ADR-0080);
- gives something that is not a `CallOutAnswer`;
- gives a *yes* that omits a declared output key, adds an undeclared one, or has a value of the wrong type;
- gives a *no* with a refusal field that its contract does not declare;
- is ticked outside the seam, for example placed in a tree by hand.

### An Actuator acts on one target and is safe to repeat

An Actuator causes a side effect in an external system: it submits an advisory, sends a notification, or writes a record.
Three rules apply to every Actuator backend ([ADR-0183](../adr/0183-a-call-out-backend-answers-yes-no-or-error-and-the-seam-turns-the-answer-into-tree-behaviour.md)).

1. **One target per call.**
   Each call acts on exactly one target.
   A tree that acts on several targets makes one call for each target and sees one verdict for each call.
2. **Safe to repeat.**
   Each call carries an idempotency id that the tree derives from the act and the target.
   When a message is re-run from holding, every call gets the same id again.
   Key your side effect on that id: when the id is one you have already acted on, do not act again, and answer *yes*.
3. **Answer error when you cannot confirm.**
   A side effect that you started but cannot confirm is *error*, not *no*.
   A rejected credential is also *error*, never *no*.
   Where your credentials live and which systems your Actuator may reach are a deployment matter, outside the protocol.

Subclass `ActuatorBackend` and implement `act()`, not `answer()`.
`act()` receives an `ActuationRequest` with the call's `target` and `idempotency_id`:

```python
from vultron.core.behaviors.call_out import (
    ActuationRequest,
    ActuatorBackend,
    CallOutAnswer,
)


class MyAdvisorySubmitter(ActuatorBackend):
    """Submits a finished advisory to an advisory platform."""

    def act(self, request: ActuationRequest) -> CallOutAnswer:
        try:
            receipt = my_advisory_platform.submit(
                advisory=request.target,
                idempotency_key=request.idempotency_id,
            )
        except my_advisory_platform.CredentialRejected as exc:
            return CallOutAnswer.error(f"advisory platform: {exc}")
        except my_advisory_platform.Unavailable as exc:
            return CallOutAnswer.error(f"advisory platform: {exc}")
        if not receipt.confirmed:
            return CallOutAnswer.error("advisory platform: no confirmation")
        # A receipt for a key the platform already holds is a yes as well.
        return CallOutAnswer.yes()
```

An Actuator declares no output keys: its `contract` is an `ActuatorContract`, and the class refuses one that declares outputs.
The tree places each Actuator on its target with `actuator_call()`, so you do not choose the target yourself.
The seam refuses an Actuator that is placed without a target, and a backend placed as an Actuator that is not an `ActuatorBackend`.

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
      Output keys: report_credibility_verdict: str  (yes only)

    Input category: Human decision.

    Success probability: 0.90 (AlmostAlwaysSucceed).

    Automation potential: Medium — SSVC exploitation status, reporter
    reputation scoring, and technical plausibility checks can be
    partially automated; final credibility determination typically
    requires human analyst review.
    """

    contract = CallOutContract(outputs={"report_credibility_verdict": str})
```

Key facts to carry into your implementation:

- **Shape**: Evaluator (returns a decision, no content artifact).
- **Input**: None from the blackboard — your backend queries its own data source.
- **Output**: A *yes* carries `report_credibility_verdict: str`.
- **Default**: `AlmostAlwaysSucceed` (p = 0.90) → deterministic ceiling is `AlwaysSucceed`.

### 2. Implement the backend

```python
# myproject/behaviors/credibility.py
from typing import ClassVar

from vultron.core.behaviors.call_out import (
    CallOutAnswer,
    CallOutBackend,
    CallOutContract,
)


class ReputationServiceCredibilityEvaluator(CallOutBackend):
    """Credibility evaluator backed by an internal reporter reputation service.

    Blackboard contract (BT-18-001):
      Input keys:  (none)
      Output keys: report_credibility_verdict: str  (yes only)
      Refusal keys: call_out_refusal_reason: str  (no only)
    """

    contract: ClassVar[CallOutContract] = CallOutContract(
        outputs={"report_credibility_verdict": str}
    )

    def answer(self) -> CallOutAnswer:
        from myproject.services import reputation_service

        try:
            score = reputation_service.score_reporter(reporter_id=...)
        except reputation_service.Unavailable as exc:
            return CallOutAnswer.error(f"reputation service: {exc}")

        if score >= 0.5:
            return CallOutAnswer.yes(
                {"report_credibility_verdict": f"credible (score={score:.2f})"}
            )
        return CallOutAnswer.no(f"reputation score {score:.2f} is below 0.5")


def reputation_credibility_factory(name: str) -> CallOutBackend:
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

- **[Capability Model](../topics/capability_model/index.md)** — the four capability shapes and the full catalog of known call-out points
- **[Reference Implementation Architecture](../topics/reference_architecture.md)** — the hexagonal boundary, inbox pipeline, and behavior-tree model
- **`vultron/core/behaviors/call_out/`** — `CallOutBackend`, `CallOutAnswer`, `CallOutContract`, the `SynchronousCallOut` seam and its time-bounded form `TimeBoundedCallOut`, the `CallOutBackendFactory` Protocol, `AlwaysSucceed`/`AlwaysFail`, and all domain bundle dataclasses
- **`vultron/demo/fuzzer/`** — probabilistic fuzzer nodes (one per call-out point) and `STOCHASTIC` bundle singletons
- **ADR-0024** — capability shape taxonomy
- **ADR-0025** — call-out point abstraction layer and factory-injection pattern
- **[ADR-0183](../adr/0183-a-call-out-backend-answers-yes-no-or-error-and-the-seam-turns-the-answer-into-tree-behaviour.md)** — the *yes* / *no* / *error* answer and the seam that interprets it

{% include-markdown "../start/_paths/connect-your-tracker/howto__wire_capability.md" %}

{% include-markdown "../start/_paths/contribute/howto__wire_capability.md" %}
