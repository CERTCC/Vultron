# Case Splitting and Merging

{% include-markdown "../../../includes/normative.md" %}

Cases sometimes need to be split into multiple cases or merged into a single case.
Case Splits can happen when a single vulnerability affects multiple products with different fix supply chains.
Case Mergers can happen when two independent reports of vulnerabilities are found to be the same vulnerability.
We discuss the impact of these events on embargoes below.

## Impact of Case Mergers on Embargoes

While relatively rare, it is sometimes necessary for two independent CVD cases to be merged into a single case. 

!!! example "Case Merge Example"

    Two Finders independently discover vulnerabilities in separate products and report them to their respective
    (distinct) Vendors.
    Each Reporter-Vendor pair has already negotiated its own embargo.
    On further investigation, it is determined that both reported problems stem from a vulnerability in a library shared
    by both products.
    The decision is made to merge the cases into a single case.
    Once the cases merge, the best option is usually to renegotiate a new embargo for the new case.

!!! note ""

    A new embargo SHOULD be proposed when any two or more
    CVD cases are to be merged into a single case and multiple parties have agreed to
    different embargo terms prior to the case merger.

!!! note ""

    If no new embargo has been proposed, or if agreement has not been
    reached, the earliest of the previously accepted embargo dates SHALL
    be adopted for the merged case.

!!! note ""

    Participants MAY propose revisions to the embargo on a merged case
    as usual.

## Impact of Case Splits on Embargoes

It is also possible that a single case needs to be split into multiple cases after an embargo has been agreed to.

!!! example "Case Split Example"

    A vulnerability that affects two widely disparate fix supply chains, such as a library used in both Software-as-a-Service (SAAS) and 
    Operational Technology (OT) environments.
    The SAAS Vendors might be well positioned for a quick fix deployment while the OT Vendors might need considerably
    longer to work through the logistics of delivering deployable fixes to their customers.
    In such a case, the case Participants might choose to split the case into its respective supply chain cohorts to
    better coordinate within each group.
    
Unlike the relatively simple situation of merging two cases, splitting a case into multiple cases is more complex.
Case splits impose a dependency between the new case embargoes because the earlier embargo on one case might reveal the
existence of a vulnerability in the products allocated to the later case.
In these scenarios, it can be helpful to engage the services of a third party Coordinator (if one is not already involved in the case)
to help navigate the case split.

!!! note ""

    When a case is split into two or more parts, any existing embargo
    SHOULD transfer to the new cases.

!!! note ""

    Participants approaching a case split MAY engage a Coordinator to act as a trusted third party to help
    resolve and coordinate embargo dependencies for the new cases.

!!! note ""

    If any of the new cases need to renegotiate the embargo inherited
    from the parent case, any new embargo SHOULD be later than the
    inherited embargo.

!!! note ""

    In the event that an earlier embargo date is needed for a child
    case, consideration SHALL be given to the impact that ending the
    embargo on that case will have on the other child cases retaining a
    later embargo date. In particular, Participants in each child case
    should assess whether earlier publication of one child case might
    reveal the existence of or details about other child cases.

!!! note ""

    Participants in a child case SHALL communicate any subsequently
    agreed changes from the inherited embargo to the Participants of the
    other child cases.

Note that it may not always be possible for the split cases to have
different embargo dates without the earlier case revealing the existence
of a vulnerability in the products allocated to the later case. For this
reason, it is often preferable to avoid case splits entirely.

