<!-- Generated from SEMANTIC_REGISTRY — do not edit; edit the occasions and run `uv run msm-occasions --write` -->

!!! info "Announce admitted act"

    Carries the admitted act inline, as it was received, and names it in inReplyTo. It informs and asks nothing: the receiver takes the change from the ledger entry that carries the act, never from the Announce.

    - **When…** the CASE_MANAGER has admitted an act that concerns an actor the ledger fan-out does not reach, such as a removed or reinstated Participant
    - **Send:** `Announce(Activity)[context=VulnerabilityCase]`
    - **Send to:** a participant
    - **Sent by:** the CASE_MANAGER
    - **Reference:** [Announce admitted act](../../case_management.md#announce-admitted-act)

    ??? example "Example activity"

        ```python exec="true" idprefix=""
        from vultron.wire.as2.vocab.examples.vocab_examples import render_example

        print(render_example("announce_participant_removal"))
        ```
