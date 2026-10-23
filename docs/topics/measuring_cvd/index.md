---
stakeholder_type: [process-researcher]
level: 200
page_type: routing
contents: generated
---

# Measuring CVD

Coordinated Vulnerability Disclosure (CVD) is the accepted response to vulnerable software.
But few measures exist to show how well CVD works.
This section describes what a Vultron case records.
The section then shows how to turn that record into desiderata and metrics.
Desiderata are the orders of events that a case should achieve, and metrics are measurements on cases.
The pages are research material for people who study the CVD process, and no page in this section is normative.

Vultron has modeled Multi-Party CVD (MPCVD) from the start.
MPCVD is the general case.
Two-party CVD, with one reporter and one vendor, is a special case of the same model.
The original model used some simple assumptions.
The removal of these assumptions is continuous improvement, not a late addition.

Every main page in this section uses the difference between two kinds of state:

- **Participant-agnostic state** belongs to the case. The case has one copy. Examples are the public state of the vul and the embargo state of the case. An event in participant-agnostic state, such as public awareness, occurs at most once in a case.
- **Participant-specific state** belongs to one participant. Each participant has its own copy. Examples are the fix state of each vendor and the deployment state of each deployer. An event in participant-specific state, such as fix readiness, can occur once for each participant.

Each main page tells how its measures change in a two-party case.
A measure can stay the same, become simpler, or not apply.

The [Foundations](foundations/index.md) group keeps the first-principles model from the report [A State-Based Model for Multi-Party Coordinated Vulnerability Disclosure (MPCVD)](https://doi.org/10.1184/R1/16416771){:target="_blank"} by Allen Householder and Jonathan Spring.
The Foundations model finds every possible history of a case with six events.
The model then ranks the histories by twelve desired outcomes.
Last, the model compares the observed histories against chance, and uses the difference as a measure of skill.
[What Does *Success* Mean in CVD?](../background/cvd_success.md) gives the twelve outcomes in plain words.
Start with that page if the state notation is new to you.

## Pages in this section

The main pages come first, in the order in which each page builds on the page before it.
The Foundations group comes after the main pages.

<!-- BEGIN GENERATED SECTION CONTENTS — do not edit; change the mkdocs.yml nav or a listed page's description: frontmatter, then run `uv run docs-site --write` -->

- [What a Case Records](what_a_case_records.md) — The events that a Vultron case records, which events belong to the case or to one participant, the two times on each entry, and the data gaps.
- [Desiderata from the Process Models](process_model_desiderata.md) — Ordering preferences beyond the original twelve, distilled from the report, embargo, consent, and multi-party process models.
- [Timing Metrics Within a Case](timing_metrics.md) — Intervals, dwell times, margins, and spreads that the case ledger's timestamps make measurable within one case.
- [Open Questions](open_questions.md) — What measuring CVD still leaves open, from transition probabilities and the order of histories to fairness across vendors.
- [Foundations](foundations/index.md) — The first-principles model of the original research: six events, the histories they allow, and a skill measure against chance.

<!-- END GENERATED SECTION CONTENTS -->

## Where the section connects

At its end, the report discusses how vendors, system owners, coordinators, and governments can use these measures.
That discussion is on [CVD Roles and Their Influence](../other_uses/roles_influence.md), in the [Other Uses](../other_uses/index.md) section.
The discussion is in Other Uses because it is about who uses the model, not about measurement.
A CVD program owner can measure their own cases without the derivation.
[How to Measure Your CVD Program](../../howto/measure_your_cvd_program.md) gives the steps.
