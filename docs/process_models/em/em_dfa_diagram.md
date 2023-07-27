<!-- em-state-machine-start -->
```mermaid
stateDiagram-v2
    direction LR
    state Pre-Embargo {
        [*] --> None
        None --> Proposed : propose
        Proposed --> None : reject
        Proposed --> Active : accept
    }
    state Active_Embargo {
        Active --> Revise : revise
        Revise --> Active : accept
        Revise --> Active : reject
        Revise --> eXited : terminate
        Active --> eXited : terminate
    }
    state Post-Embargo {
        eXited --> [*]
    }
```
<!-- em-state-machine-end -->
