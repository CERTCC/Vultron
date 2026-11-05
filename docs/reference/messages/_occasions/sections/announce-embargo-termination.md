<!-- Generated from SEMANTIC_REGISTRY — do not edit; edit the occasions and run `uv run msm-occasions --write` -->

## Announce embargo termination { #announce-embargo-termination }

Tells the active participants other than the Case Manager and any Closed Participant that the embargo it names is terminated. It proposes nothing.

=== "Details"

    - **When…** the Case Manager has applied an Embargo Termination a Case Owner sent before the end time
    - **Send:** `Announce(EmbargoEvent)[context=VulnerabilityCase]`
    - **Send to:** a participant
    - **Sent by:** the case manager
    - **Distinguished by:** register status of the named embargo `TERMINATED`
    - **Seen in:** [How to Revise or Terminate an Embargo](../../../../howto/activitypub/activities/manage_embargo.md)
    - **Mapping status:** [none](../../index.md#mapping-status)

    A termination the Case Manager starts itself, or one at the end time, sends no announcement: after the end time, the Case Manager's own end-time check ends the embargo before it applies a Case Owner's termination.

=== "Example activity"

    ```python exec="true" idprefix=""
    from vultron.wire.as2.vocab.examples.vocab_examples import (
        announce_embargo_termination,
        json2md,
    )

    print(json2md(announce_embargo_termination()))
    ```
