# Model Interactions {#ch:interactions}

Here we reflect on the interactions between the [RM](../rm/), [EM](../em/), and [CS](../cs/) models within the
overall MPCVD process.

## Global vs Participant Specific Aspects

Some aspects of the MPCVD process are global, while others are specific to a
Participant. Specifically, the [RM](../rm/) process is unique to each Participant, while the
[EM](../em/) process is global to all Participants in a case.
The [CS](../cs/) process is a hybrid: some aspects are global, while others are
Participant-specific, which we will discuss in more detail below.
Interactions between all these processes affect the overall MPCVD process for a case. 
The following diagram illustrates this distinction.

```mermaid
stateDiagram-v2
    direction LR
    state Global {
        EM
        CS_pxa
        EM --> CS_pxa
        CS_pxa --> EM
    }
    state ParticipantSpecific {
        RM
        CS_vfd
        RM --> CS_vfd
        CS_vfd --> RM
    }
    Global --> ParticipantSpecific 
    ParticipantSpecific --> Global
```

### Global vs. Participant-Specific Aspects of the CS Model.

The [CS model](../cs/) encompasses both Participant-specific and global aspects of a
CVD case. In particular, the Vendor fix path substates&mdash;Vendor unaware (_vfd_),
Vendor aware (_Vfd_), fix ready (_VFd_), and fix deployed (_VFD_)&mdash;are
specific to each Vendor Participant in a case. On the other hand, the
remaining substates represent global facts about the case
status&mdash;public awareness (_p,P_), exploit public (_x,X_), and attacks
observed (_a,A_). This local versus global distinction will become
important in the [Formal Protocol](../../formal_protocol/) definition.

```mermaid
---
title: Case State Model showing Global and Participant-Specific Aspects
---
stateDiagram-v2
    direction LR
    CS: Case State Model
    state CS {
        ps: Participant Specific
        state ps {
            [*] --> vfd
            vfd --> Vfd
            Vfd --> VFd
            VFd --> VFD
            VFD --> [*]
        }
        --
        g: Global
        state g {
            [*] --> pxa
        
            pxa --> Pxa : P
            pxa --> pXa : X
            pxa --> pxA : A
            
            pXa --> PXa : P
            pXa --> pXA : A
            
            pxA --> PxA : P
            pxA --> pXA : X
        
            Pxa --> PxA : A
            Pxa --> PXa : X
            
            pXA --> PXA : P
            PXa --> PXA : A
            PxA --> PXA : X
            PXA --> [*]
        }
    }
    [*] --> CS
    CS --> [*]
```

