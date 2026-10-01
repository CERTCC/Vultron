---
stakeholder_type: [cvd-practitioner, platform-developer]
level: 200
contents: generated
---

# CVD Case State Model Introduction

{% include-markdown "../../../includes/normative.md" %}

This section explains the Case State (CS) model of a Coordinated Vulnerability Disclosure (CVD) case.
It is for practitioners who want to know what the model tracks, and for developers who will implement it.
The pages below develop the model; the normative definition is in the [Vultron Protocol Specification §8 Case State (CS) Dimensions](../../../reference/vultron-spec/tracking-models.md#8-case-state-cs-dimensions-n).

<!-- start_excerpt -->
The CVD Case State (CS) model provides a high-level view of the state of a CVD case.
In it we model two main aspects of the case:

1. A Participant-specific *Vendor Fix Path* from initial vendor awareness through the deployment of a fix.
2. A Participant-agnostic *Public State* summarizing both public and attacker awareness of the vulnerability.

These processes run in parallel, and the CS model captures the interactions between them.
<!-- end_excerpt -->

The model comes from the report [A State-Based Model for Multi-Party Coordinated Vulnerability Disclosure](https://resources.sei.cmu.edu/library/asset-view.cfm?assetid=735513){:target="_blank"}, which carries its full derivation.
The pages in this section present the resulting model of 32 states and their transitions.

## Pages in this section

The first page defines the model's states, and the second builds on it with the transitions between them.
The research discussion of the model's limits, [CS Model Limitations](cs_model_limitations.md), draws on [Measuring CVD](../../measuring_cvd/index.md) and sits in that section.

<!-- BEGIN GENERATED SECTION CONTENTS — do not edit; change the mkdocs.yml nav or a listed page's description: frontmatter, then run `uv run docs-site --write` -->

- [CS States](cs_model.md) — The six substates a case tracks, the Vendor fix path that constrains them, and the resulting set of case states.
- [CS Transitions](transitions.md) — The events that move a case between states, the rules that restrict them, the full state diagram, and the transition grammar.

<!-- END GENERATED SECTION CONTENTS -->

## Where the model is used

The CS model is one of three process models, alongside [Report Management](../rm/index.md) and [Embargo Management](../em/index.md).
[Model Interactions](../model_interactions/index.md) explains how the CS model constrains the other two.
[Measuring CVD](../../measuring_cvd/index.md) uses the CS model to reason about the possible histories of a case.
