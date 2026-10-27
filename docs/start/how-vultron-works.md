---
description: >
  A reading path through what a Vultron case is, who takes part in it, and the
  process models that move it from report to publication.
stakeholder_type: ALL
level: 100
page_type: routing
thread:
  - title: Know what kind of thing Vultron is
    kind: chain
    stopping_point: true
    members:
      - page: topics/background/what-is-vultron.md
        blurb: >-
          a protocol your systems speak, not a platform you join, and what it leaves to you.
      - page: topics/background/cvd-coordination-problem.md
        blurb: >-
          why coordinating a case across organizations is hard today.
  - title: Follow a case from report to publication
    kind: chain
    members:
      - page: topics/case_lifecycle/a_case_under_vultron.md
        blurb: >-
          a case from a participant's seat: who owns it, and what each participant sees and controls.
      - page: topics/process_models/index.md
        blurb: >-
          the report, embargo and case state processes that move every case.
      - page: topics/capability_model/index.md
        blurb: >-
          the decisions the protocol leaves to each organization, and where its own judgment plugs in.
  - title: Look up a term
    kind: set
    members:
      - page: reference/glossary.md
        blurb: >-
          every term the rest of the site uses, defined once.
      - page: reference/vultron-taxonomy.md
        blurb: >-
          the distinct concepts that together make up Vultron, and how they relate.
---

# You want to understand how a vulnerability case runs under Vultron

Every other part of this site assumes the ideas on this one: what a Coordinated Vulnerability Disclosure (CVD) case is, who takes part in it, and the processes that move it from a first report to publication.
Read this path first if you are deciding which of the other tabs you need, or if you need the shared vocabulary before you go deeper.
Each section builds on the ones before it; read a numbered list in order and a bulleted list in any order.

{% include-markdown "../includes/lookup_link.md" %}

{% include-markdown "./_paths/how-vultron-works/start__how-vultron-works.md" %}

<!-- BEGIN GENERATED READING PATH — do not edit; change this page's thread: frontmatter, then run `uv run docs-site --write` -->

## Know what kind of thing Vultron is

1. [What Is Vultron?](../topics/background/what-is-vultron.md) — a protocol your systems speak, not a platform you join, and what it leaves to you.
2. [CVD as a Coordination Problem](../topics/background/cvd-coordination-problem.md) — why coordinating a case across organizations is hard today.

You can stop here if this section answered your question.

## Follow a case from report to publication

1. [A Case Under Vultron](../topics/case_lifecycle/a_case_under_vultron.md) — a case from a participant's seat: who owns it, and what each participant sees and controls.
2. [Vultron Process Models](../topics/process_models/index.md) — the report, embargo and case state processes that move every case.
3. [Capability Model](../topics/capability_model/index.md) — the decisions the protocol leaves to each organization, and where its own judgment plugs in.

## Look up a term

- [Glossary — Vultron](../reference/glossary.md) — every term the rest of the site uses, defined once.
- [Vultron Concept Taxonomy](../reference/vultron-taxonomy.md) — the distinct concepts that together make up Vultron, and how they relate.

<!-- END GENERATED READING PATH -->

When you know what you came to do, the other tabs each open on a path of their own:
[coordinating cases](coordinate-cases.md),
[implementing the protocol](connect-your-tracker.md),
[working on the reference implementation](contribute.md), and
[studying the process](study-the-process.md).
