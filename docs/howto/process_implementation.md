# Process Implementation Notes

Integrating the MPCVD protocol into everyday MPCVD operations requires each Participant to consider how their business processes
interact with the individual [RM](/topics/process_models/rm/), [EM](/topics/process_models/em/), 
and [CS](/topics/process_models/cs/), process models, respectively.
Here we offer some thoughts on where such integration might begin.

## RM Implementation Notes

Roughly speaking, the RM process is very close to a normal ITSM incident or service request workflow.
As such, the RM process could be implemented as a JIRA ticket workflow, as part of a Kanban process, etc.
The main modifications needed to adapt an existing workflow are to intercept the key milestones and emit the appropriate RM messages:

-   when the reports are received (_RK_)

-   when the report validation process completes (_RI_, _RV_)

-   when the report prioritization process completes (_RA_, _RD_)

-   when the report is closed (_RC_)

### Vulnerability Draft Pre-Publication Review

!!! tip inline end "Pre-Publication Drafts in Related Standards"

    [ISO/IEC 29148:2018](https://www.iso.org/standard/72311.html) includes a pre-publication review step in its process.

MPCVD case Participants often share pre-publication drafts of their advisories during the embargo period.
Our protocol proposal is mute on this subject because it is not strictly necessary for the MPCVD process to complete successfully.
However, as we observe in {== Appendix [\[app:iso_crosswalk\]](#app:iso_crosswalk){reference-type="ref"
reference="app:iso_crosswalk"} ==}, the _GI_ and _GK_ message types appear to provide sufficient mechanics for this 
process to be fleshed out as necessary.
This draft-sharing process could be built into the [*prepare publication*](/topics/behavior_logic/publication_bt/#prepare-publication-behavior) process, where appropriate.

## EM Implementation Notes

In terms of the proposal, acceptance, rejection, etc., the
EM process is
strikingly parallel to the process of scheduling a meeting in a
calendaring system.
In {== Appendix [\[app:em_icalendar\]](#app:em_icalendar){reference-type="ref" reference="app:em_icalendar"} ==},
we suggest a potential mapping of many of the concepts from the EM process onto `iCalendar` protocol semantics.

## CS Implementation Notes

Because part of the CS model is Participant specific and the other is global to the case, we address each part below.

### The _vfd_ Process

Similar to the RM process, which is specific to each Participant, the _vfd_ process is
individualized to each Vendor (or Deployer, for the simpler $d \xrightarrow{\mathbf{D}} D$ state transition).
Modifications to the Vendor's development process to implement the MPCVD protocol are expected to be minimal and are 
limited to the following:

-   acknowledging the Vendor's role on report receipt with a _CV_ message

-   emitting a _CF_ message when a fix becomes ready (and possibly terminating any active embargo to open the door to publication)

-   (if relevant) issuing a _CD_ message when the fix has been deployed

Non-Vendor Deployers are rarely involved in MPCVD cases, but when they are, their main integration point is to emit a 
_CD_ message when deployment is complete.

### The _pxa_ Process

On the other hand, the _pxa_ process hinges on monitoring public and private sources for evidence of information leaks, 
research publications, and adversarial activity.
In other words, the _pxa_ process is well positioned to be wired into Participants' threat intelligence and threat
analysis capabilities. Some portions of this process can be automated:

-   Human analysts and/or automated search agents can look for evidence of early publication of vulnerability information.

-   IDS and IPS signatures might be deployed prior to fix availability to act as an early warning of adversary activity.

-   Well-known code publication and malware analysis platforms can be monitored for evidence of exploit publication or use.