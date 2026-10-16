<!-- Generated from SEMANTIC_REGISTRY — do not edit; edit the occasions and run `uv run msm-occasions --write` -->

!!! info "Announce embargo termination"

    Tells the active participants other than the Case Manager that the embargo it names is terminated. It proposes nothing.

    - **When…** the Case Manager has applied an Embargo Termination to the active embargo
    - **Send:** `Announce(Event)[context=VulnerabilityCase]`
    - **Send to:** a participant
    - **Sent by:** the case manager
    - **Reference:** [Announce embargo termination](../../em.md#announce-embargo-termination)

    ??? example "Example activity"

        ```python exec="true" idprefix=""
        from vultron.wire.as2.vocab.examples.vocab_examples import (
            announce_embargo_termination,
            json2md,
        )

        print(json2md(announce_embargo_termination()))
        ```
