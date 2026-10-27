---
description: >
  A reading path for people who handle vulnerability reports and coordinate
  disclosure cases with other organizations.
stakeholder_type: [cvd-practitioner]
level: 100
page_type: routing
subject: neutral
thread:
  - title: Decide whether it solves a problem you have
    kind: chain
    stopping_point: true
    members:
      - page: topics/background/what-is-vultron.md
        blurb: >-
          what kind of thing Vultron is, and what it leaves to your organization.
      - page: topics/background/cvd_success.md
        blurb: >-
          the outcomes a case is trying to reach, stated independently of any tool.
      - page: reference/glossary.md#cvd-roles-and-participants
        label: CVD Roles and Participants
        blurb: >-
          the vocabulary the rest of the site uses for participants, reports and cases.
  - title: See how a case moves
    kind: chain
    members:
      - page: topics/case_lifecycle/a_case_under_vultron.md
        blurb: >-
          the case from your seat: who owns it, what you see and control, and what an embargo invitation asks of you.
      - page: topics/process_models/index.md
        blurb: >-
          the three processes a case runs: report handling, embargo, and case state.
      - page: topics/process_models/em/principles.md
        blurb: >-
          what an embargo is for and what it asks of each participant.
      - page: topics/process_models/em/negotiating.md
        blurb: >-
          how participants propose, accept and revise an embargo.
      - page: topics/process_models/em/working_with_others.md
        blurb: >-
          what happens when another party joins mid-case.
      - page: topics/process_models/em/early_termination.md
        blurb: >-
          when and how an embargo ends before its planned date.
  - title: Prepare your program
    kind: chain
    members:
      - page: howto/decide_who_owns_a_case.md
        blurb: >-
          select a path for a vulnerability: send a report, report to yourself and coordinate the case, or transfer a case.
      - page: howto/adopt_vultron.md
        blurb: >-
          name your roles, choose a conformance claim, map your intake to the report states, publish your embargo defaults, and decide which judgment calls stay yours.
  - title: Map it onto what you already do
    kind: set
    members:
      - page: reference/iso_crosswalks/index.md
        blurb: >-
          how the protocol lines up with the International Organization for Standardization (ISO) standards for vulnerability handling, disclosure, and multi-party coordination.
      - page: reference/user_stories/index.md
        blurb: >-
          the practitioner needs the protocol was designed against.
      - page: reference/ssvc_crosswalk.md
        blurb: >-
          where a Stakeholder-Specific Vulnerability Categorization (SSVC) decision enters a case.
      - page: topics/capability_model/index.md
        blurb: >-
          every decision Vultron leaves to your organization, and where your answer plugs in.
      - page: howto/measure_your_cvd_program.md
        blurb: >-
          score your own cases against the chance baseline, and read the result as a skill indicator you can act on.
  - title: Watch a case run
    kind: set
    members:
      - page: tutorials/receive_report_demo.md
        blurb: >-
          a vendor accepting, holding, or rejecting an incoming report.
      - page: tutorials/rv-demo.md
        blurb: >-
          the Reporter and Vendor (`rv`) scenario, working a case through to publication.
---

# You handle vulnerability reports and coordinate cases with other organizations

You receive vulnerability reports, work them with vendors and coordinators, and publish when the case is ready.
You might be a security researcher, a vendor's product security team, or a coordinator at a national Computer Security Incident Response Team (CSIRT).
You might also lead a Product Security Incident Response Team (PSIRT) or a CSIRT and need to decide whether to adopt Vultron; the first section below is written for that decision, and *Prepare your program* covers what adopting it asks of you.
This tab holds what adopting Vultron asks of a disclosure program, and how it lines up with the standards you already follow.
This page is a reading path through the parts of this site that describe how a Coordinated Vulnerability Disclosure (CVD) case works under Vultron, on this tab and the others.
Each section builds on the ones before it; read a numbered list in order and a bulleted list in any order.

{% include-markdown "../includes/lookup_link.md" %}

[Read What Is Vultron?](../topics/background/what-is-vultron.md){ .md-button .md-button--primary }
[Adopt Vultron in your program](../howto/adopt_vultron.md){ .md-button }

{% include-markdown "./_paths/coordinate-cases/start__coordinate-cases.md" %}

<!-- BEGIN GENERATED READING PATH — do not edit; change this page's thread: frontmatter, then run `uv run docs-site --write` -->

## Decide whether it solves a problem you have

1. [What Is Vultron?](../topics/background/what-is-vultron.md) — what kind of thing Vultron is, and what it leaves to your organization.
2. [What Does *Success* Mean in CVD?](../topics/background/cvd_success.md) — the outcomes a case is trying to reach, stated independently of any tool.
3. [CVD Roles and Participants](../reference/glossary.md#cvd-roles-and-participants) — the vocabulary the rest of the site uses for participants, reports and cases.

You can stop here if this section answered your question.

## See how a case moves

1. [A Case Under Vultron](../topics/case_lifecycle/a_case_under_vultron.md) — the case from your seat: who owns it, what you see and control, and what an embargo invitation asks of you.
2. [Vultron Process Models](../topics/process_models/index.md) — the three processes a case runs: report handling, embargo, and case state.
3. [Embargo Principles](../topics/process_models/em/principles.md) — what an embargo is for and what it asks of each participant.
4. [Negotiating Embargoes](../topics/process_models/em/negotiating.md) — how participants propose, accept and revise an embargo.
5. [Adding Participants to an Embargoed Case](../topics/process_models/em/working_with_others.md) — what happens when another party joins mid-case.
6. [Early Termination](../topics/process_models/em/early_termination.md) — when and how an embargo ends before its planned date.

## Prepare your program

1. [How to Select the Case Owner](../howto/decide_who_owns_a_case.md) — select a path for a vulnerability: send a report, report to yourself and coordinate the case, or transfer a case.
2. [How to Adopt Vultron in Your CVD Program](../howto/adopt_vultron.md) — name your roles, choose a conformance claim, map your intake to the report states, publish your embargo defaults, and decide which judgment calls stay yours.

## Map it onto what you already do

- [Standards Crosswalks](../reference/iso_crosswalks/index.md) — how the protocol lines up with the International Organization for Standardization (ISO) standards for vulnerability handling, disclosure, and multi-party coordination.
- [User Stories](../reference/user_stories/index.md) — the practitioner needs the protocol was designed against.
- [Interactions Between the Vultron Protocol and SSVC](../reference/ssvc_crosswalk.md) — where a Stakeholder-Specific Vulnerability Categorization (SSVC) decision enters a case.
- [Capability Model](../topics/capability_model/index.md) — every decision Vultron leaves to your organization, and where your answer plugs in.
- [How to Measure Your CVD Program](../howto/measure_your_cvd_program.md) — score your own cases against the chance baseline, and read the result as a skill indicator you can act on.

## Watch a case run

- [Tutorial: Run the Receive-Report Demo](../tutorials/receive_report_demo.md) — a vendor accepting, holding, or rejecting an incoming report.
- [Tutorial: Run the `rv` Demo](../tutorials/rv-demo.md) — the Reporter and Vendor (`rv`) scenario, working a case through to publication.

<!-- END GENERATED READING PATH -->
