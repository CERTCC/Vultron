!!! warning "Open question: which activities does each Participant receive?"

    A Participant carries case-scoped roles, and those roles should govern which case activities reach that Participant.
    An Observer plausibly needs less than a Vendor with fix obligations.
    The rules have not been written.

    Two placements are possible.
    The routing policy can live on the Participant, as metadata each activity is tested against.
    It can instead live with the CASE_MANAGER, as a role-based rule set applied at fan-out time.
    The second is more consistent, because it keeps one actor answerable for what every Participant knows.

    Either way the CASE_MANAGER's fan-out stays a plain loop over Participants, and the decision about whether a given activity is relayed sits inside the per-Participant send.
    A prototype can relay everything to everyone and remain correct.
    The structure has to leave room for a real rule set later.
