<!-- Generated from SEMANTIC_REGISTRY — do not edit; edit the occasions and run `uv run msm-occasions --write` -->

!!! info "Refuse proposed embargo terms"

    Records the sender's own refusal of the proposed terms. The proposal is rejected for the case only when the Case Owner sends its decision.

    - **When…** a Participant refuses proposed embargo terms
    - **Send:** `Reject(Invite(EmbargoEvent)[context=VulnerabilityCase])`
    - **Send to:** the case manager
    - **Sent by:** the invitee
    - **Distinguished by:** EM state `PROPOSED`
    - **Reference:** [Refuse proposed embargo terms](../../em.md#refuse-embargo-proposal)

    ??? example "Example activity"

        ```python exec="true" idprefix=""
        from vultron.wire.as2.vocab.examples.vocab_examples import (
            reject_embargo,
            json2md,
        )

        print(json2md(reject_embargo()))
        ```
