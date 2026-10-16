<!-- em-state-machine-start -->
```mermaid
---
title: Embargo Management State Diagram
---
stateDiagram-v2
    direction LR
    [*] --> None
    state Pre-Embargo {
        None --> Proposed : propose
        Proposed --> Proposed : propose
        Proposed --> Proposed : reject
        Proposed --> None : reject
    }
    state Active_Embargo {
        Active --> Revise : propose
        Revise --> Active : accept
        Revise --> Active : reject
        Revise --> Revise : propose
        Revise --> Revise : accept
        Revise --> Revise : reject
        Revise --> eXited : terminate
        Active --> eXited : terminate
    }
    state Post-Embargo {
        eXited
    }
    Proposed --> Active : accept
    Proposed --> Revise : accept
    eXited --> [*]
```
<!-- em-state-machine-end -->

The diagram shows every move of the EM transition table.
A self-loop on reject or accept is the move made while another proposal is still open, and accept from Proposed reaches Revise when the other open proposals become revisions of the embargo now in force.
