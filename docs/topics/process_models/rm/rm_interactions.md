---
stakeholder_type: [cvd-practitioner, process-researcher]
level: 300
page_type: explanation
description: >
  The RM model applied to common coordination scenarios, from a single Reporter and Vendor to multi-party cases.
---

# Report Management Interactions Between CVD Participants

Each Participant in a Coordinated Vulnerability Disclosure (CVD) case has their own instance of the [Report Management (RM) state model](index.md).
Participants can change their local state independently of the state of other Participants.
An event in a CVD case can cause a state transition in one Participant and no transition in another.
For example, [participants interact from the accepted state](index.md#participants-interact-from-the-accepted-state) shows that the *sender* does the action, but the state of the *recipient* changes.
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

The *Received*, *Valid*, and *Invalid* states of the Finder help in modeling and simulation, but they are less useful as part of a CVD protocol.
Other Participants can know about the vulnerability only after the Finder validates the report and decides that the report is worth the effort to coordinate its disclosure.
Without these two steps, CVD cannot happen at all.
Thus, CVD starts only *after* the Finder has reached the *Accepted* state for the vulnerability being reported.
That is also the point at which a *Finder* becomes a *Reporter*.

The model keeps these states for completeness.
The [starting states](../../../reference/formal_protocol/states.md#starting-states) of the formal protocol use this fact.
They assume that a Finder/Reporter enters a case already in *Accepted*.

The diagram below separates the hidden states of the Finder from the states that other Participants can observe.

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
            R --> [*]
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

The diagram below shows a simple Finder-Vendor CVD scenario.
As explained [above](#the-secret-lives-of-finders), other Participants cannot see most states of the Finder until the Finder reaches the *Accepted* ($A_f$) state.
The *receive* action $A_f \xrightarrow{r} R_v$ connects the two Participants, and it is an instance of [participants interacting from the accepted state](index.md#participants-interact-from-the-accepted-state).
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

The next diagram shows a slightly more complex scenario.
In it, a Finder fails to engage a Vendor and then engages a Coordinator.
This scenario is very common in the experience of the CERT Coordination Center (CERT/CC).
That is no surprise, because as a Coordinator the CERT/CC does not take part in cases like the previous example.
This scenario has three notification actions, and each one is an instance of [participants interacting from the accepted state](index.md#participants-interact-from-the-accepted-state):

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

The diagram below shows a small Multi-Party Coordinated Vulnerability Disclosure (MPCVD) scenario.
As in the other examples, each notification is an instance of [participants interacting from the accepted state](index.md#participants-interact-from-the-accepted-state).
Unlike the previous example, this scenario starts when the Finder contacts a Coordinator.
One possible reason is that the Finder knows that coordination of many Vendors is more complex.

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

Other configurations of MPCVD RM interactions are possible, and the figures below show some of them.
In these figures, each node is the full RM model of one Participant.
Each edge is a notification from the *Accepted* state of one Participant to the *Received* state of another.
The CERT/CC has observed all of the following interactions.
The RM model is designed to be composable enough to include all such permutations.

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

Supply-chain oriented MPCVD often has two or more tiers of Vendors.
The upstream Vendors notify the Vendors that use their components.
One or more Coordinators can also take part.

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
