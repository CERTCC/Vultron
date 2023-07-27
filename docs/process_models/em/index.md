# Embargo Management Process Model

!!! note "TODO"
    - [x] regex replace acronym pointers with the acronym
    - [ ] replace first use of an acronym on a page with its expansion (if not already done)
    - [ ] OR replace acronym usage with link to where it's defined
    - [ ] reproduce diagrams using mermaid
    - [ ] replace text about figures to reflect mermaid diagrams
    - [ ] replace latex tables with markdown tables
    - [ ] replace some equations with diagrams (especially for equations describing state changes)
    - [ ] move latex math definitions into note blocks `???+ note _title_` to offset from text
    - [ ] move MUST SHOULD MAY etc statements into note blocks with empty title `!!! note ""` to offset from text
    - [ ] revise cross-references to be links to appropriate files/sections
    - [ ] replace latex citations with markdown citations (not sure how to do this yet)
    - [ ] review text for flow and readability as a web page
    - [ ] add section headings as needed for visual distinction
    - [ ] add links to other sections as needed
    - [ ] add links to external resources as needed
    - [ ] replace phrases like `this report` or `this section` with `this page` or similar
    - [ ] add `above` or `below` for in-page cross-references if appropriate (or just link to the section)
    - [ ] reduce formality of language as needed
    - [ ] move diagrams to separate files and `include-markdown` them

In this chapter, we describe the basic primitives necessary for the
CVD Embargo Management (EM) process. For our purposes, an embargo is an *informal* agreement among peer
CVD case Participants to refrain from publishing information about a vulnerability until some future point in time relative to the report at
hand. Once an embargo has expired, there is no further restriction on
publishing information about the vulnerability.

!!! tip inline end "Reminder"

    Exploits are information about vulnerabilities too.


CVD case Participants must be able to propose, accept, and reject embargo timing
proposals according to their individual needs. Additionally,
Participants may want to attempt to gain agreement that enables specific
details about a vulnerability to be shared with other Participants or
made public. Such content considerations are outside the scope of this
proposal. We focus our discussion on the *when* of an embargo, not the
*what*.

Unlike the [RM](../rm/) model, in which each Participant has their own instance of the
[RM](../rm/) DFA, EM states are a global property of a CVD case. 

!!! note ""
    A CVD case SHALL NOT have more than one active embargo at a time.

