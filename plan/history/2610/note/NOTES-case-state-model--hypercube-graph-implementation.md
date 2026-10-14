---
source: NOTES-case-state-model--hypercube-graph-implementation
timestamp: '2026-10-12T19:32:55.788124+00:00'
title: Hypercube Graph Implementation
type: note
---

**Archived:** 2026-10-12
**Reason:** reference material; the module and its ADR-0060 status are documented in docs/ and the module docstrings
**Superseded by:** vultron/core/case_states/hypercube.py; ADR-0060; docs/topics/measuring_cvd/

---

## Hypercube Graph Implementation

`vultron/core/case_states/hypercube.py` implements the `CVDmodel` class, which:

- Builds the 32-state DAG (directed acyclic graph) of all 58 valid
  transitions using NetworkX.
- Implements random walks through the state space for simulation.
- Provides scoring functions to measure the "quality" of a CVD case history.
- Computes statistics over ensembles of histories.

The `CVDmodel` can be used to:

1. Generate the Hasse diagram of case states.
2. Compute all valid histories (orderings of V, F, D, P, X, A events).
3. Score a specific history against desirable orderings.
4. Benchmark a case against random walk baselines.

**Dependencies**: `networkx`, `numpy`, `pandas`.

**Status (ADR-0060)**: `vultron/core/case_states/` is a **reference model, not a
protocol path**. It is the specification of record for the CS rules and the
oracle the `cs_invariants.py` tests compare against, but new code MUST NOT
import `case_states.validations` — use `vultron/core/states/cs_invariants.py`.
See "Rule Inventory and Legacy Module Status" below.
