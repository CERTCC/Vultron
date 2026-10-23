---
stakeholder_type: [process-researcher]
level: 200
page_type: routing
contents: generated
---

# Measuring CVD

Coordinated Vulnerability Disclosure (CVD) is the consensus response to the persistent fact of vulnerable software, yet few performance indicators have been proposed to measure how well it works.
This section describes what a Vultron case records, and how that record becomes desiderata, the orderings a case should achieve, and metrics on cases.
The pages are research material for people who study the CVD process, and none of them is normative.

Vultron has modeled Multi-Party CVD (MPCVD) from the start.
MPCVD is the general case, and two-party CVD, with one reporter and one vendor, is a special case of the same model.
The original model made simplifying assumptions, and relaxing them is ongoing refinement, not a late addition.

Every page in the main part of this section builds on one split.
**Participant-agnostic state**, such as whether the vul is public and the case's embargo, belongs to the case and happens once in it.
**Participant-specific state**, such as each vendor's fix and each deployer's deployment, belongs to one participant and can happen once for each.
Each page notes how its measures carry over to the two-party case, collapse in it, or disappear.

The [Foundations](foundations/index.md) group keeps the first-principles derivation from the report [A State-Based Model for Multi-Party Coordinated Vulnerability Disclosure (MPCVD)](https://doi.org/10.1184/R1/16416771){:target="_blank"} by Allen Householder and Jonathan Spring.
It derives every possible history of a six-event case, orders those histories by twelve desired outcomes, and turns the difference between chance and observation into a measure of skill.
The twelve outcomes are stated in plain terms on [What Does *Success* Mean in CVD?](../background/cvd_success.md), which is the place to start if the state notation is new to you.

## Pages in this section

The main pages come first, in the order they build on one another, and the Foundations group follows.

<!-- BEGIN GENERATED SECTION CONTENTS — do not edit; change the mkdocs.yml nav or a listed page's description: frontmatter, then run `uv run docs-site --write` -->

- [What a Case Records](what_a_case_records.md) — The events a Vultron case records, whether each belongs to the case or to one participant, the two clocks on each record, and the gaps.
- [Desiderata from the Process Models](process_model_desiderata.md) — Ordering preferences beyond the original twelve, distilled from the report, embargo, consent, and multi-party process models.
- [Timing Metrics Within a Case](timing_metrics.md) — Intervals, dwell times, margins, and spreads that the case ledger's timestamps make measurable within one case.
- [Open Questions](open_questions.md) — What measuring CVD still leaves open, from transition probabilities and the order of histories to fairness across vendors.
- [Foundations](foundations/index.md) — The first-principles model of the original research: six events, the histories they allow, and a skill measure against chance.

<!-- END GENERATED SECTION CONTENTS -->

## Where the section connects

The report closes with reflections on how vendors, system owners, coordinators, and governments could each use these indicators.
Those reflections are on [CVD Roles and Their Influence](../other_uses/roles_influence.md), in the [Other Uses](../other_uses/index.md) section, because they are about who acts on the model rather than about measuring it.
A CVD program owner who wants to apply the measure to their own cases, without the derivation, can follow [How to Measure Your CVD Program](../../howto/measure_your_cvd_program.md).
