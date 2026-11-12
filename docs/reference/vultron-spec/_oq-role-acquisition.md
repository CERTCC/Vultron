!!! warning "Open question: acquiring a role after joining a case"
    This specification says how the Case Owner *offers* a role to a participant, and how the participant accepts or declines the offer.
    It does not say how a participant already in a case asks for an additional one.

    A participant admitted as a Vendor that later also needs the Coordinator role has no protocol path to request it.
    In practice the request is made out of band, or as an `Add(Note)` on the case, and the Case Owner then issues a role offer.
    Neither is a specified mechanism.

    Open: whether the protocol should define a role-request activity, whether a participant may give up a role it already holds, and how a role that is removed rather than added is represented in the case history.
