<!-- Generated from SEMANTIC_REGISTRY — do not edit; edit the occasions and run `uv run msm-occasions --write` -->

!!! info "Add note to case"

    Posts the note to the case named by the target, with the note carried inline as the object: the Case Manager stores the note, attaches it to the case and records the attachment in the case ledger. A receiver also accepts it after a Create of the same note, and it then changes nothing more.

    - **When…** a Participant posts a note to the case
    - **Send:** `Add(Note)[target=VulnerabilityCase]`
    - **Send to:** the case manager
    - **Sent by:** an active participant
    - **Reference:** [Add note to case](../../general.md#add-note-to-case)

    ??? example "Example activity"

        ```python exec="true" idprefix=""
        from vultron.wire.as2.vocab.examples.vocab_examples import (
            add_note_to_case,
            json2md,
        )

        print(json2md(add_note_to_case()))
        ```
