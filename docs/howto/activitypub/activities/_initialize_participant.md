# Initializing a CaseParticipant

```mermaid
flowchart LR
    subgraph as:Create
        RmCreateParticipant
    end
    subgraph as:Add
        AddParticipantToCase
    end
    RmCreateParticipant --> AddParticipantToCase
```
