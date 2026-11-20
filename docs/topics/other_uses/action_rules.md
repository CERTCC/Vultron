---
stakeholder_type: [process-researcher]
level: 400
page_type: explanation
subject: neutral
description: >
  Actions a role can take from each subset of states, and the transition each action causes.
---

# Recommended Action Rules for CVD

{% include-markdown "../../includes/not_normative.md" %}

Another application of the [CS model](../process_models/cs/index.md) is to
recommend actions for coordinating parties in CVD based on the subset of states that
currently apply to a case. What a coordinating party does depends on
their role and where they engage, as shown in the list below. As
described throughout this documentation, the Vultron protocol is intended
to synchronize state transitions across CVD stakeholders.

<!-- for spacing -->
<br/>

!!! info "Defining CVD Action Rules"

    A significant portion of CVD can be formally described as a set of action
    rules based on this model. For our purposes, a CVD action rule consists of:
    
    | Rule Component | Description                                                                                                                     |
    |----------------|---------------------------------------------------------------------------------------------------------------------------------|
    | Pattern        | The subset of states $Q^{cs} \in \mathcal{Q^{cs}}$ from which the action may be taken, narrowed by the states of other machines |
    | Role(s)        | The role(s) capable of performing the action                                                                                    |
    | Action         | A summary of the action to be taken                                                                                             |
    | Reason         | The rationale for taking the action                                                                                             |
    | Desiderata     | The desiderata the action serves, where the reason is one                                                                       |
    | Move           | The state transition the action causes, if any                                                                                  |

This rule structure follows a common user story pattern:

!!! note "Defining a CVD Action Rule"

    When a case is in a `state` $q^{cs} \in \mathcal{Q}^{cs}$, a `Role`
    can do `Action` for `Reason`, resulting in the `transition event`
    $\sigma \in \Sigma$

## CVD Action Suggestion Rules

The table below lists the authored action rules of [ADR-0216](../../adr/0216-action-rules-span-cs-rm-em-and-pec-and-authored-rules-are-compared-with-rules-generated-from-move-advice.md).
Each rule carries over one pattern and action of the original CS rules, shown in the column "Carried over from".
A rule can be narrowed by the vendor's report management (RM) state, the case's embargo management (EM) state, or the vendor's consent to an embargo (PEC), wherever those states change what the rule is.
A rule names the desiderata that its reason serves, where its reason is one: situation awareness (SA), detection, and defense order no events.
An action causes its case-state event only the first time, so a publication after the public is aware is still a valid action that changes no state.
The original rule that starts the Vulnerabilities Equities Process (VEP) of the US government is left out, because it is not a move of the protocol.
A rule suggests an action and never forbids one.

The command `uv run action-rules-docs --write` generates the table from the authored rules, and a test fails when the table is stale.
[Action Rules Against Move Advice](../measuring_cvd/action_rule_comparison.md) compares each rule with move advice at every position of one vendor.

{% include-markdown "./_action_rules_table.md" %}

!!! vultron "CVD Action Suggestion Rules Engine"

    The rules listed in the table above can be built into a rules engine that
    translates each state in the model to a set of suggested CVD actions.
    The detailed [case state listings](../../reference/case_states/index.md) in the
    references section show the original CS rules applied to each $q^{cs}$ state.

    Furthermore, much of the logic embodied in the rules above forms the basis of the
    [Vultron Process Models](../process_models/index.md)
    and
    [Behavior Logic](../behavior_logic/index.md).

## Action rules are not algorithms

The CVD action rules are not an algorithm.
We do not propose them as a set of actions required in every CVD case.
Following Atul Gawande's lead, we offer them as a way to generate CVD checklists:

!!! quote "Atul Gawande in [The Checklist Manifesto](https://atulgawande.com/book/the-checklist-manifesto/){:target="_blank"}"

    Good checklists, on the other hand, are precise.
    They are efficient, to the point, and easy to use even in the most difficult situations.
    They do not try to spell out everything--a checklist cannot fly a plane.
    Instead, they provide reminders of only the most critical and important steps--the ones that even the highly skilled professional using them could miss.
    Good checklists are, above all, practical.
