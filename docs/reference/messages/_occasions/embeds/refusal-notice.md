<!-- Generated from SEMANTIC_REGISTRY — do not edit; edit the occasions and run `uv run msm-occasions --write` -->

!!! info "Refusal notice"

    Tells the participant that its assertion was received and understood but refused, so it had no effect. It is a Refuse, a subtype of Reject, so the participant does not read it as a decline. It carries the refused activity inline and names the refusing guard's reason. This notice serves the declined purpose of the formal RE, EE, CE and GE messages.

    - **When…** the CASE_MANAGER has refused a participant's assertion because a precondition did not hold
    - **Send:** `Refuse(Activity)`
    - **Send to:** a participant
    - **Sent by:** the CASE_MANAGER
    - **Reference:** [Refusal notice](../../faults_and_acknowledgements.md#refusal-notice)

    ??? example "Example activity"

        ```python exec="true" idprefix=""
        from vultron.wire.as2.vocab.examples.vocab_examples import render_example

        print(render_example("refusal_notice"))
        ```