Even in an MPCVD case having a [vertical supply chain](https://vuls.cert.org/confluence/display/CVD/5.4+Multiparty+CVD)
---in which Vendors must wait on their upstream suppliers to produce fixes before they can take action on
their own, as in {== Figure [\[fig:mpcvd_supply_chain\]](#fig:mpcvd_supply_chain){reference-type="ref"
reference="fig:mpcvd_supply_chain"} ==} ---our intent is that the embargo
period terminates when as many Vendors as possible have been given an
adequate opportunity to produce a fix.

{% include-markdown "nda-sidebar.md" %}

## EM State Machine

As with our definition of the [RM](../rm/) model, we describe our
EM model using DFA notation.

{% include-markdown "../dfa_notation_definition.md" %}

### EM States

CVD cases are either subject to an active embargo or they are not. 
We begin with a simple two-state model for the embargo state:

```mermaid
stateDiagram-v2
    direction LR
    [*] --> None
    None --> Active
    Active --> [*]
```

However, because embargo management is a process of coordinating across
Participants, it will be useful to distinguish between the _None_ state
and an intermediate state in which an embargo has been proposed but not
yet accepted or rejected. We might call this the _None + Proposed_
state, but we shortened it to _Proposed_.

Similarly, we want to be able to discriminate between an _Active_
embargo state and one in which a revision has been proposed but is not
yet accepted or rejected, which we will denote as the _Active + Revise_
state, shortened to _Revise_. Finally, we wish to distinguish between
the state in which no embargo has ever been established (_None_), and
the final state after an active embargo has ended (_eXited_). Combining
these, we get the following set of EM states, which we denote as
$\mathcal{Q}^{em}$.

???+ note inline end "EM States ($\mathcal{Q}^{em}$) Defined"
    $\label{eq:em_states}
    \begin{split}
        \mathcal{Q}^{em} = \{ & \underline{N}one, \\
        & \underline{P}roposed, \\
        & \underline{A}ctive, \\
        & \underline{R}evise, \\
        & e\underline{X}ited \}
    \end{split}$

As a reminder, we use the underlined capital letters as shorthand for
EM state names later in the document. Also note that $q^{em} \in A$ is distinct from
$q^{rm} \in A$. An embargo can be _Active_, while a Report can be
_Accepted_, and these are independent states. Be sure to check which
model a state's shorthand notation is referring to.

```mermaid
stateDiagram-v2
    direction LR
    [*] --> None
    None --> Proposed
    Proposed --> None
    Proposed --> Active
    Active --> Revise
    Revise --> Active
    Revise --> eXited
    Active --> eXited
    eXited --> [*]
```

##### Start and Final States.

???+ note inline end "EM Start and Final States Defined"
    $q^{em}_0 = None$
    
    $\mathcal{F}^{em} = \{None,~eXited\}$

The EM process starts in the _None_ state. The process ends in one of two states: If an
embargo agreement is eventually reached, the EM process ends in the _eXited_ state.
Otherwise, if no agreement is ever reached, the EM process ends in the _None_ state. Formal
definitions of each are shown in the box at right.


### EM State Transitions

{% include-markdown "em_dfa_diagram.md" %}

The symbols of our EM DFA are the actions that cause transitions
between the states:

!!! note ""
    An embargo MAY be _proposed_.

!!! note ""
    Once proposed, it MAY be _accepted_ or _rejected_.

!!! note ""
    Once accepted, revisions MAY be _proposed_, which MAY, in turn, be
    _accepted_ or _rejected_.

!!! note ""
    Finally, accepted embargoes MUST eventually _terminate_.

A summary of the available actions is shown as $\Sigma^{em}$ below.

???+ note "EM Symbols ($\Sigma^{em}$) Defined"
    $\label{eq:em_symbols}
        \begin{split}
            \Sigma^{em} = \{
             ~\underline{p}ropose, 
             ~\underline{r}eject, 
             ~\underline{a}ccept, 
             ~\underline{t}erminate
            \}
        \end{split}$

Once again, the underlined lowercase letters will be used as shorthand
for the EM
transition names in the remainder of the document.

#### EM Transitions Defined

Now we define the possible state transitions. Figure
[\[fig:em_states_dense\]](#fig:em_states_dense){reference-type="ref"
reference="fig:em_states_dense"} summarizes the EM process DFA states and transitions.

{% include-markdown "./em_dfa_diagram.md" %}

##### Propose Embargo

Propose a new embargo when none exists:

```mermaid
stateDiagram-v2
    direction LR
    dots: ...
    [*] --> None
    None --> Proposed: propose
    Proposed --> dots
    dots --> [*]
```


##### Accept or Reject Embargo Proposal

Accept or reject a proposed embargo:

```mermaid
stateDiagram-v2
    direction LR
    [*] --> None
    None --> Proposed
    state Proposed {
        direction LR
        eval: Accept or reject?
        state choose <<choice>>
        [*] --> eval
        eval --> choose
    }
    choose --> Active: accept
    choose --> None: reject
```

##### Embargo Revision

An existing embargo can also be renegotiated by proposing a new embargo.
The existing embargo remains active until it is replaced by accepting
the revision proposal.
If the newly proposed embargo is accepted, then the old one is
abandoned. On the other hand, if the newly proposed embargo is rejected,
the old one remains accepted.

```mermaid
stateDiagram-v2
    direction LR
    dots: ...
    [*] --> dots
    dots --> Active 
    state Revise {
        direction LR
        state choose <<choice>>
        eval: Change embargo?
        [*] --> eval
        eval --> choose
    }
    Active --> Revise: revise
    choose --> Active: accept
    choose --> Active: reject
```

##### Terminate Embargo

Existing embargoes can terminate due to timer expiration or other
reasons to be discussed in
{== §[1.2.7](#sec:early_termination){reference-type="ref"
reference="sec:early_termination"} ==}. Termination can occur even if there
is an open revision proposal.

```mermaid
stateDiagram-v2
    direction LR
    dots: ...
    [*] --> dots
    dots --> Active
    dots --> Revise
    Active --> eXited: terminate
    Revise --> eXited: terminate
    eXited --> [*]
```

#### A Regular Grammar for EM {#sec:em_grammar}

Based on the actions and corresponding state transitions just described,
we define the transition function $\delta^{em}$ for the
EM process as a set
of production rules for the right-linear grammar using our
single-character shorthand in
[\[eq:em_transition_function\]](#eq:em_transition_function){reference-type="eqref"
reference="eq:em_transition_function"}.

???+ note inline end "EM Transition Function ($\delta^{em}$) Defined"
    $\label{eq:em_transition_function}
        \delta^{em} = 
        \begin{cases}
            % \epsilon \to & N \\
                   N \to ~pP~|~\epsilon \\
                   P \to ~pP~|~rN~|~aA \\
                   A \to ~pR~|~tX \\
                   R \to ~pR~|~aA~|~rA~|~tX \\
                   X \to ~\epsilon \\
        \end{cases}$

Due to the numerous loops in the DFA shown in Figure
[\[fig:em_states_dense\]](#fig:em_states_dense){reference-type="ref"
reference="fig:em_states_dense"}, the EM grammar is capable of generating
arbitrarily long strings of _propose_-_propose_ and _propose_-_reject_
histories matching the regular expression `(p*r)*(pa(p*r)*(pa)?t)?`. As
an example, here is an exhaustive list of all the possible traces of
length seven or fewer:

> _pr_, _pat_, _ppr_, _ppat_, _papt_, _prpr_, _pppr_, _ppppr_, _pprpr_,
> _prppr_, _pappt_, _ppapt_, _pppat_, _papat_, _paprt_, _prpat_,
> _pppppr_, _papppt_, _prpppr_, _ppprpr_, _ppappt_, _pppapt_, _prprpr_,
> _papapt_, _pprppr_, _pappat_, _paprpt_, _prppat_, _prpapt_, _ppaprt_,
> _pprpat_, _ppapat_, _papprt_, _ppppat_, _pprprpr_, _prprppr_,
> _paprppt_, _prpprpr_, _pappprt_, _papppat_, _ppppapt_, _prpaprt_,
> _papappt_, _pappapt_, _pppappt_, _pprpppr_, _pppprpr_, _prppppr_,
> _ppprppr_, _ppapppt_, _ppaprpt_, _papprpt_, _ppapprt_, _ppappat_,
> _prpppat_, _prpapat_, _ppprpat_, _ppppppr_, _pprppat_, _papapat_,
> _paprpat_, _ppapapt_, _prprpat_, _paprprt_, _prppapt_, _pppapat_,
> _pprpapt_, _pppaprt_, _pppppat_, _prpappt_, _papaprt_, _pappppt_

However, because EM
is a human-oriented scheduling process, our experience suggests that we
should expect there to be a natural limit on CVD Participants' tolerance for churn during
embargo negotiations. Hence, we expect most paths through the
EM DFA to be on the short end of this list in practice. We offer some thoughts on a
potential reward function over EM DFA strings in [Future Work](../../future_work.md).

For example, it is often preferable for a Vendor to accept whatever
embargo the Reporter initially proposes followed closely by proposing a
revision to their preferred timeline than it is for the Vendor and
Reporter to ping-pong proposals and rejections without ever establishing
an embargo in the first place. In the worst case (i.e., where the
Reporter declines to extend their embargo), a short embargo is
preferable to none at all. This implies a preference for strings
starting with _par_ over strings starting with _ppa_ or _prpa_, among
others. We will come back to this idea in [Default Embargoes](#default-embargoes)
and in the [worked protocol example](../../formal_protocol/worked_example/#vendor-accepts-then-proposes-revision).

### EM DFA Fully Defined

Taken together, the complete DFA specification for the
EM process is shown below right.

???+ note "EM DFA $(\mathcal{Q},q_0,\mathcal{F},\Sigma,\delta)^{em}$ Fully Defined"

    $$EM = 
        \begin{pmatrix}
                \begin{aligned}
                    \mathcal{Q}^{em} = & \{ N,P,A,R,X \}, \\
                    q^{em}_0 = & N, \\
                    \mathcal{F}^{em} = &\{ N,X \},  \\
                    \Sigma^{em} = &\{ p,r,a,t \}, \\
                    \delta^{em} = &
                        \begin{cases}
                           N \to ~pP~|~\epsilon \\
                           P \to ~pP~|~rN~|~aA \\
                           A \to ~pR~|~tX \\
                           R \to ~pR~|~aA~|~rA~|~tX \\
                           X \to ~\epsilon \\
                        \end{cases}
                \end{aligned}
        \end{pmatrix}$$


### Default Embargoes

As described in {== §[1.1.2.2](#sec:em_grammar){reference-type="ref"
reference="sec:em_grammar"} ==}, the EM process has the potential for unbounded
*propose-reject* churn. To reduce the potential for this churn and
increase the likelihood that *some* embargo is established rather than a
stalemate of unaccepted proposals, we offer the following guidance.

##### Declaring Defaults.

First, we note that all CVD Participants (including Reporters) are
free to establish their own default embargo period in a published
vulnerability disclosure policy. In particular, we recommend that
CVD report
recipients (typically Vendors and Coordinators) do so.

!!! note ""  

    Participants MAY include a default embargo period as part of a
    published Vulnerability Disclosure Policy.

!!! note ""  

    Recipients SHOULD post a default embargo period as part of their
    Vulnerability Disclosure Policy to set expectations with potential
    Reporters.

##### Using Defaults.

Next, we work through the possible interactions of published policies
with proposed embargoes. Each of the following scenarios assumes a
starting state of $q^{em} \in N$, and a negotiation between two parties.
We cover the extended situation (adding parties to an existing embargo)
in [Inviting Others](#inviting-others-to-an-embargoed-case). For now, we begin with the simplest
case and proceed in an approximate order of ascending complexity.

In each of the following, subscripts on transitions indicate the
Participant whose proposal is being acted upon, not the Participant who
is performing the action. For example, $a_{sender}$ indicates acceptance
of the Sender's proposal, even if it is the Receiver doing the
accepting.

###### No Defaults, No Proposals

We begin with the simplest case, in which neither party has a default and no
embargo has been proposed.

```mermaid
stateDiagram-v2
    direction LR
    [*] --> N
```

!!! note ""  

    ???+ note inline end "Formalism"

        $$q^{em} \in N$$

    If neither Sender nor Receiver proposes an embargo, and no policy
    defaults apply, no embargo SHALL exist.


###### Sender Proposes When Receiver Has No Default Embargo

Next, we consider the case where the Sender has a default embargo or otherwise proposes an embargo
and the Receiver has no default embargo specified by policy.

```mermaid
stateDiagram-v2
    direction LR
    [*] --> N
    N --> P : sender proposes
    P --> A : receiver accepts
    A --> R : receiver proposes revision
```

!!! note ""  

    ???+ note inline end "Formalism"

        $$q^{em} \in N \xrightarrow{p_{sender}} P \xrightarrow{a_{sender}} A$$

    If the Sender proposes an embargo and the Receiver has no default
    embargo specified by policy, the Receiver SHOULD accept the Sender's
    proposal.


!!! note ""  

    ???+ note inline end "Formalism"

        $$q^{em} \in A \xrightarrow{p_{receiver}} R$$

    The Receiver MAY then propose a revision.


###### Receiver Has Default Embargo, Sender Implies Acceptance

The next scenario is where the Receiver has a default embargo specified by
policy and the Sender does not propose an embargo.

```mermaid
stateDiagram-v2
    direction LR
    [*] --> N
    N --> P : receiver default proposal
    P --> A : sender accepts
```


!!! note ""  

    ???+ note inline end "Formalism"

        $$q^{em} \in N \xrightarrow{p_{receiver}} P$$

    A Receiver's default embargo specified in its vulnerability
    disclosure policy SHALL be treated as an initial embargo proposal.


!!! note ""  

    ???+ note inline end "Formalism"

        $$q^{em} \in N \xrightarrow{p_{receiver}} P \xrightarrow{p_{sender}} P$$

    If the Receiver has declared a default embargo in its vulnerability
    disclosure policy and the Sender proposes nothing to the contrary,
    the Receiver's default embargo SHALL be considered as an accepted
    proposal.



###### Sender Proposes an Embargo Longer than the Receiver Default

Now we consider the case where the Sender proposes an embargo longer
than the Receiver's default.

```mermaid
stateDiagram-v2
    direction LR
    [*] --> N
    N --> P : receiver<br/>proposes<br/>default<br/>(shorter)
    P --> A : sender<br/>accepts<br/>(shorter)
    A --> R : sender<br/>proposes<br/>(longer)
    R --> A : receiver<br/>accepts<br/>(longer)
    R --> A : receiver rejects<br/>(shorter default persists)
```

!!! note ""  

    If the Sender proposes an embargo *longer* than the Receiver's
    default embargo, the Receiver's default SHALL be taken as accepted
    and the Sender's proposal taken as a proposed revision.

    ???+ note "Formalism"

        $$q^{em} \in N \xrightarrow{p_{receiver}} P \xrightarrow{p_{sender}} P \xrightarrow{a_{receiver}} A \xrightarrow{r_{sender}} R$$


!!! note ""  

    ???+ note inline end "Formalism"

        $$q^{em} \in \begin{cases}
            R \xrightarrow{a_{sender}} A \\
            R \xrightarrow{r_{sender}} A
            \end{cases}$$

    The Receiver MAY then *accept* or *reject* the proposed extension.


###### Sender Proposes an Embargo Shorter than the Receiver Default

Finally, we reach a common scenario in which the Sender proposes an
embargo shorter than the Receiver's default.

```mermaid
stateDiagram-v2
    direction LR
    [*] --> N
    N --> P : sender<br/>proposes<br/>(shorter)
    P --> A : receiver<br/>accepts<br/>(shorter)
    A --> R : receiver<br/>proposes<br/>(longer default)
    R --> A : sender<br/>accepts<br/>(longer default))
    R --> A : sender rejects<br/>(shorter persists)
```

!!! note ""  

    If the Sender proposes an embargo *shorter* than the Receiver's
    default embargo, the Sender's proposal SHALL be taken as accepted
    and the Receiver's default taken as a proposed revision.

    ???+ note "Formalism"
    
        $$q^{em} \in N \xrightarrow{p_{receiver}} P \xrightarrow{p_{sender}} P \xrightarrow{a_{sender}} A \xrightarrow{r_{receiver}} R$$


!!! note ""  

    ???+ note inline end "Formalism"

        $$q^{em} \in \begin{cases}
            R \xrightarrow{a_{receiver}} A \\
            R \xrightarrow{r_{receiver}} A
            \end{cases}$$

    The Sender MAY then *accept* or *reject* the proposed extension.


!!! info "A Game Theory Argument for Accepting the Shortest Proposed Embargo"

    Readers may notice that we have taken a _shortest proposal wins_
    approach to the above guidance. This is intentional, and it results
    directly from the asymmetry mentioned in
    [Negotiating Embargoes](#negotiating-embargoes)
    The Receiver is faced with a
    choice to either *accept* the Reporter's proposal and attempt to extend
    it or to *reject* the proposal and end up with no embargo at all.
    Therefore, if we take the stance that for a vulnerability with no fix
    available, *any* embargo is better than *no* embargo, it should be
    obvious that it is in the Receiver's interest to *accept* even a short
    proposed embargo before immediately working to revise it.
    
    The alternative is impractical because the Reporter is not obligated to
    provide the report to the Receiver at all. In the scenario where a
    Reporter *proposes* a short embargo and the Receiver *rejects* it
    because it is not long enough, the Reporter might choose to exit the
    negotiation entirely and publish whenever they choose without ever
    providing the report to the Receiver. That is not to say that we
    recommend this sort of behavior from Reporters. In fact, we specifically
    recommend the opposite in
    [Negotiating Embargoes](#negotiating-embargoes). Rather, it once more
    acknowledges the time-dependent informational asymmetry inherent to the
    CVD process.

!!! info "A Logical Argument for Accepting the Shortest Proposed Embargo"

    Perhaps the above reasoning comes across as too Machiavellian for some
    readers. Here is a different perspective: Say a Reporter proposes an
    embargo of _n_ days, while the Vendor would prefer _m_ days. If _n_ and
    _m_ are given in units of days, we can look at them as a series of
    individual agreements, each of 1 day in length. We will represent each
    Participant as a vector representing that Participant's willingness to
    perpetuate the embargo on each day. Embargo willingness will be
    represented as a _1_ if the Participant is willing to commit to keeping
    the embargo on that day, and a _0_ if they are not. For simplicity's
    sake, we assume that each Participant is willing to maintain the embargo
    up to a certain point, and then their willingness goes away. In other
    words, each vector will be a series of zero or more _1_s followed by
    zero or more _0_s. For example, $[1,1,1,1,0,0,0]$ represents a
    Participant's willingness to engage in a 4-day embargo.
    
    For our two Participants, let $\mathbf{x}_ and _\mathbf{y}$ be
    zero-indexed vectors of length $max(n,m)$.
    
    $$\begin{aligned}
        |\mathbf{x}| &= max(n,m) \\
        |\mathbf{y}| &= max(n,m)
    \end{aligned}$$
    
    The elements of each vector represent each respective Participant's
    willingness for the embargo to persist on each consecutive day.
    
    $$\begin{aligned}
        \label{eq:x_i}
        \mathbf{x} = 
            \begin{bmatrix} x_i :
            x_i = 
            \begin{cases}
                1 &\text{if }i < n \\
                0 &\text{otherwise} \\
            \end{cases}
            & \text{for } 0 \leq i < max(n,m)
            \end{bmatrix} \\
        \label{eq:y_i}
        \mathbf{y} =
            \begin{bmatrix} y_i : 
            y_i = 
            \begin{cases}
                1 &\text{if }i < m \\
                0 &\text{otherwise}
            \end{cases}
            & \text{ for } 0 \leq i < max(n,m)
        \end{bmatrix}
    \end{aligned}$$
    
    Note that we have constructed these vectors so that each vector's scalar
    sum is just the length of embargo they prefer.
    
    $$\begin{aligned}
        \Sigma(\mathbf{x}) &= n \\
        \Sigma(\mathbf{y}) &= m 
    \end{aligned}$$
    
    Now we can define an agreement vector $\mathbf{z}$ as the pairwise
    logical *AND* ($\wedge$) of elements from $\mathbf{x}_ and _\mathbf{y}$:
    
    $$\begin{aligned}
        \label{eq:z_i}
        \mathbf{z} = 
        \begin{bmatrix} z_i : 
            z_i = x_i \land y_i
            & \text{for }0 \leq i < max(n,m)
        \end{bmatrix}
    \end{aligned}$$
    
    For example, if one party prefers an embargo of length $n=4$ days while
    another prefers one of length $m=7$ days, we can apply
    [\[eq:x_i\]](#eq:x_i){reference-type="eqref" reference="eq:x_i"},
    [\[eq:y_i\]](#eq:y_i){reference-type="eqref" reference="eq:y_i"}, and
    [\[eq:z_i\]](#eq:z_i){reference-type="eqref" reference="eq:z_i"} as
    follows:
    
    $$\begin{split}
        \mathbf{x} &= [1,1,1,1,0,0,0] \\
        \wedge~\mathbf{y} &= [1,1,1,1,1,1,1] \\
        \hline
        \mathbf{z} &= [1,1,1,1,0,0,0]
        \end{split}$$
    
    From this, we can see that the scalar sum of the agreement vector---and
    therefore the longest embargo acceptable to both parties---is simply the
    lesser of _n_ and _m_:
    
    $$\Sigma ( \mathbf{z} ) = min(n,m)$$

#### The Shortest Proposed Embargo Wins.

In other words, if a Reporter proposes a 90-day embargo, but the Vendor
prefers a 30-day embargo, we can think of this as a series of 1-day
agreements in which both parties agree to the first 30 days of the
embargo and disagree beyond that. By accepting the shorter 30-day
embargo, the Reporter now has 30 days to continue negotiations with the
Vendor to extend the embargo. Even if those continued negotiations fail,
both parties get at least the 30-day embargo period they agreed on in
the first place. This should be preferable to both parties versus the
alternative of no embargo at all were they to simply reject the shorter
proposal. Typically it is the Reporter who desires a shorter embargo
than the Vendor. We chose our example to demonstrate that this analysis
works between any two parties, regardless of which party wants the
shorter embargo.

!!! info "Resolving Multiple Proposals at Once"

    On our way to making this principle explicit, we immediately came across
    a second scenario worth a brief diversion: What to do when multiple
    revisions are up for negotiation simultaneously? Based on the idea of
    extending the above to an efficient pairwise evaluation of multiple
    proposals, we suggest the following heuristic:

    1.  Sort the proposals in order from earliest to latest according to
    their expiration date.
    2.  Set the current candidate to the earliest proposal.
    3.  Loop over each remaining (later) proposal, evaluating it against the
    current candidate.
    4.  If the newly evaluated proposal is accepted, it becomes the current
    candidate and the loop repeats.
    5.  Otherwise, the loop exits at the first *reject*ed proposal.
    6.  The current candidate (i.e., the latest *accept*ed proposal) becomes
    the new *Active* embargo.
    7.  If the earliest proposed revision is rejected---implying that none
    of the later ones would be acceptable either---then the existing
    *Active* embargo remains intact.

Summarizing the principles just laid out as rules

!!! note ""

    When two or more embargo proposals are open (i.e., none have yet
    been accepted) and $q^{em} \in P$, Participants SHOULD accept the
    shortest one and propose the remainder as revisions.

!!! note ""

    When two or more embargo revisions are open (i.e., an embargo is
    active yet none of the proposals have been decided) and
    $q^{em} \in R$, Participants SHOULD *accept* or *reject* them
    individually, in earliest to latest expiration order.

### Early Termination {#sec:early_termination}

Embargoes sometimes terminate prior to the agreed date and time. This is
an unavoidable, if inconvenient, fact arising from three main causes:

1.  Vulnerability discovery capability is widely distributed across the
    world, and not all Finders become cooperative Reporters.

2.  Even among otherwise cooperative CVD Participants, leaks sometimes happen.

3.  Adversaries are unconstrained by CVD in their vulnerability discovery,
    exploit code development, and use of exploit code in attacks.

While many leaks are unintentional and due to miscommunication or errors
in a Participant's CVD process, the effect is the same
regardless of the cause. As a result,

!!! note ""

    Participants SHOULD be prepared with contingency plans in the event
    of early embargo termination.

Some reasons to terminate an embargo before the agreed date include the
following:


!!! note ""
  
    Embargoes SHALL terminate immediately when information about the
    vulnerability becomes public. Public information may include reports
    of the vulnerability or exploit code.
    ($q^{cs} \in \{ \cdot\cdot\cdot P \cdot\cdot, \cdot\cdot\cdot\cdot X \cdot \}$)

!!! note ""

    Embargoes SHOULD terminate early when there is evidence that the
    vulnerability is being actively exploited by adversaries.
    ($q^{cs} \in \{ \cdot\cdot\cdot\cdot\cdot A \}$)

!!! note ""

    Embargoes SHOULD terminate early when there is evidence that
    adversaries possess exploit code for the vulnerability.

!!! note ""

    Embargoes MAY terminate early when there is evidence that
    adversaries are aware of the technical details of the vulnerability.

The above is not a complete list of acceptable reasons to terminate an
embargo early. Note that the distinction between the *SHALL* in the
first item and the *SHOULD* in the second is derived from the reasoning
given in
{== §[\[sec:transition_function\]](#sec:transition_function){reference-type="ref"
reference="sec:transition_function"} ==}, where we describe the
CS model's
transition function. Embargo termination is the set of transitions
described [above](#terminate-embargo).

##### Waiting for All Vendors to Reach Fix Ready May Be Impractical.

It is not necessary for all Vendor Participants to reach
$q^{cs} \in VF\cdot\cdot\cdot\cdot$ before publication or embargo termination.
Especially in larger MPCVD cases, there comes a point where the net
benefit of waiting for every Vendor to be ready is outweighed by the
benefit of delivering a fix to the population that can deploy it. No
solid formula for this exists, but factors to consider include the
market share of the Vendors in $q^{cs} \in VF \cdot\cdot\cdot\cdot$ compared to
those with $q^{cs} \in \cdot f\cdot\cdot\cdot\cdot$; the software supply chain for
fix delivery to Deployers; the potential impact to critical
infrastructure, public safety/health, or national security; etc.

!!! note ""

    Embargoes MAY terminate early when a quorum of Vendor Participants
    is prepared to release fixes for the vulnerability
    ($q^{cs}  \in VF\cdot\cdot\cdot\cdot$), even if some Vendors remain
    unprepared ($q^{cs} \in \cdot f \cdot\cdot\cdot\cdot$).

!!! note ""

    Participants SHOULD consider the software supply chain for the
    vulnerability in question when determining an appropriate quorum for
    release.

### Impact of Case Mergers on Embargoes

While relatively rare, it is sometimes necessary for two independent
CVD cases to be
merged into a single case. This can happen, for example, when two
Finders independently discover vulnerabilities in separate products and
report them to their respective (distinct) Vendors. On further
investigation, it might be determined that both reported problems stem
from a vulnerability in a library shared by both products. In this
scenario, each Reporter-Vendor pair might have already negotiated an
embargo for the case. Once the cases merge, the best option is usually
to renegotiate a new embargo for the new case.

!!! note ""

    A new embargo SHOULD be proposed when any two or more
    CVD cases are to be merged into a single case and multiple parties have agreed to
    different embargo terms prior to the case merger.

!!! note ""

    If no new embargo has been proposed, or if agreement has not been
    reached, the earliest of the previously accepted embargo dates SHALL
    be adopted for the merged case.

!!! note ""

    Participants MAY propose revisions to the embargo on a merged case
    as usual.

### Impact of Case Splits on Embargoes

It is also possible that a single case needs to be split into multiple
cases after an embargo has been agreed to. For example, consider a
vulnerability that affects two widely disparate fix supply chains, such
as a library used in both SAAS and OT environments. The
SAAS Vendors might
be well positioned for a quick fix deployment while the
OT Vendors might
need considerably longer to work through the logistics of delivering
deployable fixes to their customers. In such a case, the case
Participants might choose to split the case into its respective supply
chain cohorts to better coordinate within each group.

!!! note ""

    When a case is split into two or more parts, any existing embargo
    SHOULD transfer to the new cases.

!!! note ""

    If any of the new cases need to renegotiate the embargo inherited
    from the parent case, any new embargo SHOULD be later than the
    inherited embargo.

!!! note ""

    In the event that an earlier embargo date is needed for a child
    case, consideration SHALL be given to the impact that ending the
    embargo on that case will have on the other child cases retaining a
    later embargo date. In particular, Participants in each child case
    should assess whether earlier publication of one child case might
    reveal the existence of or details about other child cases.

!!! note ""

    Participants in a child case SHALL communicate any subsequently
    agreed changes from the inherited embargo to the Participants of the
    other child cases.

Note that it may not always be possible for the split cases to have
different embargo dates without the earlier case revealing the existence
of a vulnerability in the products allocated to the later case. For this
reason, it is often preferable to avoid case splits entirely.

