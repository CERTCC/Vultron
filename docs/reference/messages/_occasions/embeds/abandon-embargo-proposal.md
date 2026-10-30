<!-- Generated from SEMANTIC_REGISTRY — do not edit; edit the occasions and run `uv run msm-occasions --write` -->

!!! info "Abandon embargo proposal"

    Cancels the proposal for the case. The Case Manager then withdraws each Invite it relayed for the proposal. This Reject is not the Case Manager's consent.

    - **When…** the Case Manager abandons an open embargo proposal it received once the case is public, an exploit is public or attacks are observed
    - **Send:** `Reject(Invite(EmbargoEvent)[context=VulnerabilityCase])`
    - **Send to:** a participant
    - **Sent by:** the case manager
    - **Reference:** [Abandon embargo proposal](../../em.md#abandon-embargo-proposal)

    ??? example "Example activity"

        ```python exec="true" idprefix=""
        from vultron.wire.as2.vocab.examples.vocab_examples import (
            abandon_embargo_proposal,
            json2md,
        )

        print(json2md(abandon_embargo_proposal()))
        ```
