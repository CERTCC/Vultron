<!-- Generated from SEMANTIC_REGISTRY — do not edit; edit the occasions and run `uv run msm-occasions --write` -->

## Remove note from case { #remove-note-from-case }

Asks to remove the note from the case named by the target. This implementation does not support it: the case ledger is append-only and removing ledgered content has no defined meaning yet, so every receiver refuses it and the note stays in the case (CM-30-003).

=== "Details"

    - **When…** a note's author or the Case Owner withdraws a note from the case
    - **Send:** `Remove(Note)[target=VulnerabilityCase]`
    - **Send to:** the CASE_MANAGER
    - **Sent by:** the Case Owner or the note's author
    - **Seen in:** [How to Post a Status Update or a Case Note](../../../../howto/activitypub/activities/status_updates.md)
    - **Formal definition:** [General Inquiry (GI)](../../../formal_protocol/messages.md#other-message-types)
    - **Mapping status:** [expansion](../../index.md#mapping-status)

=== "Example activity"

    ```python exec="true" idprefix=""
    from vultron.wire.as2.vocab.examples.vocab_examples import render_example

    print(render_example("remove_note_from_case"))
    ```
