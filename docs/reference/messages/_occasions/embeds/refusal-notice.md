<!-- Generated from SEMANTIC_REGISTRY — do not edit; edit the occasions and run `uv run msm-occasions --write` -->

!!! info "Refusal notice"

    Tells the participant that its assertion was received and understood but refused, so it had no effect. It carries the refused activity inline and names the refusing guard's reason. This notice serves the declined purpose of the formal RE, EE, CE and GE messages.

    - **When…** the Case Manager has refused a participant's assertion because a precondition did not hold
    - **Send:** `Reject(Activity)`
    - **Send to:** a participant
    - **Sent by:** the case manager
    - **Reference:** [Refusal notice](../../faults_and_acknowledgements.md#refusal-notice)

    ??? example "Example activity"

        ```python exec="true" idprefix=""
        from vultron.wire.as2.vocab.examples.vocab_examples import (
            refusal_notice,
            json2md,
        )

        print(json2md(refusal_notice()))
        ```
