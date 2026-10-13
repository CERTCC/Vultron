---
source: NOTES-case-state-model--measuring-cvd-process-quality
timestamp: '2026-10-12T19:32:56.655426+00:00'
title: Measuring CVD Process Quality
type: note
---

**Archived:** 2026-10-12
**Reason:** reference pointer plus an untracked future idea; not guidance
**Superseded by:** docs/topics/measuring_cvd/

---

## Measuring CVD Process Quality

Based on the research paper [*A State-Based Model for Multi-Party CVD*](
https://www.sei.cmu.edu/documents/1952/2021_003_001_737890.pdf), the
`hypercube.py` module implements a framework for measuring the quality of a
CVD process by analyzing the order in which case state events occur.

Documentation in `docs/topics/measuring_cvd/` covers:

- `benchmarking.md` / `benchmarking_mpcvd.md` — how to compare a case history against baselines
- `desirable_histories.md` — which event orderings are considered "good"
- `discriminating_skill_and_luck.md` — statistical methods for separating skill from chance
- `possible_histories.md` — enumeration of all valid event sequences
- `random_walk.md` — using random walks as a null hypothesis baseline
- `reasoning_over_histories.md` — how to draw conclusions from history analysis

**Future application**: Applying these scoring techniques to `VulnerabilityCase`
objects and their event history logs would provide quantitative quality metrics
for the CVD process. This is not high priority for the prototype but would be
a valuable analytical capability.

**Prerequisite**: The `VulnerabilityCase` object's activity/event history
needs to be in a format that `hypercube.py` can consume. This likely requires
a translation layer from ActivityStreams history to the `(V, F, D, P, X, A)`
event sequence format expected by `CVDmodel`.
