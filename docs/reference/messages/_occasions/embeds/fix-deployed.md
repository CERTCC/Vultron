<!-- Generated from SEMANTIC_REGISTRY — do not edit; edit the occasions and run `uv run msm-occasions --write` -->

!!! info "Fix Deployed (CD)"

    Announces that the Deployer whose participant record is the target has deployed the fix.

    - **When…** a Deployer has deployed the fix
    - **Send:** `Add(ParticipantStatus)[target=CaseParticipant]`
    - **Sent by:** an active participant (usually: deployer)
    - **Distinguished by:** `dState` = `D`
    - **Reference:** [Fix Deployed (CD)](../../cs.md#fix-deployed)

    ??? example "Example activity"

        ```python exec="true" idprefix=""
        from vultron.wire.as2.vocab.examples.vocab_examples import (
            add_fix_deployment_to_participant,
            json2md,
        )

        print(json2md(add_fix_deployment_to_participant()))
        ```
