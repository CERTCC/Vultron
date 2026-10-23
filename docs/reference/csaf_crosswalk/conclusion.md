---
description: >
  What the comparison of the Common Security Advisory Framework (CSAF) 2.1
  draft with Vultron shows, and the follow-up work it opens on each side.
stakeholder_type: [cvd-practitioner, platform-developer]
level: 300
page_type: explanation
---

# CSAF 2.1 Crosswalk: Conclusions

{% include-markdown "../../includes/not_normative.md" %}

This page gives the conclusions of the comparison between the Common Security Advisory Framework (CSAF) 2.1 draft and the Vultron Protocol.
It is for readers who want the result of the crosswalk without its detail, and for readers who want to follow the work that comes next.
Each follow-up item links to the issue that tracks it.
The [overview](overview.md), the [concept mapping](concept_mapping.md), the [coverage differences](coverage.md), and the [proposals](proposals.md) give the detail.

{% include-markdown "./_csaf_version.md" %}

---

## What the comparison shows

CSAF and Vultron work at different levels of abstraction.
CSAF records what happened in a disclosure, and Vultron controls how a disclosure proceeds.
The design discussion of the CSAF Technical Committee (TC) states the same difference: the CSAF involvement model is "a documentation model".
For this reason, most gaps are not defects on either side.
They are the result of the different purposes.

The two models are close where they meet.
A CSAF action has the same shape as a Vultron activity: an actor, recipients, a time, a type, and a link to earlier events.
The CSAF entity categories and the Vultron roles cover most of the same parties, and both models put finder and reporter into one role.
Both models also keep exploit availability and public status as facts about the vulnerability, not as events between parties.

The comparison gives three relations between a CSAF document and a Vultron case:

| Relation | Conclusion |
|---|---|
| Replacement | A CSAF document is not the case of record. It holds selected events, has one issuing party, and has no rules for change. |
| Nested content | A CSAF document can travel inside a case as the content of a report, and Vultron can read its process fields as claims by the sender. |
| Projection | A participant can produce a CSAF document from its copy of the case, at publication and during coordination. |

---

## Where each side can improve

The largest gap on the CSAF side is the embargo.
A CSAF document cannot show that an embargo date moved, and it cannot record an early end of an embargo.
The [proposals](proposals.md) page gives two changes that would close this gap.

The largest gap on the Vultron side is depth in the object model.
CSAF describes each vulnerability, each product, and the status of each product.
Vultron does not yet hold vulnerability records on the case, and it tracks the fix path once for each participant.
The Vultron object model has not reached that depth yet.
These gaps are recognized, and they are not decisions to leave the detail out.

Traffic Light Protocol (TLP) labels are a gap of a different type.
Vultron controls access through entitlement and the embargo, and CSAF controls it through a label on each document.
A label becomes necessary when a projection leaves the case, and the way Vultron handles labels is an open concern.

---

## Follow-up work

All follow-up items are part of the Vultron Epic [#5130 CSAF 2.1 crosswalk and interoperability](https://github.com/CERTCC/Vultron/issues/5130){:target="_blank"}.

### Changes Vultron could make

| Issue | Change | Source |
|---|---|---|
| [#5131](https://github.com/CERTCC/Vultron/issues/5131){:target="_blank"} | Vultron could identify CSAF content in a report by its `mediaType`, and read its process fields as claims by the sender. | [Overview](overview.md#a-csaf-document-can-travel-inside-a-case) |
| [#5132](https://github.com/CERTCC/Vultron/issues/5132){:target="_blank"} | Vultron could add vulnerability records to the case, with CSAF or Common Vulnerabilities and Exposures (CVE) content. | [Concept mapping](concept_mapping.md#content-objects) |
| [#5134](https://github.com/CERTCC/Vultron/issues/5134){:target="_blank"} | Vultron could produce a CSAF document from the copy of a case that a participant keeps. | [Overview](overview.md#a-case-can-produce-a-csaf-document) |
| [#5133](https://github.com/CERTCC/Vultron/issues/5133){:target="_blank"} | Vultron could define how TLP labels appear in its data and logic. This item is a concern. | [Overview](overview.md#tlp-marks-a-projection-not-a-case) |
| [#5140](https://github.com/CERTCC/Vultron/issues/5140){:target="_blank"} | Vultron could track the fix path at the granularity of products and deployers. This item is a concern. | [Below](#the-fix-path-and-products) |
| [#5135](https://github.com/CERTCC/Vultron/issues/5135){:target="_blank"} | Vultron could record which participants want public credit. This item is undecided. | [Coverage differences](coverage.md#vulnerability-detail) |

### Changes CSAF could make

The TC decides on changes to CSAF.
Issue [#5137](https://github.com/CERTCC/Vultron/issues/5137){:target="_blank"} tracks the decision whether to send the [proposals](proposals.md) to the TC, for example as comments in the public review of the draft.

---

## The fix path and products

The chain from a case to a deployment is longer in reality than in the Vultron model.
A case holds vulnerabilities, a vulnerability affects the products of vendors, and deployers install the fix for each product.
The Vultron vendor fix path tracks Vendor Awareness (V), Fix Readiness (F), and Fix Deployed (D) once for each participant ([§8.1 VFD — Vendor Aware, Fix Ready, Fix Deployed](../vultron-spec/tracking-models.md#81-vfd-vendor-aware-fix-ready-fix-deployed)).

Each of the three events has a different natural unit:

| Event | Natural unit | Reason |
|---|---|---|
| Vendor Awareness (V) | One vendor | A vendor learns of the vulnerability once. |
| Fix Readiness (F) | One vendor and one product | A vendor with several affected products can have a fix ready for one product and not for another. |
| Fix Deployed (D) | One vendor, one product, and one deployer | Each deployer installs the fix for each product at its own time. |

A case with several vulnerabilities multiplies each unit again.
CSAF already records status at this granularity, in `vulnerabilities[].product_status` and `vulnerabilities[].remediations`.

Tracking at this granularity could increase the state space very much.
It could also bring the Vultron model of the process closer to the real process.
The page [Limitations and Future Work](../../topics/process_models/cs/cs_model_limitations.md#state-explosion) already describes D as a process that spreads through many deployments, and it suggests a roll-up of many facts into one event.
Concern [#5140](https://github.com/CERTCC/Vultron/issues/5140){:target="_blank"} tracks the question.

---

## Summary

| Principle | Statement |
|---|---|
| Purpose | CSAF records a disclosure, and Vultron controls it. Most gaps come from this difference. |
| Shape | A CSAF action and a Vultron activity have the same shape. |
| Relation | A CSAF document is nested content or a projection of a case, never its replacement. |
| CSAF gap | The embargo needs its own end date and a way to record an early end. |
| Vultron gap | The object model needs vulnerability records and possibly product-level fix tracking. |
| Labels | A TLP label belongs to a projection, and Vultron has yet to define how it handles labels. |

## Further reading

- [CSAF 2.1 and Vultron](overview.md) — how a CSAF document relates to a Vultron case.
- [Proposals](proposals.md) — the changes CSAF could make, with their reasons.
- [Concept mapping](concept_mapping.md) — each concept on the two sides, with the type of mapping in each direction.
- [Coverage differences](coverage.md) — concepts that only one of the two models has.
- [Epic #5130](https://github.com/CERTCC/Vultron/issues/5130){:target="_blank"} — the follow-up work on the Vultron side.
