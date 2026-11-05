<!-- Generated from SEMANTIC_REGISTRY — do not edit; edit the occasions and run `uv run msm-occasions --write` -->

## Offer case participant role { #offer-case-participant-role }

Offers one role on the case to the participant named by the target. The Case Manager records the offer and forwards it to that participant.

=== "Details"

    - **When…** the Case Owner offers a CVD role on the case to another participant
    - **Send:** `Offer(CaseParticipantRole)[context=VulnerabilityCase]`
    - **Send to:** the case manager
    - **Sent by:** the case owner
    - **Seen in:** [How to Delegate a Role to Another Participant](../../../../howto/activitypub/activities/role_delegation.md)
    - **Mapping status:** [none](../../index.md#mapping-status)

=== "Example activity"

    ```python exec="true" idprefix=""
    from vultron.wire.as2.vocab.examples.vocab_examples import (
        offer_case_participant_role,
        json2md,
    )

    print(json2md(offer_case_participant_role()))
    ```
