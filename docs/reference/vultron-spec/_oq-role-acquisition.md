!!! warning "Open question: acquiring a role after joining a case"
    This specification says how the Case Owner *assigns* a role and how a role is
    *offered and accepted*. It does not say how a participant already in a case
    asks for an additional one.

    A participant admitted as a Vendor that later also needs the Coordinator
    role has no protocol path to request it. In practice the request is made out
    of band, or as a `Add(Note)` on the case, and the Case Owner then issues a
    role offer. Neither is a specified mechanism.

    Open: whether the protocol should define a role-request activity, whether a
    participant may decline a role it was assigned, and how a role that is
    removed rather than added is represented in the case history.
