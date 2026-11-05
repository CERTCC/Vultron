<!-- Generated from SEMANTIC_REGISTRY — do not edit; edit the occasions and run `uv run msm-occasions --write` -->

!!! info "Ask a participant about proposed embargo terms"

    Asks one participant to accept or reject proposed embargo terms, or a proposed revision. The Case Manager sends one to each participant other than the proposer, naming the proposer in `attributedTo`, and the participant's answer names this Invite.

    - **When…** the Case Manager asks a Participant to answer embargo terms another Participant proposed
    - **Send:** `Invite(EmbargoEvent)[context=VulnerabilityCase]`
    - **Send to:** a participant
    - **Sent by:** the case manager
    - **Reference:** [Ask a participant about proposed embargo terms](../../em.md#relay-embargo-proposal)

    ??? example "Example activity"

        ```python exec="true" idprefix=""
        from vultron.wire.as2.vocab.examples.vocab_examples import (
            relay_embargo_proposal,
            json2md,
        )

        print(json2md(relay_embargo_proposal()))
        ```
