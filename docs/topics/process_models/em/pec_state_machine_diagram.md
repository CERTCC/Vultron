```mermaid
---
title: Participant Embargo Consent State Machine (one row per participant and embargo)
---
stateDiagram-v2
    direction LR
    [*] --> UNINVITED
    UNINVITED --> INVITED: INVITE
    UNINVITED --> AGREED: AGREE
    UNINVITED --> DECLINED: DECLINE
    INVITED --> AGREED: AGREE
    INVITED --> DECLINED: DECLINE
    INVITED --> TIMED_OUT: TIME_OUT
    AGREED --> DECLINED: DECLINE
    DECLINED --> INVITED: INVITE
    DECLINED --> AGREED: AGREE
    TIMED_OUT --> INVITED: INVITE
    TIMED_OUT --> AGREED: AGREE
    TIMED_OUT --> DECLINED: DECLINE
```

The diagram shows the five states of one consent row and the triggers `INVITE`, `AGREE`, `DECLINE` and `TIME_OUT` that move it.
`CARRY_OVER` also moves every state except `AGREED` to `AGREED`, when the case owner activates a revision that ends no later than the embargo it replaces; those edges are omitted for legibility.
No state is terminal: a row stops accepting triggers when its embargo's register entry reaches a final status.
