---
description: >
  The first-principles model of the original research: six events, the histories they allow, and a skill measure against chance.
stakeholder_type: [process-researcher]
level: 500
page_type: routing
contents: generated
---

# Foundations

{% include-markdown "../../../includes/not_normative.md" %}

The pages in this group derive a measure of Coordinated Vulnerability Disclosure (CVD) skill from first principles.
They come from the report [A State-Based Model for Multi-Party Coordinated Vulnerability Disclosure (MPCVD)](https://doi.org/10.1184/R1/16416771){:target="_blank"} by Allen Householder and Jonathan Spring, and they describe that report's model as it was written.
They are for readers who want to see how the measure is built, not only how to apply it.

The model here is a much simpler version of what Vultron does today.
It treats a case as six events, each happening once, and asks only in what order they happen.
A Vultron case records far more: each participant's own report, fix, and deployment state, the case's embargo and public state, and when the case learned of each change.
[What a Case Records](../what_a_case_records.md) describes that record.

The simpler model is kept because it shows how to reason about the process models.
Counting the possible histories, ranking them, and comparing what happened against what chance would produce is a method that carries over to the richer record.
The main pages of [Measuring CVD](../index.md) apply it there.

## Pages in this group

The first four pages construct the model, the next two measure against it, and the rest apply the measure or extend the model.

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
    It builds the graph of case states, enumerates the possible histories, computes the probability of each history under the random walk, and computes the frequency of each desideratum.
    Its [Application Programming Interface (API) reference](../../../reference/code/case_states.md) documents each function.
