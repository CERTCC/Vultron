---
stakeholder_type: [cvd-practitioner]
level: 300
page_type: explanation
subject: protocol
description: >
  What happens to embargoes when cases are split or merged.
---

# Case Splitting and Merging

{% include-markdown "../../../includes/specification_governs.md" %}

Sometimes it is necessary to split a case into multiple cases, or to merge cases into a single case.
A Case Split can occur when a single vulnerability affects multiple products with different fix supply chains.
A Case Merger can occur when two independent vulnerability reports are about the same vulnerability.
Below, we discuss how these events affect embargoes.

## Impact of Case Mergers on Embargoes

Sometimes it is necessary to merge two independent CVD cases into a single case, but this is relatively rare.

!!! example "Case Merge Example"

    Two Finders independently discover vulnerabilities in separate products.
    Each Finder reports to the Vendor of their product, and these Vendors are different.
    Each Reporter-Vendor pair has already negotiated its own embargo.
    Further investigation shows that both reported problems come from a vulnerability in a library that both products share.

    The Participants decide to merge the cases into a single case.
    After the cases merge, the best option is usually to negotiate a new embargo for the new case.

!!! note ""

    A new embargo SHOULD be proposed when any two or more CVD cases are to be merged into a single case and multiple parties have agreed to different embargo terms prior to the case merger.

!!! note ""

    If no new embargo has been proposed, or if agreement has not been reached, the earliest of the previously accepted embargo dates SHALL be adopted for the merged case.

!!! note ""

    Participants MAY propose revisions to the embargo on a merged case as usual.

## Impact of Case Splits on Embargoes

It can also become necessary to split a single case into multiple cases after the Participants agree to an embargo.

!!! example "Case Split Example"

    A vulnerability can affect two very different fix supply chains.
    An example is a library used in both Software-as-a-Service (SAAS) and Operational Technology (OT) environments.
    The SAAS Vendors might be ready for a quick fix deployment.
    But the OT Vendors might need much more time to solve the logistics of delivering deployable fixes to their customers.

    In such a case, the case Participants might choose to split the case into one cohort for each supply chain.
    Each group can then coordinate better within itself.

A merge of two cases is relatively simple.
A split of a case into multiple cases is more complex.
A case split makes the embargoes of the new cases depend on each other.
This is because the earlier embargo on one case might reveal that a vulnerability exists in the products of the later case.

In these scenarios, a third-party Coordinator can help with the case split.
If no Coordinator is already involved in the case, the Participants can engage one.

!!! note ""

    When a case is split into two or more parts, any existing embargo SHOULD transfer to the new cases.

!!! note ""

    Participants approaching a case split MAY engage a Coordinator to act as a trusted third party to help resolve and coordinate embargo dependencies for the new cases.

!!! note ""

    If any of the new cases need to renegotiate the embargo inherited from the parent case, any new embargo SHOULD be later than the inherited embargo.

!!! note ""

    In the event that an earlier embargo date is needed for a child case, consideration SHALL be given to the impact that ending the embargo on that case will have on the other child cases retaining a later embargo date.
    In particular, Participants in each child case should assess whether earlier publication of one child case might reveal the existence of or details about other child cases.

!!! note ""

    Participants in a child case SHALL communicate any subsequently agreed changes from the inherited embargo to the Participants of the other child cases.

Sometimes the split cases cannot have different embargo dates unless the earlier case reveals that a vulnerability exists in the products of the later case.
For this reason, it is often better to not split cases at all.

In Vultron, the Case Owner of the parent plans a split.
To do this, the Case Owner proposes a child Case to the CASE_MANAGER of the parent.
The child links to its parent by ID.
The child inherits the end time of the active embargo as a new embargo of its own, and it inherits nothing else from the parent.

One CASE_MANAGER hosts the parent and its children.
That CASE_MANAGER records each embargo change in the ledgers of the other Cases, and those ledgers tell their own Participants.
[ADR-0125](../../../adr/0125-case-split-child-case-inherits-the-embargo-only.md) records the design.

## Doing It on the Wire

- [How to Establish an Embargo](../../../howto/activitypub/activities/establish_embargo.md) — propose and activate the embargo for a child or merged case.
- [How to Revise or Terminate an Embargo](../../../howto/activitypub/activities/manage_embargo.md) — change inherited embargo terms, or end an embargo.
