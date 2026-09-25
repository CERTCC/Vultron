---
stakeholder_type: [cvd-practitioner, process-researcher]
level: 300
---

# Report Management Interactions Between CVD Participants

Each Participant in a Coordinated Vulnerability Disclosure (CVD) case has their own instance of the [Report Management (RM) state model](index.md).
Participants can change their local state independent of the state of other Participants.
Events within a CVD case may trigger a state transition in one Participant while no transition occurs in another.
For example, [participants interact from the accepted state](index.md#participants-interact-from-the-accepted-state) shows that even though the *sender* is the one taking the action, it is the *recipient*'s state that changes.
The table below lists role-based actions.

| Finder/Reporter  |      Vendor      |   Coordinator    | Action                                  |                                         RM Transition                                          |
|:----------------:|:----------------:|:----------------:|-----------------------------------------|:----------------------------------------------------------------------------------------------:|
| :material-check: |                  |                  | Discover Vulnerability (hidden)         |                           [Receive Report](index.md#receive-report)                            |
| :material-check: |                  |                  | Analyze Discovery (hidden)              |                          [Validate Report](index.md#validate-report)                           |
| :material-check: |                  |                  | Decide whether to initiate CVD (hidden) |                        [Prioritize Report](index.md#prioritize-report)                         |
| :material-check: | :material-check: | :material-check: | Notify Vendor                           | [Participants Interact from Accepted](index.md#participants-interact-from-the-accepted-state) |
| :material-check: | :material-check: | :material-check: | Notify Coordinator                      | [Participants Interact from Accepted](index.md#participants-interact-from-the-accepted-state) |
|                  | :material-check: | :material-check: | Receive Report                          |                           [Receive Report](index.md#receive-report)                            |
|                  | :material-check: | :material-check: | Validate Report                         |                          [Validate Report](index.md#validate-report)                           |
| :material-check: | :material-check: | :material-check: | Prioritize Report                       |                        [Prioritize Report](index.md#prioritize-report)                         |
| :material-check: | :material-check: | :material-check: | Pause Work                              |                        [Prioritize Report](index.md#prioritize-report)                         |
| :material-check: | :material-check: | :material-check: | Resume Work                             |                        [Prioritize Report](index.md#prioritize-report)                         |
| :material-check: | :material-check: | :material-check: | Close Report                            |                             [Case Closure](index.md#case-closure)                             |

A few examples of this model applied to common CVD and multi-party CVD case scenarios follow.

## The Secret Lives of Finders

The Finder's *Received*, *Valid*, and *Invalid* states are useful for modeling and simulation, but they are less useful as part of a CVD protocol.
For anyone else to know about the vulnerability, and for CVD to happen at all, the Finder must already have validated the report and prioritized it as worth the effort of coordinating its disclosure.
In other words, CVD only starts *after* the Finder has reached the *Accepted* state for the vulnerability being reported.
That is also the point at which a *Finder* becomes a *Reporter*.
The model keeps these states for completeness.
The formal protocol's [starting states](../../../reference/formal_protocol/states.md#starting-states) build on this: a Finder/Reporter is presumed to enter a case already in *Accepted*.

The diagram below separates the Finder's hidden states from the ones other Participants can observe.

```mermaid
---
title: Hidden States of Finders
---
stateDiagram-v2
    direction LR
    state Finder {
        direction LR
        A: Accepted
        state Hidden {
            direction LR
            R: Received
            I: Invalid
            V: Valid
            D: Deferred
            [*] --> R
            R --> I
            R --> V
            V --> D
            I --> V
            V --> A
            D --> A
            D --> [*]
            I--> [*]
        }
        state Observable {
            direction LR
            D2: Deferred
            A --> D2
            D2 --> A
            A --> [*]
            D2 --> [*]
        }
                
    }
```

## Finder-Vendor CVD

A simple Finder-Vendor CVD scenario is shown below.
As explained [above](#the-secret-lives-of-finders), most of the Finder's states are hidden from view until they reach the *Accepted* ($A_f$) state.
The *receive* action $A_f \xrightarrow{r} R_v$ that bridges the two Participants is an instance of [participants interacting from the accepted state](index.md#participants-interact-from-the-accepted-state).
Each Participant then continues through their own copy of the [RM state machine](index.md#rm-states), shown here as "…".

```mermaid
---
title: Finder-Vendor CVD
---
stateDiagram-v2
    direction LR
    state Finder {
        direction LR
        Af: A<sub>f</sub>
        fprior: …
        fprior --> Af
    }
    state Vendor {
        direction LR
        Rv: R<sub>v</sub>
        vafter: …
        Rv --> vafter
    }
    Af --> Rv: r
```

## Finder-Coordinator-Vendor CVD

A slightly more complicated scenario in which a Finder engages a Coordinator after failing to engage a Vendor is shown in the next diagram.
This scenario is very common in the experience of the CERT Coordination Center (CERT/CC).
That is no surprise, because as a Coordinator the CERT/CC does not take part in cases like the previous example.
Here there are three notification actions, each an instance of [participants interacting from the accepted state](index.md#participants-interact-from-the-accepted-state):

- First, $A_f \xrightarrow{r_0} R_v$ represents the Finder's initial attempt to reach the Vendor.
- Next, $A_f \xrightarrow{r_1} R_c$ is the Finder's subsequent attempt to engage with the Coordinator.
- Finally, the Coordinator contacts the Vendor in $A_c \xrightarrow{r_2} R_v$.

The diagram shows only the states each notification connects.

```mermaid
---
title: Finder-Coordinator-Vendor CVD
---
stateDiagram-v2
    direction LR
    state Finder {
        direction LR
        Af: A<sub>f</sub>
    }
    state Coordinator {
        direction LR
        Rc: R<sub>c</sub>
        Ac: A<sub>c</sub>
        cmid: …
        Rc --> cmid
        cmid --> Ac
    }
    state Vendor {
        direction LR
        Rv: R<sub>v</sub>
        vafter: …
        Rv --> vafter
    }
    Af --> Rv: r0
    Af --> Rc: r1
    Ac --> Rv: r2
```

## MPCVD with a Coordinator and Multiple Vendors

A small Multi-Party Coordinated Vulnerability Disclosure (MPCVD) scenario is shown below.
As with the other examples, each notification shown is an instance of [participants interacting from the accepted state](index.md#participants-interact-from-the-accepted-state).
Unlike the previous example, this scenario starts with the Finder contacting a Coordinator, perhaps because they recognize the increased complexity of coordinating multiple Vendors' responses.

- First, $A_f \xrightarrow{r_0} R_c$ represents the Finder's initial report to the Coordinator.
- Next, $A_c \xrightarrow{r_1} R_{v_1}$ shows the Coordinator contacting the first Vendor.
- Finally, the Coordinator contacts a second Vendor in $A_c \xrightarrow{r_2} R_{v_2}$.

The diagram shows only the states each notification connects.

```mermaid
---
title: MPCVD with a Coordinator and Multiple Vendors
---
stateDiagram-v2
    direction LR
    state Finder {
        direction LR
        Af: A<sub>f</sub>
    }
    state Coordinator {
        direction LR
        Rc: R<sub>c</sub>
        Ac: A<sub>c</sub>
        cmid: …
        Rc --> cmid
        cmid --> Ac
    }
    state Vendor1 {
        direction LR
        Rv1: R<sub>v<sub>1</sub></sub>
        v1after: …
        Rv1 --> v1after
    }
    state Vendor2 {
        direction LR
        Rv2: R<sub>v<sub>2</sub></sub>
        v2after: …
        Rv2 --> v2after
    }
    Af --> Rc: r0
    Ac --> Rv1: r1
    Ac --> Rv2: r2
```

## A Menagerie of MPCVD Scenarios

Other MPCVD RM interaction configurations are possible, and the following figures show a few of them.
This time each node represents a Participant's entire RM model, and each edge is a notification from one Participant's *Accepted* state to another's *Received* state.
The CERT/CC has observed all of the following interactions.
The RM model is meant to be composable enough to accommodate all such permutations.

### Finder coordinates MPCVD with Multiple Vendors

A Finder notifies multiple Vendors without engaging a Coordinator.

```mermaid
---
title: Finder coordinates MPCVD with Multiple Vendors
---
stateDiagram-v2
    direction LR
    Finder --> Vendor1: r0
    Finder --> Vendor2: r1
    Finder --> Vendor3: r2
```

### Vendor coordinates MPCVD

A Finder notifies a Vendor, who, in turn, notifies other Vendors.

```mermaid
---
title: Vendor coordinates MPCVD
---
stateDiagram-v2
    direction LR
    Finder --> Vendor1: r0
    Vendor1 --> Vendor2: r1
    Vendor1 --> Vendor3: r2
    Vendor1 --> Vendor4: r3
```

### Vendor Engages a Coordinator for MPCVD

A Finder notifies a Vendor, who, in turn, engages a Coordinator to reach other Vendors.

```mermaid
---
title: Vendor Engages a Coordinator for MPCVD
---
stateDiagram-v2
    direction LR
    Finder --> Vendor1: r0
    Vendor1 --> Coordinator: r1
    Coordinator --> Vendor2: r2
    Coordinator --> Vendor3: r3
    Coordinator --> Vendor4: r4
```

### Supply-chain oriented MPCVD

Supply-chain oriented MPCVD often has two or more tiers of Vendors, each notified by the upstream Vendors whose components they use, with or without one or more Coordinators' involvement.

```mermaid
---
title: Supply-chain oriented MPCVD
---
stateDiagram-v2
    direction LR
    Finder --> Vendor1: r0
    Vendor1 --> Vendor2: r1
    Vendor1 --> Vendor3: r2
    Vendor1 --> Coordinator: r3
    Vendor2 --> Vendor4: r4
    Vendor4 --> Vendor5: r5
    Vendor3 --> Vendor6: r6
    Coordinator --> Vendor7: r7
    Vendor7 --> Vendor8: r8
    Vendor7 --> Vendor9: r9
```

## Where to go next

Once a case exists, the RM process runs alongside the [Embargo Management (EM) process](../em/index.md).
[Interactions Between the RM and EM Models](../model_interactions/rm_em.md) describes the constraints each places on the other.
