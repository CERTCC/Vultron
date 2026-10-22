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
      - page: tutorials/index.md
        blurb: >-
          the guided demos, and what each one shows.
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
      - page: reference/specs/index.md
        blurb: >-
          the machine-readable requirements the code is tested against.
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
This page is a reading path from running the demos to understanding why the codebase is built the way it is.
Each section builds on the ones before it; read a numbered list in order and a bulleted list in any order.

<!-- BEGIN GENERATED READING PATH — do not edit; change this page's thread: frontmatter, then run `uv run docs-site --write` -->

## Run it

1. [Vultron Protocol Tutorials](../tutorials/index.md) — the guided demos, and what each one shows.
2. [Tutorial: Running the Multi-Actor Container Demos](../tutorials/container_demos.md) — several actors coordinating a case on your machine.

## Understand how it is built

[Decisions](../adr/index.md) holds the architecture decision records behind the design.

1. [Reference Implementation Architecture](../topics/reference_architecture.md) — the layers, the ports and adapters, and the behavior trees that drive them.
2. [Specifications](../reference/specs/index.md) — the machine-readable requirements the code is tested against.

## Start contributing

[Contributing](../about/contributing.md) says how to propose a change and get it merged.
The [Vultron Developer Docs](https://github.com/CERTCC/Vultron/blob/main/docs/developer/index.md) cover setup, testing and day-to-day development tasks.

- [Working on This Implementation](../about/project_record.md) — the decision records, project requirements, and generated references, each reached from one page.

<!-- END GENERATED READING PATH -->
