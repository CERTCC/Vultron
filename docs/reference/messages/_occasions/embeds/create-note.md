<!-- Generated from SEMANTIC_REGISTRY — do not edit; edit the occasions and run `uv run msm-occasions --write` -->

!!! info "Create note"

    Creates a note and, when the note's context names the case, posts it to that case: the Case Manager attaches the note and records the attachment in the case ledger. The Create carries no target. A receiver also accepts a Create followed by an Add of the same note, and the Add then changes nothing more.

    - **When…** a Participant posts a new note to the case
    - **Send:** `Create(Note)`
    - **Send to:** the case manager
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
