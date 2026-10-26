---
description: >
  A reading path for people who want to work on the Vultron reference
  implementation.
stakeholder_type: [project-contributor]
level: 100
page_type: routing
thread:
  - title: Run it
    kind: chain
    members:
      - page: tutorials/receive_report_demo.md
        blurb: >-
          the demo environment, and one actor working an incoming report.
      - page: tutorials/container_demos.md
        blurb: >-
          several actors coordinating a case on your machine.
  - title: Understand how it is built
    kind: chain
    framing: >-
      [Decisions](../adr/index.md) holds the architecture decision records behind the design.
    members:
      - page: topics/reference_architecture.md
        blurb: >-
          the layers, the ports and adapters, and the behavior trees that drive them.
      - page: reference/specs/architecture.md
        blurb: >-
          the requirements on how this implementation is built, which other implementations need not follow.
      - page: howto/wire_capability.md
        blurb: >-
          replacing a stub decision with your own service.
  - title: Start contributing
    kind: set
    framing: |-
      [Contributing](../about/contributing.md) says how to propose a change and get it merged.
      The [Vultron Developer Docs](https://github.com/CERTCC/Vultron/blob/main/docs/developer/index.md) cover setup, testing and day-to-day development tasks.
    members:
      - page: about/project_record.md
        blurb: >-
          the decision records, project requirements, and generated references, each reached from one page.
---

# You want to work on the Vultron reference implementation

You want to run, change, or extend the Python code in this repository.
This tab holds CERT/CC's reference implementation of the protocol: its demos, its architecture, and the requirements on how it is built.
What every implementation must do is on [Implement the Protocol](connect-your-tracker.md); this tab is about one implementation of it.
This page is a reading path from running the demos to understanding why the codebase is built the way it is.
Each section builds on the ones before it; read a numbered list in order and a bulleted list in any order.

[Run the demos](../tutorials/container_demos.md){ .md-button .md-button--primary }
[Read the architecture](../topics/reference_architecture.md){ .md-button }

{% include-markdown "./_paths/contribute/start__contribute.md" %}

<!-- BEGIN GENERATED READING PATH — do not edit; change this page's thread: frontmatter, then run `uv run docs-site --write` -->

## Run it

1. [Tutorial: Run the Receive-Report Demo](../tutorials/receive_report_demo.md) — the demo environment, and one actor working an incoming report.
2. [Tutorial: Running the Multi-Actor Container Demos](../tutorials/container_demos.md) — several actors coordinating a case on your machine.

## Understand how it is built

[Decisions](../adr/index.md) holds the architecture decision records behind the design.

1. [Reference Implementation Architecture](../topics/reference_architecture.md) — the layers, the ports and adapters, and the behavior trees that drive them.
2. [Architecture Specifications](../reference/specs/architecture.md) — the requirements on how this implementation is built, which other implementations need not follow.
3. [Wiring a Capability into the Reference Implementation](../howto/wire_capability.md) — replacing a stub decision with your own service.

## Start contributing

[Contributing](../about/contributing.md) says how to propose a change and get it merged.
The [Vultron Developer Docs](https://github.com/CERTCC/Vultron/blob/main/docs/developer/index.md) cover setup, testing and day-to-day development tasks.

- [Working on This Implementation](../about/project_record.md) — the decision records, project requirements, and generated references, each reached from one page.

<!-- END GENERATED READING PATH -->
