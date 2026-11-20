<!-- Generated from SEMANTIC_REGISTRY — do not edit; edit the occasions and run `uv run msm-occasions --write` -->

## Case Owner invites an actor { #owner-invite-actor-to-case }

The Case Owner's own decision, sent to the CASE_MANAGER only: the case preview as the object, the invitee as the target, and the roles it offers. The CASE_MANAGER records it and sends its own Stub Invite to the invitee, crediting the Case Owner in `attributedTo` and naming this Invite in `inReplyTo`; the invitee answers that Stub Invite.

=== "Details"

    - **When…** the Case Owner decides to invite an actor to the case
    - **Send:** `Invite(VulnerabilityCase preview)[target=Actor]`
    - **Send to:** the CASE_MANAGER
    - **Sent by:** a participant
    - **Seen in:** [How to Invite an Actor to a Case](../../../../howto/activitypub/activities/invite_actor.md)
    - **Mapping status:** [none](../../index.md#mapping-status)

=== "Example activity"

    ```python exec="true" idprefix=""
    from vultron.wire.as2.vocab.examples.vocab_examples import render_example

    print(render_example("owner_invite_actor_to_case"))
    ```
