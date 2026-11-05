<!-- Generated from SEMANTIC_REGISTRY — do not edit; edit the occasions and run `uv run msm-occasions --write` -->

## Reject case participant offer { #reject-case-participant-offer }

Rejects the proposed participant record. The Case Manager tells the recommender.

=== "Details"

    - **When…** the Case Owner declines a suggested actor
    - **Send:** `Reject(Offer(CaseParticipant)[target=VulnerabilityCase])`
    - **Send to:** the case manager
    - **Sent by:** the case owner
    - **Seen in:** [How to Suggest an Actor for a Case](../../../../howto/activitypub/activities/suggest_actor.md)
    - **Formal definition:** [General Inquiry (GI)](../../../formal_protocol/messages.md#other-message-types)
    - **Mapping status:** [expansion](../../index.md#mapping-status)

=== "Example activity"

    ```python exec="true" idprefix=""
    from vultron.wire.as2.vocab.examples.vocab_examples import (
        reject_case_participant_offer,
        json2md,
    )

    print(json2md(reject_case_participant_offer()))
    ```
