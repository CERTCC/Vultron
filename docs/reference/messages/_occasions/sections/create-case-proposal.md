<!-- Generated from SEMANTIC_REGISTRY — do not edit; edit the occasions and run `uv run msm-occasions --write` -->

## Create case proposal { #create-case-proposal }

Submits a case proposal for the attached report to the service's inbox. No case exists yet.

=== "Details"

    - **When…** a report receiver asks a Case Actor Service to open a case for a report
    - **Send:** `Create(CaseProposal)`
    - **Send to:** an actor outside any case
    - **Sent by:** the case proposal's author (usually: vendor, coordinator)
    - **Mapping status:** [none](../../index.md#mapping-status)

=== "Example activity"

    ```python exec="true" idprefix=""
    from vultron.wire.as2.vocab.examples.vocab_examples import (
        create_case_proposal,
        json2md,
    )

    print(json2md(create_case_proposal()))
    ```
