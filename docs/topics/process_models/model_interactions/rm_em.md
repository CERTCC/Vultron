# Interactions Between the RM and EM Models

{% include-markdown "../../../includes/normative.md" %}

There are additional constraints on how the [RM](../rm/index.md) and [EM](../em/index.md) processes interact.

## Start Embargo Negotiations As Early as Possible

A Sender often wants to know the embargo terms *before* handing over a report.
The protocol serves that need, but not by running the EM process ahead of the
report. The EM process is *per case*, so before a case exists there is no EM
state machine for a transition to occur in.

Two mechanisms give the Sender what they need instead:

1. **Read the Recipient's published default.** A Report Recipient's published
   default embargo period is a
   [standing proposal](../em/defaults.md#embargoes-are-active-at-case-creation).
   A Sender can know the terms in advance by reading it, with no exchange at all.
   Where the Recipient has published nothing, the short
   [protocol default](../em/defaults.md#no-defaults-no-proposals-the-protocol-default)
   applies, so the Sender still knows the floor.

2. **State terms with the report.** A Sender proposes its own terms by including
   a proposed embargo with the report submission. Where the two differ, the
   [shortest proposal wins](../em/defaults.md#rationale-for-accepting-the-shortest-proposed-embargo)
   and the longer becomes a proposed revision — so agreement is reached at case
   creation rather than negotiated beforehand.

!!! note ""

    The [EM](../em/index.md) process SHALL NOT begin before a case exists. A
    Sender that wishes to fix terms before sharing a report SHALL either rely on
    the Recipient's published default embargo period or include a proposed
    embargo with the report submission.

!!! info "This Guidance Changed"

    Earlier versions of this page stated that the EM process MAY begin — the
    initial _propose_ transition $q^{em} \in N \xrightarrow{p} P$ — prior to the
    report being sent to a potential Participant ($q^{rm} \in S$). ADR-0096
    withdrew that.

    The **motivation** was sound and is preserved above: a Participant may well
    wish to ensure acceptable embargo terms before sharing a report with a
    potential recipient. The **mechanism** was not. EM is a global per-case state
    machine, so a $N \xrightarrow{p} P$ transition before any case exists names a
    machine instance that cannot exist. The two mechanisms above deliver the same
    assurance without a pre-case phase.

!!! note ""

    The [EM](../em/index.md) process SHALL begin when a recipient reaches RM _Received_
    ($q^{rm} \in R$), because that is when the case exists. For an embargo-eligible case
    this is not merely a SHOULD: an embargo is established at case creation, from the
    Recipient's published default, the Sender's proposal, or the
    [protocol default](../em/defaults.md#no-defaults-no-proposals-the-protocol-default).

```mermaid
stateDiagram-v2
    direction LR
    state RM {
        Received
    }
    state EM {
        None --> Proposed : propose
        Proposed --> Active : accept
    }
    RM --> EM : begin at<br/>case creation
```

The *propose* and *accept* transitions above are applied atomically at case creation
and the intermediate *Proposed* state is never externally observable
([EP-04-002](../em/defaults.md#why-active-and-not-proposed)).

## Negotiate Embargoes for Active Reports

!!! note ""

    Embargo Management MAY begin in any of the active RM states
    ($q^{rm} \in \{ R,V,A \}$).

```mermaid
stateDiagram-v2
    direction LR
    state RM {
        Received
        Valid
        Accepted
    }
    state EM {
        None --> Proposed : propose
    }
    RM --> EM : ok to<br/>proceed
```

!!! note ""

    Embargo Management SHOULD NOT begin in an inactive RM state
    ($q^{rm} \in \{ I,D,C \}$).

```mermaid
stateDiagram-v2
    direction LR
    state RM {
        Invalid
        Deferred
        Closed
    }
    state EM {
        None --> Proposed : propose
    }
    RM --> EM : avoid
```

## Negotiate Embargoes Through Validation and Prioritization

!!! note ""

    Embargo Management MAY run in parallel to validation
    ($q^{rm} \in \{R,I\} \xrightarrow{\{v,i\}} \{V,I\}$) and
    prioritization ($q^{rm} \in V \xrightarrow{\{a,d\}} \{A,D\}$)
    activities.

## Renegotiate Embargoes While Reports Are Valid Yet Unclosed

!!! note ""

    EM revision proposals ($q^{em} \in A \xrightarrow{p} R$) and
    acceptance or rejection of those proposals
    (${q^{em} \in R \xrightarrow{\{a,r\}} A}$) MAY occur during any of
    the valid yet unclosed RM states (${q_{rm} \in \{ V,A,D \} }$).

```mermaid
stateDiagram-v2
    direction LR
    state RM {
        Valid
        Accepted
        Deferred
    }
    state EM {
        Revise --> Active : accept
        Revise --> Active : reject
        Active --> Revise : propose
    }
    RM --> EM : ok to<br/>proceed
```

## Avoid Embargoes for Invalid Reports

!!! note ""

    Embargo Management SHOULD NOT begin with a proposal from a
    Participant in RM _Invalid_ ($q^{rm} \in I$).

```mermaid
stateDiagram-v2
    direction LR
    state RM {
        Invalid
    }
    state EM {
        None --> Proposed : propose
    }
    RM --> EM : avoid
```

## ...but Don't Lose Momentum if Validation Is Pending

!!! note ""

    Outstanding embargo negotiations
    ($q^{em} \in P \xrightarrow{\{r,p\}} \{N,P\}$) MAY continue in
    RM _Invalid_
    ($q^{rm} \in I$) (e.g., if it is anticipated that additional
    information may be forthcoming to promote the report from _Invalid_
    to _Valid_) ($q^{rm} \in I \xrightarrow{v} V$).

```mermaid
stateDiagram-v2
    direction LR
    state RM {
        Invalid --> Valid: (anticipated)
    }
    state EM {
        None --> Propose : propose
    }
    RM --> EM : ok to<br/>proceed
```

## Only Accept Embargoes for Possibly Valid Yet Unclosed Reports

!!! note ""

    Embargo Management MAY proceed from EM _Proposed_ to EM _Accepted_
    ($q^{em} \in P \xrightarrow{a} A$) when RM is neither _Invalid_ nor _Closed_
    ($q^{rm} \in \{R,V,A,D\}$).

```mermaid
stateDiagram-v2
    direction LR
    state RM {
        Start
        Received
        Valid
        Accepted
        Deferred
    }
    state EM {
        Proposed --> Accepted : accept
    }
    RM --> EM : ok to<br/>proceed
```

!!! note ""

    Embargo Management SHOULD NOT proceed from EM _Proposed_ to EM _Accepted_ when
    RM is _Invalid_
    or _Closed_ ($q^{rm} \in \{I,C\}$).

```mermaid
stateDiagram-v2
    direction LR
    state RM {
        Invalid
        Closed
    }
    state EM {
        Proposed --> Accepted : accept
    }
    RM --> EM : avoid
```

!!! note ""

    Embargo Management MAY proceed from EM _Proposed_ to EM _None_
    ($q^{em} \in P \xrightarrow{r} N$) when RM is _Invalid_ or _Closed_.

```mermaid
stateDiagram-v2
    direction LR
    state RM {
        Invalid
        Closed
    }
    state EM {
        Proposed --> None : reject
    }
    RM --> EM : ok to<br/>proceed
```

## Report Closure, Deferral, and Active Embargoes

Participants' individual Report Management processes can interact with the Embargo Management process at the case level
in a number of ways.
We describe these interactions below.

!!! note ""

    Participants SHOULD NOT close reports ($q^{rm} \in \{I,D,A\} \xrightarrow{c} C$) while an embargo is
    active ($q^{em} \in \{ A,R \}$).

```mermaid
stateDiagram-v2
    direction LR
    state RM {
        Invalid --> Closed: close
        Deferred --> Closed: close
        Accepted --> Closed: close
    }
    state EM {
        Active
        Revise
    }
    EM --> RM : avoid
```

Instead,

!!! note ""
  
    Reports with no further tasks SHOULD be held in either
    _Deferred_ or _Invalid_ (${q^{rm} \in \{ D,I\}}$) (depending on the
    report validity status) until the embargo has terminated
    (${q^{em} \in X}$).

This allows Participants to stop work on a report but still maintain their participation in an extant embargo.
Notwithstanding the above,

!!! note ""

    Participants who choose to close a report ($q^{rm} \in \{I,D,A\} \xrightarrow{c} C$) while an embargo remains
    in force ($q^{em} \in \{A,R\}$) SHOULD communicate their intent to either continue to adhere to the embargo or 
    terminate their compliance with it.

Report closure or deferral alone does not terminate an embargo.

!!! note ""

    A Participant's closure or deferral ($q^{rm} \in \{C,D\}$) of a report
    while an embargo remains active ($q^{em} \in \{A,R\}$) and while
    other Participants remain engaged ($q^{rm} \in \{R,V,A\}$) SHALL NOT
    automatically terminate the embargo.

```mermaid
stateDiagram-v2
    direction LR
state RM {
        Invalid --> Closed: close
        Deferred --> Closed: close
        Accepted --> Closed: close
    }
    state EM {
        Active --> eXited: terminate
        Revise --> eXited: terminate
    }
    RM --> EM : does not imply
```

It is expected that Participants will continue to adhere to the embargo until it is explicitly terminated.
However,

!!! note ""

    Participants MAY choose to terminate their compliance with an embargo at any time.

While this is usually an undesirable development, it must be communicated to other Participants
so that they can make informed decisions about the viability of the extant embargo.

!!! note ""

    Any changes to a Participant's intention to adhere to an active
    embargo SHOULD be communicated in addition to any necessary
    notifications regarding RM or EM state changes.

!!! note ""

    Upon receipt of a Participant's notification of intent to end their compliance with an embargo,
    other Participants MAY choose to terminate the embargo.
