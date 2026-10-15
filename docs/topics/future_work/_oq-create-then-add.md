!!! warning "Open question: does a status or an embargo event need its own `Create` before the `Add`?"

    ActivityStreams lets a sender attach a new object in two ways.
    The sender can send one `Add` that carries the object inline.
    As an alternative, the sender can send a `Create` that mints the object, and then an `Add` that attaches it.

    This implementation supports only the first way for a case status, a participant status and an embargo proposal.
    It does not support a received `Create(CaseStatus)`, `Create(ParticipantStatus)` or `Create(Event)`, and it does not support a direct `Create(CaseParticipant)`.
    An inbox refuses each one as an unrecognized activity.
    The demos send the single `Add`, or the `Invite` that carries the `EmbargoEvent`.
    That is a choice of the prototype, and the protocol does not require it.
    A note uses the second way: `Create(Note)` and then `Add(Note)`.

    The open question is whether the protocol must also support the separate `Create` for these objects.
    If it must, each `Create` changes the case file.
    Thus each `Create` needs its own committed ledger entry and a replica apply step, and the `Add` that follows must find the object that the `Create` stored.

    Concern [#4635](https://github.com/CERTCC/Vultron/issues/4635) records this question.
