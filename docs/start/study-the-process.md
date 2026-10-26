---
description: >
  A reading path for people who study how coordinated vulnerability disclosure
  works and how to measure and improve it.
stakeholder_type: [process-researcher]
level: 100
page_type: routing
thread:
  - title: Start from the goals
    kind: chain
    members:
      - page: topics/background/what-is-vultron.md
        blurb: >-
          what the protocol is, and the research it formalizes.
      - page: topics/background/interoperability.md
        blurb: >-
          why independent organizations need shared meaning, not only shared formats.
      - page: topics/background/cvd_success.md
        blurb: >-
          the outcomes a case is trying to reach.
  - title: Work with the models
    kind: chain
    members:
      - page: topics/process_models/index.md
        blurb: >-
          the report, embargo and case state processes and how they interact.
      - page: topics/process_models/cs/cs_model.md
        blurb: >-
          the state space of every possible case history.
      - page: topics/measuring_cvd/index.md
        blurb: >-
          what a case records, and the desiderata and metrics drawn from it.
      - page: topics/other_uses/index.md
        blurb: >-
          applications of the model outside the protocol.
  - title: Go to the formal definition
    kind: set
    members:
      - page: reference/formal_protocol/index.md
        blurb: >-
          the Multi-Party Coordinated Vulnerability Disclosure (MPCVD) protocol as communicating hierarchical state machines.
      - page: reference/user_stories/index.md
        blurb: >-
          the requirements the protocol was designed against.
---

# You study how vulnerability disclosure works and want the models behind it

You work on Coordinated Vulnerability Disclosure (CVD) as a process: how cases unfold, how to measure them, and how to make the ecosystem healthier.
Vultron grew out of that research, and its protocol is built on formal models you can reuse on their own.
This page is a reading path through the models, the measurements, and the formal definition.
Each section builds on the ones before it; read a numbered list in order and a bulleted list in any order.

<!-- BEGIN GENERATED READING PATH — do not edit; change this page's thread: frontmatter, then run `uv run docs-site --write` -->

## Start from the goals

1. [What Is Vultron?](../topics/background/what-is-vultron.md) — what the protocol is, and the research it formalizes.
2. [The Need for Interoperability in Coordinated Vulnerability Disclosure](../topics/background/interoperability.md) — why independent organizations need shared meaning, not only shared formats.
3. [What Does *Success* Mean in CVD?](../topics/background/cvd_success.md) — the outcomes a case is trying to reach.

## Work with the models

1. [Vultron Process Models](../topics/process_models/index.md) — the report, embargo and case state processes and how they interact.
2. [CVD Case State Model](../topics/process_models/cs/cs_model.md) — the state space of every possible case history.
3. [Measuring CVD](../topics/measuring_cvd/index.md) — what a case records, and the desiderata and metrics drawn from it.
4. [Other Uses of the Vultron Case State Model](../topics/other_uses/index.md) — applications of the model outside the protocol.

## Go to the formal definition

- [A Formal Protocol Definition for MPCVD](../reference/formal_protocol/index.md) — the Multi-Party Coordinated Vulnerability Disclosure (MPCVD) protocol as communicating hierarchical state machines.
- [User Stories](../reference/user_stories/index.md) — the requirements the protocol was designed against.

<!-- END GENERATED READING PATH -->
