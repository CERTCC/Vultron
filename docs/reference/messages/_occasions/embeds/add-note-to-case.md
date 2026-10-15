<!-- Generated from SEMANTIC_REGISTRY — do not edit; edit the occasions and run `uv run msm-occasions --write` -->

!!! info "Add note to case"

    Attaches the note to the case named by the target, and the Case Manager records the attachment in the case ledger. A receiver accepts it on its own, for a note created earlier or elsewhere, or after a Create of the same note. This implementation's add-note trigger does not send it: a new note goes as a Create alone.

    - **When…** a Participant attaches a note that already exists to the case
    - **Send:** `Add(Note)[target=VulnerabilityCase]`
    - **Send to:** the case manager
    - **Sent by:** not yet checked
    - **Reference:** [Add note to case](../../general.md#add-note-to-case)

    ??? example "Example activity"

        ```python exec="true" idprefix=""
        from vultron.wire.as2.vocab.examples.vocab_examples import (
            add_note_to_case,
            json2md,
        )

        print(json2md(add_note_to_case()))
        ```
