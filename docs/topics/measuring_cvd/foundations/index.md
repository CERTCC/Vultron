---
description: >
  The first-principles model of the original research: six events, the histories they allow, and a skill measure against chance.
stakeholder_type: [process-researcher]
level: 500
page_type: routing
subject: neutral
contents: generated
---

# Foundations

{% include-markdown "../../../includes/not_normative.md" %}

The pages in this group build a measure of Coordinated Vulnerability Disclosure (CVD) skill from first principles.
The pages come from the report [A State-Based Model for Multi-Party Coordinated Vulnerability Disclosure (MPCVD)](https://doi.org/10.1184/R1/16416771){:target="_blank"} by Allen Householder and Jonathan Spring.
The pages describe the model of that report as the report wrote it.
The pages are for readers who want to see how the measure is built, not only how to use it.

The model in these pages is much simpler than what Vultron does today.
The model treats a case as six events, gives each event one occurrence, and asks only in which order the six events occur.
A Vultron case records much more:

- the report, fix, and deployment state of each participant
- the embargo state and the public state of the case
- the time at which the case learned of each change

[What a Case Records](../what_a_case_records.md) describes the record of a Vultron case.

We keep the simpler model because it shows a method to reason about the process models.
A history is the order in which the six events occur in one case.
The method has three steps: count the possible histories, rank the histories, and compare the observed histories against chance.
The same method works on the larger record of a Vultron case.
The main pages of [Measuring CVD](../index.md) use the method on that larger record.

## Pages in this group

The first four pages build the model.
The next two pages measure against the model.
The remaining pages use the measure or extend the model.

<!-- BEGIN GENERATED SECTION CONTENTS — do not edit; change the mkdocs.yml nav or a listed page's description: frontmatter, then run `uv run docs-site --write` -->

- [Possible Histories](../possible_histories.md) — The 70 histories a case can have, derived from the six CS events and their ordering constraints.
- [Desirable Histories](../desirable_histories.md) — The twelve desired orderings and the partial order they induce over the histories.
- [Random Walks](../random_walk.md) — A baseline in which every allowed transition is equally likely, from the principle of indifference.
- [Reasoning Over Histories](../reasoning_over_histories.md) — How often each history and each desired ordering occurs under that baseline.
- [Discriminating Skill from Luck](../discriminating_skill_and_luck.md) — The skill coefficient, which normalizes an observed frequency against the baseline.
- [Observing Skill](../observing_skill.md) — The skill coefficient applied to Microsoft security updates and to commodity exploit data.
- [Benchmarking CVD](../benchmarking.md) — What a reasonable benchmark for the skill coefficient is, and why the naive benchmark of zero is a low bar.
- [Benchmarking MPCVD](../benchmarking_mpcvd.md) — Extending the measure to a case in which every affected vendor and product has its own history.
- [State Space Size](../state_space_size.md) — How large the Vultron protocol state space is for each participant role and for a whole case, and why coordination keeps it tractable.
- [Reward Functions](../reward_functions.md) — Criteria for reward functions over Report Management and Embargo Management histories, and the simulation work they would enable.

<!-- END GENERATED SECTION CONTENTS -->

!!! info "In the reference implementation"

    `vultron/core/case_states/hypercube.py` reproduces the tables in these pages.
    The module builds the graph of case states and lists the possible histories.
    It calculates the probability of each history under the random walk, and the frequency of each desideratum.
    Its [Application Programming Interface (API) reference](../../../reference/code/case_states.md) documents each function.
