!!! warning "Open question: should the protocol add other wire forms for attaching a case record or a note?"

    ActivityStreams lets a sender attach a new object in more than one way.
    The protocol names one way for each act ([ADR-0137](../../adr/0137-case-records-are-attached-by-one-message-never-created-first.md)):

    - A case status is attached by `Add(CaseStatus)`, and a participant status by `Add(ParticipantStatus)`.
    - A proposed embargo event travels on the `Invite` that proposes it.
    - A participant record is made by the Case Manager as a consequence of an act it records.
    - A note is attached by `Add(Note)` with the case as `target`.

    A received `Create` of any of these objects is not a protocol message, and its receiver does not change the case file because of it.

    The protocol defers four other forms.
    It does not reject them:

    - A `Create` that mints the object, then an `Add` that attaches it.
    - A `Create` whose `context` names the case, which attaches the object in one message.
      ActivityPub servers post content this way with `Create(Note)`.
    - A note that is not part of any case.
    - A private note from the Case Manager to one participant about a case, which the case record does not carry.
      The note could reach an inert participant, which receives no case content.
      If the protocol adds this form, the Case Manager may send it but is never required to.

    A participant that a precondition guard refused already learns why from the [refusal notice](../../reference/messages/faults_and_acknowledgements.md#refusal-notice), which is sent to that participant alone and is not recorded in the case.

    The open question is whether the protocol adds any of these forms.
    Each `Create` form changes the case file, so it needs its own committed ledger entry and a replica apply step.
    The `Create` then `Add` form also needs a definition for an object that exists but is not attached.
    A receiver must accept every form the protocol names, so each added form is a cost to every implementation.

    Issue [#4550](https://github.com/CERTCC/Vultron/issues/4550) records the convention that one act names one form.
