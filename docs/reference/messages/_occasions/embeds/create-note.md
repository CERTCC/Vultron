<!-- Generated from SEMANTIC_REGISTRY — do not edit; edit the occasions and run `uv run msm-occasions --write` -->

!!! info "Create note"

    Mints a note for the case. When the note's context names the case, the Case Manager attaches it and records the attachment in the case ledger, so the Add that follows changes nothing more.

    - **When…** a Participant has written a note it is about to post to the case
    - **Send:** `Create(Note)`
    - **Sent by:** not yet checked
    - **Reference:** [Create note](../../general.md#create-note)

    ??? example "Example activity"

        ```python exec="true" idprefix=""
        from vultron.wire.as2.vocab.examples.vocab_examples import (
            create_note,
            json2md,
        )

        print(json2md(create_note()))
        ```
