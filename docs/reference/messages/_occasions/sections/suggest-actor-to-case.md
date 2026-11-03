<!-- Generated from SEMANTIC_REGISTRY — do not edit; edit the occasions and run `uv run msm-occasions --write` -->

## Suggest actor to case { #suggest-actor-to-case }

Recommends an actor to the CASE_MANAGER for the case named by the target.

=== "Details"

    - **When…** a Participant suggests an actor that the case should include
    - **Send:** `Offer(Actor)[target=VulnerabilityCase]`
    - **Send to:** the CASE_MANAGER
    - **Sent by:** a participant
    - **Distinguished by:** sender is not the Case Owner
    - **Seen in:** [How to Suggest an Actor for a Case](../../../../howto/activitypub/activities/suggest_actor.md)
    - **Formal definition:** [General Inquiry (GI)](../../../formal_protocol/messages.md#other-message-types)
    - **Mapping status:** [expansion](../../index.md#mapping-status)

=== "Example activity"

    ```python exec="true" idprefix=""
    from vultron.wire.as2.vocab.examples.vocab_examples import (
        recommend_actor,
        json2md,
    )

    print(json2md(recommend_actor()))
    ```
