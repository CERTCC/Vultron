<!-- Generated from SEMANTIC_REGISTRY — do not edit; edit the occasions and run `uv run msm-occasions --write` -->

| When… | Send | Send to | Sent by | Distinguished by | Details |
|---|---|---|---|---|---|
| a Participant has received a message it cannot process | `Create(ProcessingFault)` | the case manager | not yet checked | — | [Create processing fault](../faults_and_acknowledgements.md#create-processing-fault) |
| the Case Manager has refused a participant's assertion because a precondition did not hold | `Reject(Activity)` | a participant | the case manager | — | [Refusal notice](../faults_and_acknowledgements.md#refusal-notice) |
