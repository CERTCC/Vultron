!!! warning "Open question: which activities does each Participant receive?"

    A Participant holds case-scoped roles.
    These roles control which case activities go to that Participant.
    An Observer possibly receives fewer activities than a Vendor that has fix obligations.
    The project has not written these rules.

    There are two possible locations for the routing policy.
    The policy can be on the Participant, as metadata for a test against each activity.
    As an alternative, the policy can be with the CASE_MANAGER, as a set of role-based rules for fan-out.
    The second location agrees better with the other parts of the protocol.
    It keeps one actor responsible for the knowledge of each Participant.

    For the two locations, the fan-out of the CASE_MANAGER continues to be a simple loop across the Participants.
    The per-Participant send makes the decision to relay an activity or not to relay it.
    A prototype can relay each activity to each Participant and stay correct.
    But the structure gives space for a complete set of rules.
