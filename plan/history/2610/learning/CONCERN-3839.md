---
source: CONCERN-3839
timestamp: '2026-10-02T17:27:28.739655+00:00'
title: 'docs: benchmarking_mpcvd.md gives MPCVD dimensionality as 5 per vendor-product
  pair, while the CS model has six substates'
type: learning
---

## Observation

`docs/topics/measuring_cvd/benchmarking_mpcvd.md` § "Dimensionality of an MPCVD Case" states

$$D_{max} = 5 * N_{vprod}$$

and, until #3838, its next tip said the goal was to reduce a case "to the 5 dimensions of a single vendor CVD case". The Case State (CS) model those pages build on has **six** substates (`vfdpxa`: three per-vendor fix-path bits and three shared public-state bits), as `cs/cs_model.md` and spec §8 define them. Either the constant is a carry-over error from the 2021 report, or it encodes a reasoning (for example, that one of the six dimensions does not multiply per vendor-product pair) that the page no longer states.

PR #3838 removed the number from the prose parenthetical because the sentence now links to `cs_model.md`, where a reader would see six. It left the formula in place because the claim could not be verified against its authority (the report) in that session (DF-10-001)

## Why it matters

The page is 500-level research addressed to `process-researcher`, and a wrong or unexplained constant in the one formula it introduces undermines the dimensionality argument the rest of the page rests on.

## Suggested resolution

Check the constant against *A State-Based Model for Multi-Party Coordinated Vulnerability Disclosure (MPCVD)* (Householder and Spring, 2021). Then either correct the formula, or add one sentence stating why the per-pair dimensionality is five rather than six.

Governing specs: DF-10-001, DF-09-005

Found while working #3626 (PR #3838).

**Resolved**: 2026-10-02 — the constant 5 is correct: the causal constraints D ⇒ F ⇒ V and X ⇒ P ⇒ V collapse the six CS substates into five dimensions (maintainer). Captured in docs/topics/measuring_cvd/benchmarking_mpcvd.md.
Docs PR: <https://github.com/CERTCC/Vultron/pull/4174>.
