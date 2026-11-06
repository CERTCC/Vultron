!!! warning "Open question: may the Case Owner delegate activating an embargo to the CASE_MANAGER?"
    Activating a proposed embargo is the Case Owner's decision for the case.
    The owner sends `Add(EmbargoEvent)` with `target` naming the `VulnerabilityCase`, and `inReplyTo` naming the `Invite(EmbargoEvent)` that proposed it.
    Ending an embargo can already be delegated: the CASE_MANAGER may send the `Remove(EmbargoEvent)` on the owner's behalf.
    Activation has no such path.

    What is settled is how the owner's own answer bears on any activation.
    The owner's `Accept(Invite(EmbargoEvent))` or `Reject(Invite(EmbargoEvent))` is its consent as a participant, and its decision for the case never rewrites that answer.
    An owner that declined a proposal accepts it before it activates it.
    So if activation is ever delegated, only an owner that has accepted the proposal can authorize the CASE_MANAGER's `Add`.

    Open: whether the owner may delegate activation at all; how a delegation is expressed on the wire, for example as part of the owner's published embargo policy or as an instruction for one case; and whether the CASE_MANAGER's `Add` names the owner's `Accept` or the proposal's `Invite` in `inReplyTo`.
    Once a resolution is reached, it will be reflected in this reference and in the embargo message requirements.
