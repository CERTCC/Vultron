<!-- Generated from SEMANTIC_REGISTRY — do not edit; edit the occasions and run `uv run msm-occasions --write` -->

!!! info "Announce embargo termination"

    Tells the active participants other than the CASE_MANAGER and any Closed Participant that the embargo it names is terminated. It proposes nothing.

    - **When…** the CASE_MANAGER has applied an Embargo Termination a Case Owner sent before the end time
    - **Send:** `Announce(EmbargoEvent)[context=VulnerabilityCase]`
    - **Send to:** a participant
    - **Sent by:** the CASE_MANAGER
    - **Distinguished by:** register status of the named embargo `TERMINATED`
    - **Reference:** [Announce embargo termination](../../em.md#announce-embargo-termination)

    ??? example "Example activity"

        ```python exec="true" idprefix=""
        from vultron.wire.as2.vocab.examples.vocab_examples import render_example

        print(render_example("announce_embargo_termination"))
        ```
