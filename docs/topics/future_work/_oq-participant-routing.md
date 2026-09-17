!!! warning "Open question: which activities does each Participant receive?"

    A Participant holds case-scoped roles.
    The protocol settles the largest part of this question already.
    An Observer receives full case content, and no reduced delivery tier applies to a role (CM-25-003, ADR-0057).
    The gate on case content is admission to the case plus consent to the embargo, and it is not the role (MV-10-005).

    The open part is smaller.
    It covers the single Activity, and it does not cover case content.
    A reduced tier for some Participants is a deferred mechanism, and the project has not specified it.

    There are two possible locations for a routing policy of this type.
    The policy can be on the Participant, as metadata for a test against each activity.
    As an alternative, the policy can be with the CASE_MANAGER, as a set of role-based rules for fan-out.
    The second location agrees better with the other parts of the protocol.
    It keeps one actor responsible for the knowledge of each Participant.

    For the two locations, the fan-out of the CASE_MANAGER continues to be a simple loop across the Participants.
    The per-Participant send makes the decision to relay an activity or not to relay it.
    A prototype can relay each activity to each Participant and stay correct.
    But the structure gives space for a complete set of rules.
