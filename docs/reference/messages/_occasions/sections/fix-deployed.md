<!-- Generated from SEMANTIC_REGISTRY — do not edit; edit the occasions and run `uv run msm-occasions --write` -->

## Fix Deployed (CD) { #fix-deployed }

Announces that the Deployer whose participant record is the target has deployed the fix.

=== "Details"

    - **When…** a Deployer has deployed the fix
    - **Send:** `Add(ParticipantStatus)[target=CaseParticipant]`
    - **Send to:** the CASE_MANAGER
    - **Sent by:** the CASE_MANAGER or the Case Owner or the participant status's author (usually: deployer)
    - **Distinguished by:** `dState` = `D`
    - **Seen in:** [How to Post a Status Update or a Case Note](../../../../howto/activitypub/activities/status_updates.md)
    - **Formal definition:** [Fix Deployed (CD)](../../../formal_protocol/messages.md#cs-message-types)
    - **Mapping status:** [collapse](../../index.md#mapping-status)

=== "Example activity"

    ```python exec="true" idprefix=""
    from vultron.wire.as2.vocab.examples.vocab_examples import render_example

    print(render_example("add_fix_deployment_to_participant"))
    ```
