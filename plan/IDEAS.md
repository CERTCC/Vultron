# Project Ideas

## Broaden CaseActor timestamping requirement

`CM-10-002` says:

> Embargo acceptances MUST be timestamped by the CaseActor at
> the time of receipt, not using the participant's claimed timestamp
> **Rationale**: The CaseActor applies the only trusted timestamp; the
> participant's reported time cannot be verified

This is actually a generally good idea for all messages received by the 
CaseActor that cause the CaseActor to update its state. So for example, 
participant status updates, embargo status updates, notes added to a case, 
etc. Every item that causes a case to be updated needs to have the 
CaseActor's timestamp as a trusted source of time for history recostruction.
This is important for auditability on cases, and for the "single source of 
truth" principle for a case's history. Without it, we could wind up with 
different copies of a case held by different actors having different 
timestamps for the same events, leading to disagreement about the order of 
events in the history of a case.
