<!-- Generated from SEMANTIC_REGISTRY — do not edit; edit the occasions and run `uv run msm-occasions --write` -->

## Remove participant from case { #remove-participant-from-case }

The Case Owner's own removal of the actor named by the object, from the case named by the origin. The CASE_MANAGER records it as the ledger entry and announces it to the removed actor.

=== "Details"

    - **When…** the Case Owner removes a Participant from active participation
    - **Send:** `Remove(Actor)[origin=VulnerabilityCase]`
    - **Send to:** the CASE_MANAGER
    - **Sent by:** the Case Owner
    - **Seen in:** [How to Manage a Case Roster](../../../../howto/activitypub/activities/manage_participants.md)
    - **Mapping status:** [none](../../index.md#mapping-status)

=== "Example activity"

    ```python exec="true" idprefix=""
    from vultron.wire.as2.vocab.examples.vocab_examples import render_example

    print(render_example("remove_participant_from_case"))
    ```
