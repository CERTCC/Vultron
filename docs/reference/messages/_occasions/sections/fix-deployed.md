<!-- Generated from SEMANTIC_REGISTRY — do not edit; edit the occasions and run `uv run msm-occasions --write` -->

## Fix Deployed (CD) { #fix-deployed }

Announces that the Deployer whose participant record is the target has deployed the fix.

=== "Details"

    - **When…** a Deployer has deployed the fix
    - **Send:** `Add(ParticipantStatus)[target=CaseParticipant]`
    - **Send to:** the case manager
    - **Sent by:** the case manager or the case owner or the participant status's author (usually: deployer)
    - **Distinguished by:** `dState` = `D`
    - **Seen in:** [How to Post a Status Update or a Case Note](../../../../howto/activitypub/activities/status_updates.md)
    - **Formal definition:** [Fix Deployed (CD)](../../../formal_protocol/messages.md#cs-message-types)
    - **Mapping status:** [collapse](../../index.md#mapping-status)

=== "Example activity"

    ```python exec="true" idprefix=""
    from vultron.wire.as2.vocab.examples.vocab_examples import (
        add_fix_deployment_to_participant,
        json2md,
    )

    print(json2md(add_fix_deployment_to_participant()))
    ```
