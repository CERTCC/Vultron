<!-- Generated from SEMANTIC_REGISTRY — do not edit; edit the occasions and run `uv run msm-occasions --write` -->

!!! info "Remove note from case"

    Removes the note from the case named by the target.

    - **When…** a note's author or the Case Owner withdraws a note from the case
    - **Send:** `Remove(Note)[target=VulnerabilityCase]`
    - **Send to:** the case manager
    - **Sent by:** the case owner or the note's author
    - **Reference:** [Remove note from case](../../general.md#remove-note-from-case)

    ??? example "Example activity"

        ```python exec="true" idprefix=""
        from vultron.wire.as2.vocab.examples.vocab_examples import (
            remove_note_from_case,
            json2md,
        )

        print(json2md(remove_note_from_case()))
        ```
