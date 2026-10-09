---
stakeholder_type: [process-researcher]
level: 200
contents: generated
---

# Measuring CVD

Coordinated Vulnerability Disclosure (CVD) is the consensus response to the persistent fact of vulnerable software, yet few performance indicators have been proposed to measure how well it works at the broadest scales.
This section fills that gap.
It derives every possible history a CVD case can have from the [Case State (CS) model](../process_models/cs/index.md), orders those histories by a set of desired outcomes, computes how often each outcome would occur by chance, and turns the difference between chance and observation into a measure of skill.
The pages are research material for people who study the CVD process, and none of them is normative.

The section is derived from the report [A State-Based Model for Multi-Party Coordinated Vulnerability Disclosure (MPCVD)](https://doi.org/10.1184/R1/16416771){:target="_blank"} by Allen Householder and Jonathan Spring.
The twelve desired outcomes it measures against are stated in plain terms on [What Does *Success* Mean in CVD?](../background/cvd_success.md), which is the place to start if the state notation is new to you.

## Pages in this section

The pages build on one another in the order shown.
The first four construct the model, the next two measure against it, and the remaining pages apply the measure, extend the model, or discuss its limits.

<!-- BEGIN GENERATED SECTION CONTENTS — do not edit; change the mkdocs.yml nav or a listed page's description: frontmatter, then run `uv run docs-site --write` -->

- [Possible Histories](possible_histories.md) — The 70 histories a case can have, derived from the six CS events and their ordering constraints.
- [Desirable Histories](desirable_histories.md) — The twelve desired orderings and the partial order they induce over the histories.
- [Random Walks](random_walk.md) — A baseline in which every allowed transition is equally likely, from the principle of indifference.
- [Reasoning Over Histories](reasoning_over_histories.md) — How often each history and each desired ordering occurs under that baseline.
- [Discriminating Skill from Luck](discriminating_skill_and_luck.md) — The skill coefficient, which normalizes an observed frequency against the baseline.
- [Observing Skill](observing_skill.md) — The skill coefficient applied to Microsoft security updates and to commodity exploit data.
- [Benchmarking CVD](benchmarking.md) — What a reasonable benchmark for the skill coefficient is, and why the naive benchmark of zero is a low bar.
- [Benchmarking MPCVD](benchmarking_mpcvd.md) — Extending the measure to a case in which every affected vendor and product has its own history.
- [Reward Functions](reward_functions.md) — Criteria for reward functions over Report Management and Embargo Management histories, and the simulation work they would enable.
- [State Space Size](state_space_size.md) — How large the Vultron protocol state space is for each participant role and for a whole case, and why coordination keeps it tractable.
- [CS Model Limitations](../process_models/cs/cs_model_limitations.md) — Research discussion of what the model leaves out, including transition probabilities and the ordering of case histories.

<!-- END GENERATED SECTION CONTENTS -->

## Where the section connects

The report closes with reflections on how vendors, system owners, coordinators, and governments could each use these indicators.
Those reflections are on [CVD Roles and Their Influence](../other_uses/roles_influence.md), in the [Other Uses](../other_uses/index.md) section, because they are about who acts on the model rather than about measuring it.
A CVD program owner who wants to apply the measure to their own cases, without the derivation, can follow [How to Measure Your CVD Program](../../howto/measure_your_cvd_program.md).
