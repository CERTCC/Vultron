# Interactions Between the RM and EM Models {#sec:rm_em_interactions}

There are additional constraints on how the [RM](../rm/) and [EM](../em/) processes interact.

## Start Embargo Negotiations As Early as Possible

!!! note ""

    The [EM](../em/) process
    MAY begin (i.e., the initial _propose_ transition
    $q^{em} \in N \xrightarrow{p} P$) prior to the report being sent to
    a potential Participant ($q^{rm} \in S$), for example, when a
    Participant wishes to ensure acceptable embargo terms prior to
    sharing a report with a potential recipient.

```mermaid
stateDiagram-v2
    direction LR
    state ParticipantSpecific {
        state Sender {
            state RM {
                Accepted
            }
        }
        state Recipient {
            RM2: RM
            state RM2 {
                Start
            }
        }
    }
    state Global {
        state EM {
            None --> Proposed : propose
        }
    }
    Sender --> EM : propose
```

!!! note ""

    If it has not already begun, the [EM](../em/) process SHOULD begin when a recipient
    is in RM _Received_ ($q^{rm} \in R$) whenever possible.


```mermaid
stateDiagram-v2
    direction LR
    state RM {
        Received
    }
    state EM {
        None --> Proposed : propose
    }
    RM --> EM : begin if not<br/>already started
```

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

## Avoid Embargoes for Invalid Reports...

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

!!! note ""

    Participants SHOULD NOT close reports
    ($q^{rm} \in \{I,D,A\} \xrightarrow{c} C$) while an embargo is
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


!!! note ""
  
    Instead, reports with no further tasks SHOULD be held in either
    _Deferred_ or _Invalid_ (${q^{rm} \in \{ D,I\}}$) (depending on the
    report validity status) until the embargo has terminated
    (${q^{em} \in X}$). This allows Participants to stop work on a
    report but still maintain their participation in an extant embargo.

!!! note ""

    Notwithstanding, Participants who choose to close a report
    ($q^{rm} \in \{I,D,A\} \xrightarrow{c} C$) while an embargo remains
    in force ($q^{em} \in \{A,R\}$) SHOULD communicate their intent to
    either continue to adhere to the embargo or terminate their
    compliance with it.

!!! note ""
  
    Report closure or deferral does not terminate an embargo. A
    Participant's closure or deferral ($q^{rm} \in \{C,D\}$) of a report
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
    

!!! note ""

    Any changes to a Participant's intention to adhere to an active
    embargo SHOULD be communicated clearly in addition to any necessary
    notifications regarding RM or EM state changes.
