# Report Management Interactions Between CVD Participants

Each Participant in a case has their own instance of the RM state model.
Participants can change their local state independent of the state of other Participants.
Events within a CVD case may trigger a state transition in one Participant while no transition occurs in another.
For example, in [particpants interact from the accepted state](#participants-interact-from-the-accepted-state) we showed
that even though the _sender_ is the one taking the action, it is the _recipient_'s state that changes.
The table below lists role-based actions. 

| Finder/Reporter  |      Vendor       |    Coordinator    | Action                                  | RM Transition  |
|:----------------:|:-----------------:|:-----------------:|-----------------------------------------|:-------------:|
| :material-check: |                   |                   | Discover Vulnerability (hidden)         |            |
| :material-check: |                   |                   | Analyze Discovery (hidden)              |            |
| :material-check: |                   |                   | Decide whether to initiate CVD (hidden) |            |
| :material-check: | :material-check: | :material-check: | Notify Vendor                           |            |
| :material-check: | :material-check: | :material-check: | Notify Coordinator                      |            |
|         | :material-check: | :material-check: | Receive Report                          |            |
|         | :material-check: | :material-check: | Validate Report                         |            |
| :material-check: | :material-check: | :material-check: | Prioritize Report                       |            |
| :material-check: | :material-check: | :material-check: | Pause Work                              |            |
| :material-check: | :material-check: | :material-check: | Resume Work                             |            |
| :material-check: | :material-check: | :material-check: | Close Report                            |            |

A few examples of this model applied to common CVD and MPCVD case scenarios follow.

## The Secret Lives of Finders

While the Finder's _Received_, _Valid_, and _Invalid_ states are useful
for modeling and simulation purposes, they are less useful to us as part
of a potential CVD protocol. Why? Because for anyone else to know about the vulnerability
(and as a prerequisite to CVD happening at all), the Finder must have
already validated the report and prioritized it as worthy of further
effort to have any reason to attempt to coordinate its disclosure. In
other words, CVD only starts *after* the Finder has already reached the
_Accepted_ state for any given vulnerability to be reported.
Correspondingly, this also represents their transition from *Finder* to
*Reporter*. Nevertheless, for now, we retain these states for
completeness. We revisit this topic in our derivation of a protocol
state model for Reporters in
{== §[\[sec:other_participants\]](#sec:other_participants){reference-type="ref"
reference="sec:other_participants"} ==}.

```mermaid
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


## Finder-Vendor CVD.

A simple Finder-Vendor CVD scenario is shown below.
As explained [above](#the-secret-lives-of-finders), many of the Finder's states would be
hidden from view until they reach the _Accepted_ ($A_f$) state. The
_receive_ action bridging $A_f \xrightarrow{r} R_v$ corresponds to the
[participants interact from the accepted state](#participants-interact-from-the-accepted-state) scenario above.

```mermaid
stateDiagram-v2
    direction LR
    state Finder {
        direction LR
        R: R<sub>f</sub>
        I: I<sub>f</sub>
        V: V<sub>f</sub>
        A: A<sub>f</sub>
        D: D<sub>f</sub>
        [*] --> R
        R --> I
        R --> V
        I --> V
        V --> A
        V --> D
        A --> D
        D --> A
        D --> [*]
        A --> [*]
        I --> [*]
    }
    state Vendor {
        direction LR
        RV:R<sub>v</sub>
        IV:I<sub>v</sub>
        VV:V<sub>v</sub>
        AV:A<sub>v</sub>
        DV:D<sub>v</sub>
        [*] --> RV
        RV --> IV
        RV --> VV
        IV --> VV
        VV --> AV
        VV --> DV
        AV --> DV
        DV --> AV
        DV --> [*]
        AV --> [*]
        IV --> [*]
    }
    A --> RV: r
```

## Finder-Coordinator-Vendor CVD.

A slightly more complicated scenario in which a Finder engages a
Coordinator after failing to engage a Vendor is shown in the next diagram.
This scenario is very common in our
experience at the CERT/CC, which should come as no surprise
considering our role as a Coordinator means that we do not participate
in cases following the previous example. Here we see three notification
actions corresponding to [participants interacting from the accepted state](#participants-interact-from-the-accepted-state):

-   First, $A_f \xrightarrow{r_0} R_v$ represents the Finder's initial
    attempt to reach the Vendor.

-   Next, $A_f \xrightarrow{r_1} R_c$ is the Finder's subsequent attempt
    to engage with the Coordinator.

-   Finally, the Coordinator contacts the Vendor in
    $A_c \xrightarrow{r_2} R_v$.

```mermaid
stateDiagram-v2
    direction LR
    state Finder {
        direction LR
        R: R<sub>f</sub>
        I: I<sub>f</sub>
        V: V<sub>f</sub>
        A: A<sub>f</sub>
        D: D<sub>f</sub>

        [*] --> R
        R --> I
        R --> V
        I --> V
        V --> A
        V --> D
        A --> D
        D --> A
        D --> [*]
        A --> [*]
        I --> [*]
    }
    state Coordinator {
        direction LR
        RC:R<sub>c</sub>
        IC:I<sub>c</sub>
        VC:V<sub>c</sub>
        AC:A<sub>c</sub>
        DC:D<sub>c</sub>
        [*] --> RC
        RC --> IC
        RC --> VC
        IC --> VC
        VC --> AC
        VC --> DC
        AC --> DC
        DC --> AC
        DC --> [*]
        AC --> [*]
        IC --> [*]
    }
    state Vendor {
        direction LR
        RV:R<sub>v</sub>
        IV:I<sub>v</sub>
        VV:V<sub>v</sub>
        AV:A<sub>v</sub>
        DV:D<sub>v</sub>
        [*] --> RV
        RV --> IV
        RV --> VV
        IV --> VV
        VV --> AV
        VV --> DV
        AV --> DV
        DV --> AV
        DV --> [*]
        AV --> [*]
        IV --> [*]
    }
    A --> RV: r0
    A --> RC: r1
    AC --> RV: r2
```


## MPCVD with a Coordinator and Multiple Vendors.

A small MPCVD scenario is shown below. As with the other examples, each
notification shown is an instance of [participants interacting from the accepted state](#participants-interact-from-the-accepted-state).
Contrary to the previous example, this scenario starts with the Finder contacting a Coordinator, perhaps
because they recognize the increased complexity of coordinating multiple Vendors' responses.

-   First, $A_f \xrightarrow{r_0} R_c$ represents the Finder's initial
    report to the Coordinator.

-   Next, $A_c \xrightarrow{r_1} R_{v_1}$ shows the Coordinator
    contacting the first Vendor.

-   Finally, the Coordinator contacts a second Vendor in
    $A_c \xrightarrow{r_2} R_{v_2}$.

```mermaid
stateDiagram-v2
    direction LR
    state Finder {
        direction LR
        R: R<sub>f</sub>
        I: I<sub>f</sub>
        V: V<sub>f</sub>
        A: A<sub>f</sub>
        D: D<sub>f</sub>
        [*] --> R
        R --> I
        R --> V
        I --> V
        V --> A
        V --> D
        A --> D
        D --> A
        D --> [*]
        A --> [*]
        I --> [*]
    }
    state Coordinator {
        direction LR
        RC:R<sub>c</sub>
        IC:I<sub>c</sub>
        VC:V<sub>c</sub>
        AC:A<sub>c</sub>
        DC:D<sub>c</sub>
        [*] --> RC
        RC --> IC
        RC --> VC
        IC --> VC
        VC --> AC
        VC --> DC
        AC --> DC
        DC --> AC
        DC --> [*]
        AC --> [*]
        IC --> [*]
    }
    state Vendor {
        direction LR
        RV:R<sub>v<sub>1</sub></sub>
        IV:I<sub>v<sub>1</sub></sub>
        VV:V<sub>v<sub>1</sub></sub>
        AV:A<sub>v<sub>1</sub></sub>
        DV:D<sub>v<sub>1</sub></sub>
        [*] --> RV
        RV --> IV
        RV --> VV
        IV --> VV
        VV --> AV
        VV --> DV
        AV --> DV
        DV --> AV
        DV --> [*]
        AV --> [*]
        IV --> [*]
    }
    state Vendor2 {
        direction LR
        RV2:R<sub>v<sub>2</sub></sub>
        IV2:I<sub>v<sub>2</sub></sub>
        VV2:V<sub>v<sub>2</sub></sub>
        AV2:A<sub>v<sub>2</sub></sub>
        DV2:D<sub>v<sub>2</sub></sub>
        [*] --> RV2
        RV2 --> IV2
        RV2 --> VV2
        IV2 --> VV2
        VV2 --> AV2
        VV2 --> DV2
        AV2 --> DV2
        DV2 --> AV2
        DV2 --> [*]
        AV2 --> [*]
        IV2 --> [*]
    }
    A --> RC: r0
    AC --> RV: r1
    AC --> RV2: r2
```


## A Menagerie of MPCVD Scenarios.

Other MPCVD RM interaction configurations are possible, of course. We demonstrate a few such
scenarios in the following figures.
This time each node represents a Participant's entire RM model. We have observed all of the
following interactions at the CERT/CC.
We intend the RM model to be sufficiently composable to accommodate all such permutations.


### Finder coordinates MPCVD with Multiple Vendors

A Finder notifies multiple Vendors without engaging a Coordinator.

```mermaid
stateDiagram-v2
    direction LR
    Finder --> Vendor1: r0
    Finder --> Vendor2: r1
    Finder --> Vendor3: r2
```

### Vendor coordinates MPCVD 

A Finder notifies a Vendor, who, in turn, notifies other Vendors.

```mermaid
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
stateDiagram-v2
    direction LR
    Finder --> Vendor1: r0
    Vendor1 --> Coordinator: r1
    Coordinator --> Vendor2: r2
    Coordinator --> Vendor3: r3
    Coordinator --> Vendor4: r4
```

### Supply-chain oriented MPCVD.

Supply-chain oriented MPCVD often has two or more tiers of
Vendors being notified by their upstream component suppliers, with
or without one or more Coordinators' involvement.

```mermaid
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

