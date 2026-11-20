<!-- Generated from SEMANTIC_REGISTRY — do not edit; edit the occasions and run `uv run msm-occasions --write` -->

## Reinstate participant in case { #reinstate-participant-in-case }

The Case Owner's own reinstatement of the removed actor named by the object. The CASE_MANAGER records it as the ledger entry and announces it to the actor, which becomes active again and receives the ledger entries it missed.

=== "Details"

    - **When…** the Case Owner reinstates a removed Participant
    - **Send:** `Add(Actor)[target=VulnerabilityCase]`
    - **Send to:** the CASE_MANAGER
    - **Sent by:** the Case Owner
    - **Seen in:** [How to Manage a Case Roster](../../../../howto/activitypub/activities/manage_participants.md)
    - **Mapping status:** [none](../../index.md#mapping-status)

=== "Example activity"

    ```python exec="true" idprefix=""
    from vultron.wire.as2.vocab.examples.vocab_examples import render_example

    print(render_example("reinstate_participant_in_case"))
    ```
