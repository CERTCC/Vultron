# A Formal Protocol Definition for [MPCVD]{acronym-label="MPCVD" acronym-form="singular+short"} {#sec:formal_protocol}

!!! note "TODO"
    - clean up acronyms
    - clean up cross-reference links
    - clean up section titles
    - redo diagrams in mermaid

The [MPCVD]{acronym-label="MPCVD" acronym-form="singular+short"} process
can be described as a Communicating Hierarchical State Machine. In this
chapter, we begin by laying out the requirements for a formal protocol
definition followed by a step-by-step walkthrough of each of those
requirements as they relate to the [RM]{acronym-label="RM"
acronym-form="singular+short"}, [EM]{acronym-label="EM"
acronym-form="singular+short"}, and [CS]{acronym-label="CS"
acronym-form="singular+short"} models we described in preceding
chapters.

## Communication Protocol Definitions {#sec:protocol_definition}

A communication protocol allows independent processes, represented as
finite state machines, to coordinate their state transitions through the
passing of messages. Brand and Zafiropulo [@brand1983communicating]
defined a protocol as follows. A **protocol** with $N$ processes is a
quadruple:

$$\label{eq:protocol}
protocol = 
    \Big \langle 
        { \langle S_i \rangle }^N_{i=1}, 
        { \langle o_i \rangle }^N_{i=1},
        { \langle M_{i,j} \rangle}^N_{i,j=1},
        { succ }
    \Big \rangle$$

Where

-   $N$ is a positive integer representing the number of processes.

-   $\langle S_i \rangle_{i=1}^N$ are $N$ disjoint finite sets ($S_i$
    represents the set of states of process $i$).

-   Each $o_i$ is an element of $S_i$ representing the initial state of
    process $i$.

-   $\langle M_{ij} \rangle_{i,j=1}^N$ are $N^2$ disjoint finite sets
    with $M_{ii}$ empty for all $i$. $M_{ij}$ represents the messages
    that can be sent from process $i$ to process $j$,

-   $succ$ is a partial function mapping for each $i$ and $j$,
    $$S_i \times M_{ij} \rightarrow S_i \textrm{ and } S_i \times M_{ji} \rightarrow S_i$$
    $succ(s,x)$ is the state entered after a process transmits or
    receives message $x$ in state $s$. It is a transmission if $x$ is
    from $M_{ij}$ and a reception if $x$ is from $M_{ji}$.

The **global state** of a protocol given by
[\[eq:protocol\]](#eq:protocol){reference-type="eqref"
reference="eq:protocol"} is a pair $\langle S, C \rangle$, where

-   $S$ is an $N$-tuple of states $\langle s_1,\dots,s_N \rangle$ with
    each $s_i$ representing the current state of process $i$.

-   $C$ is an $N^2$-tuple
    $\langle c_{1,1},\dots, c_{1,N}, c_{2,1}, \dots \dots, c_{N,N} \rangle$,
    where each $c_{i,j}$ is a sequence of messages from $M_{i,j}$. The
    message sequence $c_{i,j}$ represents the contents of the channel
    from process $i$ to $j$. (Note that $c_{i,j}$ is empty when $i = j$
    since processes are presumed to not communicate with themselves.)

We detail each of these in the subsequent sections of this chapter: $N$
in §[1.2](#sec:protocol_n_processes){reference-type="ref"
reference="sec:protocol_n_processes"}, ${ \langle S_i \rangle}^N_{i=1}$
in §[1.3](#sec:protocol_states){reference-type="ref"
reference="sec:protocol_states"}, ${ \langle o_i \rangle }^N_{i=1}$ in
§[1.5](#sec:protocol_starting_states){reference-type="ref"
reference="sec:protocol_starting_states"},
${ \langle M_{i,j} \rangle }^N_{i,j=1}$ in
§[1.6](#sec:protocol_message_types){reference-type="ref"
reference="sec:protocol_message_types"}, and
${ \langle {succ} \rangle }_{i=1}^N$ in
§[1.7](#sec:protocol_transition_functions){reference-type="ref"
reference="sec:protocol_transition_functions"}.

## Number of Processes {#sec:protocol_n_processes}

The processes we are concerned with represent the different Participants
in their roles (Finder, Vendor, Coordinator, Deployer, and Other). Each
Participant has their own process, but Participants might take on
multiple roles in a given case. The total number of processes $N$ is
simply the count of unique Participants, as shown in
[\[eq:n_participants\]](#eq:n_participants){reference-type="eqref"
reference="eq:n_participants"}.

$$\label{eq:n_participants}
    N = |Participants| = | Reporters \cup Vendors \cup Coordinators \cup Deployers \cup Others |$$

## States {#sec:protocol_states}

Each Participant in an [MPCVD]{acronym-label="MPCVD"
acronym-form="singular+short"} case has a corresponding
[RM]{acronym-label="RM" acronym-form="singular+short"} state, an
[EM]{acronym-label="EM" acronym-form="singular+short"} state, and an
overall [CS]{acronym-label="CS" acronym-form="singular+short"} state.
Therefore, we can represent a Participant's state as a triple comprising
the state of each of these models as in
[\[eq:q_participant\]](#eq:q_participant){reference-type="eqref"
reference="eq:q_participant"}.

$$\label{eq:q_participant}
    q_{Participant} = (q^{rm},q^{em},q^{cs})$$

Good Participant situation awareness makes for good
[CVD]{acronym-label="CVD" acronym-form="singular+short"} decision
making.

-   Participants SHOULD track the state of other Participants in a case
    to inform their own decision making as it pertains to the case.

An example object model to facilitate such tracking is given in
§[\[sec:case_object\]](#sec:case_object){reference-type="ref"
reference="sec:case_object"}. However, the protocol we are developing is
expected to function even when incomplete information is available to
any given Participant.

-   Adequate operation of the protocol MUST NOT depend on perfect
    information across all Participants.

A generic state model for a [CVD]{acronym-label="CVD"
acronym-form="singular+short"} Participant can be composed from the
Cartesian product of $\mathcal{Q}^{rm}$, $\mathcal{Q}^{em}$, and
$\mathcal{Q}^{cs}$ as shown in
[\[eq:protocol_states\]](#eq:protocol_states){reference-type="eqref"
reference="eq:protocol_states"}.

$$\label{eq:protocol_states}
    S_i 
    % = \mathcal{Q}^{rm} \times \mathcal{Q}^{em} \times \mathcal{Q}^{cs}
    = 
    \underbrace{
    \begin{bmatrix}
        S \\
        R \\
        I \\
        V \\
        D \\
        A \\ 
        C \\
    \end{bmatrix}
    }_{\mathcal{Q}^{rm}}
    \times 
    % embargo state
    \underbrace{
    \begin{bmatrix}
        N \\
        P \\
        A \\
        R \\
        X \\
    \end{bmatrix}
    }_{\mathcal{Q}^{em}}
    \times 
    % case state
    \underbrace{
    \begin{bmatrix}
        \begin{bmatrix}
            \varnothing \\
            vfd \\
            Vfd \\
            VFd \\
            VFD \\
        \end{bmatrix}
        \times 
        \begin{bmatrix}
            p \\
            P
        \end{bmatrix}
        \times 
        \begin{bmatrix}
            x \\
            X
        \end{bmatrix}
        \times 
        \begin{bmatrix}
            a \\
            A
        \end{bmatrix}
    \end{bmatrix}
    }_{\mathcal{Q}^{cs}}$$

Note that
[\[eq:protocol_states\]](#eq:protocol_states){reference-type="eqref"
reference="eq:protocol_states"} splits the case state
($\mathcal{Q}^{cs}$) into chunks corresponding to the Vendor fix path
($vfd \xrightarrow{\mathbf{V}} Vfd \xrightarrow{\mathbf{F}} VFd \xrightarrow{\mathbf{D}} VFD$)
and the public-exploit-attack ($pxa \xrightarrow{\dots} PXA$) sub-models
detailed in the Householder and Spring 2021 report
[@householder2021state]. This is done for two reasons. First, it gives
us a more compact notation to represent the 32 states of the
[CS]{acronym-label="CS" acronym-form="singular+short"} model. Second, it
highlights the fact that the Vendor fix path represents the state of an
individual Participant, whereas the public-exploit-attack sub-model
represents facts about the world at large. Because not all Participants
are Vendors or Deployers, Participants might not have a corresponding
state on the $vfd \xrightarrow{} VFD$ axis. Therefore, we add a null
element $\varnothing$ to the set of states representing the Vendor fix
path.

Thus, one might conclude that a total of 1,400 states is possible for
each Participant, as shown in
[\[eq:n_states\]](#eq:n_states){reference-type="eqref"
reference="eq:n_states"}.

$$\label{eq:n_states}
    | S_i | = 
        % actor rm state
        | \mathcal{Q}^{rm} | \cdot 
        % embargo state
        | \mathcal{Q}^{em} | \cdot
        % case state
        | \mathcal{Q}^{cs} | 
        % multiply
        = 7 \cdot 5 \cdot (5 \cdot 2 \cdot 2 \cdot 2) = 1400$$

However, this dramatically overstates the possibilities for individual
[CVD]{acronym-label="CVD" acronym-form="singular+short"} Participant
Roles because many of these states will be unreachable to individual
Participants. In the remainder of this section, we detail these
differences.

### Unreachable States

For any Participant, the [RM]{acronym-label="RM"
acronym-form="singular+short"} $Closed$ state implies that the
[EM]{acronym-label="EM" acronym-form="singular+short"} and
[CVD]{acronym-label="CVD" acronym-form="singular+short"} Case states do
not matter. Similarly, for any Participant, the [RM]{acronym-label="RM"
acronym-form="singular+short"} $Start$ state represents a case that the
Participant doesn't even know about yet. Therefore, the $Start$ state
also implies that the [EM]{acronym-label="EM"
acronym-form="singular+short"} and [CVD]{acronym-label="CVD"
acronym-form="singular+short"} Case states do not matter. We use $*$ to
represent the "don't care" value.

$$\label{eq:closed_start_ignore}
    q^{rm} \in \{S,C\} \implies (q^{em} \in *) \cup (q^{cs} \in *)$$

A public exploit implies the vulnerability is public as well. In other
words, $q^{cs} \in \cdot\cdot\cdot pX \cdot$ is an ephemeral state that resolves
quickly to $q^{cs} \in \cdot\cdot\cdot PX \cdot$. (As a reminder, dots ($\cdot$)
in [CVD]{acronym-label="CVD" acronym-form="singular+short"} case state
notation indicate single-character wildcards.)

$$\label{eq:X_implies_P}
    q^{cs} \in \cdot\cdot\cdot\cdot X \cdot \implies q^{cs} \in \cdot\cdot\cdot PX \cdot$$

Furthermore, when a vulnerability becomes public, the
[EM]{acronym-label="EM" acronym-form="singular+short"} state no longer
matters.

$$\label{eq:P_implies_no_embargo}
    q^{cs} \in \cdot\cdot\cdot P \cdot\cdot \implies q^{em} \in *$$

Taken together, we can modify
[\[eq:protocol_states\]](#eq:protocol_states){reference-type="eqref"
reference="eq:protocol_states"} in light of
[\[eq:closed_start_ignore\]](#eq:closed_start_ignore){reference-type="eqref"
reference="eq:closed_start_ignore"},
[\[eq:X_implies_P\]](#eq:X_implies_P){reference-type="eqref"
reference="eq:X_implies_P"}, and
[\[eq:P_implies_no_embargo\]](#eq:P_implies_no_embargo){reference-type="eqref"
reference="eq:P_implies_no_embargo"}. The result is shown in
[\[eq:protocol_states_reduced\]](#eq:protocol_states_reduced){reference-type="eqref"
reference="eq:protocol_states_reduced"}.

$$\label{eq:protocol_states_reduced}
    S_i 
    % = \mathcal{Q}^{rm} \times \mathcal{Q}^{em} \times \mathcal{Q}^{cs}
    = 
    \begin{cases}
    (S, *, *)\\
    {}\\
    \begin{bmatrix}
        R \\
        I \\
        V \\
        D \\
        A \\ 
    \end{bmatrix}
    \times 
    % embargo state
    \begin{bmatrix}
        N \\
        P \\
        A \\
        R \\
        X \\
    \end{bmatrix}
    \times 
    % case state
    \begin{bmatrix}
        \begin{bmatrix}
            \varnothing \\
            vfd \\
            Vfd \\
            VFd \\
            VFD \\
        \end{bmatrix}
        \times 
        \begin{bmatrix}
            p \\
        \end{bmatrix}
        \times 
        \begin{bmatrix}
            x \\
        \end{bmatrix}
        \times 
        \begin{bmatrix}
            a \\
            A \\
        \end{bmatrix}
    \end{bmatrix} \\
    {} \\
    \begin{bmatrix}
        R \\
        I \\
        V \\
        D \\
        A \\ 
    \end{bmatrix}
    \times 
    % embargo state
    \begin{bmatrix}
    * \\
    \end{bmatrix}
    \times 
    % case state
    \begin{bmatrix}
        \begin{bmatrix}
            \varnothing \\
            vfd \\
            Vfd \\
            VFd \\
            VFD \\
        \end{bmatrix}
        \times 
        \begin{bmatrix}
            P
        \end{bmatrix}
        \times 
        \begin{bmatrix}
            x \\
            X
        \end{bmatrix}
        \times 
        \begin{bmatrix}
            a \\
            A
        \end{bmatrix}
    \end{bmatrix} \\
    {}\\
    (C, *, *) \\
    \end{cases}$$

This means that each Participant must be in one of 352 possible states.

$$\begin{split}
    |S_i| &= 1 + \big(5 \cdot 5 \cdot (5 \cdot 1 \cdot 1 \cdot 2)\big) + \big(5 \cdot 1 \cdot (5 \cdot 1 \cdot 2 \cdot 2\big) + 1 \\
        %   &= 2 + 250 + 100
          &= 352
\end{split}$$

### Vendors (Fix Suppliers) {#sec:vendor_states}

Vendors are the sole providers of fixes. Therefore, they are the only
Participants in a [CVD]{acronym-label="CVD"
acronym-form="singular+short"} case for which the
$Vfd \xrightarrow{\mathbf{F}} VFd \xrightarrow{\mathbf{D}} VFD$ path is
possible. Furthermore, since they are Vendors by definition, they do not
have access to the $vfd$ state or the $\varnothing$ state that was just
added. As a Vendor has a report in $Received$, it is, by definition, at
least in the $Vfd$ case state.

Vendors create fixes only when they are in the $Accepted$
[RM]{acronym-label="RM" acronym-form="singular+short"} state. Because
the $Received$, $Invalid$, and $Valid$ states come strictly *before* the
$Accepted$ state in the [RM]{acronym-label="RM"
acronym-form="singular+short"} [DFA]{acronym-label="DFA"
acronym-form="singular+short"}, there is no way for the Vendor to be in
either $VFd$ or $VFD$ while in any of those states.

$$q^{rm}_{Vendor} \in \{R,I,V\} \implies q^{cs}_{Vendor} \in Vfd\cdot\cdot\cdot$$

Vendors with the ability to deploy fixes themselves have access to three
states in the fix path: $\{Vfd,~VFd,~VFD\}$. However, this is not always
the case. Vendor Participants without a deployment capability can only
create fixes, limiting them to the middle two states in the fix path:
$\{Vfd,~VFd\}$. Additional discussion of the distinction between Vendors
with and without a deployment capability can be found in the Householder
and Spring 2021 report [@householder2021state].

We apply these caveats to the generic model from
[\[eq:protocol_states_reduced\]](#eq:protocol_states_reduced){reference-type="eqref"
reference="eq:protocol_states_reduced"} to arrive at a Vendor state
model in in
[\[eq:protocol_states_vendor\]](#eq:protocol_states_vendor){reference-type="eqref"
reference="eq:protocol_states_vendor"}

$$\label{eq:protocol_states_vendor}
    S_{i_{Vendor}} =
    \begin{cases}
    (S, *, *)\\
    {}\\
    \begin{bmatrix}
        R \\
        I \\
        V \\
    \end{bmatrix}
    \times 
    % embargo state
    \begin{bmatrix}
        N \\
        P \\
        A \\
        R \\
        X \\
    \end{bmatrix}
    \times 
    % case state
    \begin{bmatrix}
        \begin{bmatrix}
            Vfd \\
        \end{bmatrix}
        \times
        \begin{bmatrix}
            p \\
        \end{bmatrix}
        \times 
        \begin{bmatrix}
            x \\
        \end{bmatrix}
        \times 
        \begin{bmatrix}
            a \\
            A \\
        \end{bmatrix}

        % \begin{bmatrix}
        %     pxa \\
        %     pxA \\
        %     pXa \\
        %     pXA \\
        % \end{bmatrix}
    \end{bmatrix} \textrm{\quad}\parbox{10em}{\small{unprioritized,\\maybe embargoed}} \\
    {}\\
    \begin{bmatrix}
        D \\
        A \\ 
    \end{bmatrix}
    \times 
    % embargo state
    \begin{bmatrix}
        N \\
        P \\
        A \\
        R \\
        X \\
    \end{bmatrix}
    \times 
    % case state
    \begin{bmatrix}
        \begin{bmatrix}
            Vfd \\
            VFd \\
            VFD^{\dagger} \\
        \end{bmatrix}
        \times 
        \begin{bmatrix}
            p \\
        \end{bmatrix}
        \times 
        \begin{bmatrix}
            x \\
        \end{bmatrix}
        \times 
        \begin{bmatrix}
            a \\
            A \\
        \end{bmatrix}
        % \begin{bmatrix}
        %     pxa \\
        %     pxA \\
        %     pXa \\
        %     pXA \\
        % \end{bmatrix}
    \end{bmatrix}  \textrm{\quad}\parbox{10em}{\small{prioritized,\\maybe embargoed}} \\
    {} \\
    \begin{bmatrix}
        R \\
        I \\
        V \\
    \end{bmatrix}
    \times 
    % embargo state
    \begin{bmatrix}
    * \\
    \end{bmatrix}
    \times 
    % case state
    \begin{bmatrix}
        \begin{bmatrix}
            Vfd \\
        \end{bmatrix}
        \times 
        \begin{bmatrix}
            P \\
        \end{bmatrix}
        \times 
        \begin{bmatrix}
            x \\
            X \\
        \end{bmatrix}
        \times 
        \begin{bmatrix}
            a \\
            A \\
        \end{bmatrix}
        % \begin{bmatrix}
        %     Pxa \\
        %     PxA \\
        %     PXa \\
        %     PXA \\
        % \end{bmatrix}
    \end{bmatrix}  \textrm{\quad}\parbox{10em}{\small{unprioritized,\\embargo irrelevant}}  \\
    {} \\
    \begin{bmatrix}
        D \\
        A \\ 
    \end{bmatrix}
    \times 
    % embargo state
    \begin{bmatrix}
    * \\
    \end{bmatrix}
    \times 
    % case state
    \begin{bmatrix}
        \begin{bmatrix}
            Vfd \\
            VFd \\
            VFD^{\dagger}\\
        \end{bmatrix}
        \times 
        \begin{bmatrix}
            P \\
        \end{bmatrix}
        \times 
        \begin{bmatrix}
            x \\
            X \\
        \end{bmatrix}
        \times 
        \begin{bmatrix}
            a \\
            A \\
        \end{bmatrix}

        % \begin{bmatrix}
        %     Pxa \\
        %     PxA \\
        %     PXa \\
        %     PXA \\
        % \end{bmatrix}
    \end{bmatrix}  \textrm{\quad}\parbox{10em}{\small{prioritized,\\embargo irrelevant}} \\
    {}\\
    (C, *, *) \\
    \end{cases}$$

The $\dagger$ on $VFD$ in
[\[eq:protocol_states_vendor\]](#eq:protocol_states_vendor){reference-type="eqref"
reference="eq:protocol_states_vendor"} indicates that the $VFD$ state is
accessible only to Vendors with a deployment capability. As tallied in
[\[eq:vendor_state_count_with_deploy\]](#eq:vendor_state_count_with_deploy){reference-type="eqref"
reference="eq:vendor_state_count_with_deploy"} and
[\[eq:vendor_state_count_without_deploy\]](#eq:vendor_state_count_without_deploy){reference-type="eqref"
reference="eq:vendor_state_count_without_deploy"} respectively, there
are 128 possible states for a Vendor with deployment capability and 100
for those without.

$$\label{eq:vendor_state_count_with_deploy}
    \begin{split}
        |S_{i_{\frac{Vendor}{Deployer}}}| = & 1 + \big(3 \cdot 5 \cdot (1 \cdot 1 \cdot 1 \cdot 2)\big) + \big(2 \cdot 5 \cdot (3 \cdot 1 \cdot 1 \cdot 2)\big) \\
        & + \big(3 \cdot 1 \cdot (1 \cdot 1 \cdot 2 \cdot 2)\big) + \big(2 \cdot 1 \cdot (3 \cdot 1 \cdot 2 \cdot 2)\big) + 1 \\
        % = & 2 + 30 + 60 + 12 + 24 \\
        = & 128 \\    
    \end{split}$$

$$\label{eq:vendor_state_count_without_deploy}
    \begin{split}
        |S_{i_{Vendor}}| = & 1 + \big(3 \cdot 5 \cdot (1 \cdot 1 \cdot 1 \cdot 2)\big) + \big(2 \cdot 5 \cdot (2 \cdot 1 \cdot 1 \cdot 2)\big) \\
        & + \big(3 \cdot 1 \cdot (1 \cdot 1 \cdot 2 \cdot 2)\big) + \big(2 \cdot 1 \cdot (2 \cdot 1 \cdot 2 \cdot 2)\big) + 1 \\
        % = & 2 + 30 + 40 + 12 + 16 \\
        = & 100 \\    
    \end{split}$$

### Non-Vendor Deployers {#sec:deployer_states}

We just explained that not all Vendors are Deployers. Likewise, not all
Deployers are Vendors. Most [CVD]{acronym-label="CVD"
acronym-form="singular+short"} cases leave Non-Vendor Deployers entirely
out of the [CVD]{acronym-label="CVD" acronym-form="singular+short"}
process, so their appearance is expected to be rare in actual cases.
However, there are scenarios when an [MPCVD]{acronym-label="MPCVD"
acronym-form="singular+short"} case may include Non-Vendor Deployers,
such as when a vulnerability in some critical infrastructure component
is being handled or when the [MPCVD]{acronym-label="MPCVD"
acronym-form="singular+short"} protocol is used in the context of a
[VDP]{acronym-label="VDP" acronym-form="singular+short"}. These
Non-Vendor Deployers participate only in the
$d \xrightarrow{\mathbf{D}} D$ transition on the fix path. Similar to
the Vendor scenario in §[1.3.2](#sec:vendor_states){reference-type="ref"
reference="sec:vendor_states"}, it is expected that Deployers actually
deploy fixes only when they are in the RM $Accepted$ state (implying
their intent to deploy). Therefore, their set of possible states is even
more restricted than Vendors, as shown in
[\[eq:protocol_states_nonvendor_deployer\]](#eq:protocol_states_nonvendor_deployer){reference-type="eqref"
reference="eq:protocol_states_nonvendor_deployer"}.

$$\label{eq:protocol_states_nonvendor_deployer}
    S_{i_{Deployer}} =
    \begin{cases}
    (S, *, *)\\
    {}\\
    \begin{bmatrix}
        R \\
        I \\
        V \\
    \end{bmatrix}
    \times 
    % embargo state
    \begin{bmatrix}
        N \\
        P \\
        A \\
        R \\
        X \\
    \end{bmatrix}
    \times 
    % case state
    \begin{bmatrix}
        \begin{bmatrix}
            d \\
        \end{bmatrix}
        \times 
        \begin{bmatrix}
            p \\
        \end{bmatrix}
        \times 
        \begin{bmatrix}
            x \\
        \end{bmatrix}
        \times 
        \begin{bmatrix}
            a \\
            A \\
        \end{bmatrix}
    \end{bmatrix} \text{\quad}\parbox{10em}{\small{unprioritized,\\maybe embargoed}} \\
    {}\\
    \begin{bmatrix}
        D \\
        A \\ 
    \end{bmatrix}
    \times 
    % embargo state
    \begin{bmatrix}
        N \\
        P \\
        A \\
        R \\
        X \\
    \end{bmatrix}
    \times 
    % case state
    \begin{bmatrix}
        \begin{bmatrix}
            d \\
            D \\
        \end{bmatrix}
        \times 
        \begin{bmatrix}
            p \\
        \end{bmatrix}
        \times 
        \begin{bmatrix}
            x \\
        \end{bmatrix}
        \times 
        \begin{bmatrix}
            a \\
            A \\
        \end{bmatrix}
    \end{bmatrix}\text{\quad}\parbox{10em}{\small{prioritized,\\maybe embargoed}} \\
    {} \\
    \begin{bmatrix}
        R \\
        I \\
        V \\
    \end{bmatrix}
    \times 
    % embargo state
    \begin{bmatrix}
    * \\
    \end{bmatrix}
    \times 
    % case state
    \begin{bmatrix}
        \begin{bmatrix}
            d \\
        \end{bmatrix}
        \times 
        \begin{bmatrix}
            P \\
        \end{bmatrix}
        \times 
        \begin{bmatrix}
            x \\
            X \\
        \end{bmatrix}
        \times 
        \begin{bmatrix}
            a \\
            A \\
        \end{bmatrix}
    \end{bmatrix} \text{\quad}\parbox{10em}{\small{unprioritized,\\embargo irrelevant}}  \\
    {} \\
    \begin{bmatrix}
        D \\
        A \\ 
    \end{bmatrix}
    \times 
    % embargo state
    \begin{bmatrix}
    * \\
    \end{bmatrix}
    \times 
    % case state
    \begin{bmatrix}
        \begin{bmatrix}
            d \\
            D \\
        \end{bmatrix}
        \times 
        \begin{bmatrix}
            P \\
        \end{bmatrix}
        \times 
        \begin{bmatrix}
            x \\
            X \\
        \end{bmatrix}
        \times 
        \begin{bmatrix}
            a \\
            A \\
        \end{bmatrix}
    \end{bmatrix} \text{\quad}\parbox{10em}{\small{prioritized,\\embargo irrelevant}} \\
    {}\\
    (C, *, *) \\
    \end{cases}$$

Thus, Non-Vendor Deployers can be expected to be in 1 of 100 possible
states, as shown in
[\[eq:deployer_state_count\]](#eq:deployer_state_count){reference-type="eqref"
reference="eq:deployer_state_count"}.

$$\label{eq:deployer_state_count}
    \begin{split}
        |S_{i_{Deployer}}| = & 1 + \big(3 \cdot 5 \cdot (1 \cdot 1 \cdot 1 \cdot 2)\big) + \big(2 \cdot 5 \cdot (2 \cdot 1 \cdot 1 \cdot 2)\big) \\
        & + \big(3 \cdot 1 \cdot (1 \cdot 1 \cdot 2 \cdot 2)\big) + \big(2 \cdot 1 \cdot (2 \cdot 1 \cdot 2 \cdot 2)\big) + 1 \\
        % = & 2 + 30 + 40 + 12 + 16 \\
        = & 100 \\    
    \end{split}$$

### Non-Vendor, Non-Deployer Participants {#sec:other_participants}

Finally, [CVD]{acronym-label="CVD" acronym-form="singular+short"} cases
often involve Participants who are neither Vendors nor Deployers.
Specifically, Finder/Reporters fall into this category, as do
Coordinators. Other roles, as outlined in the *CERT Guide to Coordinated
Vulnerability Disclosure* [@householder2017cert], could be included here
as well. Because they do not participate directly in the Vendor fix
path, these Non-Vendor, Non-Deployer [CVD]{acronym-label="CVD"
acronym-form="singular+short"} Participants fall into the $\varnothing$
case substate we added to
[\[eq:protocol_states\]](#eq:protocol_states){reference-type="eqref"
reference="eq:protocol_states"}. Their state model is shown in
[\[eq:protocol_states_other\]](#eq:protocol_states_other){reference-type="eqref"
reference="eq:protocol_states_other"}.

$$\label{eq:protocol_states_other}
    S_{i_{Other}} = 
    \begin{cases}
    (S,*,*) \\
    {} \\
    \begin{bmatrix}
        R \\
        I \\
        V \\
        D \\
        A \\ 
    \end{bmatrix}
    \times 
    % embargo state
    \begin{bmatrix}
        N \\
        P \\
        A \\
        R \\
        X \\
    \end{bmatrix}
    \times 
    % case state
    \begin{bmatrix}
        \begin{bmatrix}
        \varnothing
        \end{bmatrix} 
        \times
        \begin{bmatrix}
            p \\
        \end{bmatrix}
        \times 
        \begin{bmatrix}
            x \\
        \end{bmatrix}
        \times 
        \begin{bmatrix}
            a \\
            A \\
        \end{bmatrix}
    \end{bmatrix} \text{\quad \small{(maybe embargoed)}}\\
    {}\\
    \begin{bmatrix}
        R \\
        I \\
        V \\
        D \\
        A \\ 
    \end{bmatrix}
    \times 
    % embargo state
    \begin{bmatrix}
        * \\
    \end{bmatrix}
    \times 
    % case state
    \begin{bmatrix}
    \begin{bmatrix}
        \varnothing
    \end{bmatrix}
    \times
        \begin{bmatrix}
            P \\
        \end{bmatrix}
        \times 
        \begin{bmatrix}
            x \\
            X \\
        \end{bmatrix}
        \times 
        \begin{bmatrix}
            a \\
            A \\
        \end{bmatrix}
        
    \end{bmatrix} \text{\quad \small{(embargo irrelevant)}} \\
    {} \\
    (C,*,*) \\
    \end{cases}$$

Non-Vendor Non-Deployer [CVD]{acronym-label="CVD"
acronym-form="singular+short"} Participants (Finder/Reporters,
Coordinators, etc.) will be in 1 of 72 states, as calculated in
[\[eq:n_states_other\]](#eq:n_states_other){reference-type="eqref"
reference="eq:n_states_other"}.

$$\label{eq:n_states_other}
    \begin{split}
        |S_{i_{Other}}| = & 1 + \big(5 \cdot 5 \cdot (1 \cdot 1 \cdot 1 \cdot 2)\big) + \big(5 \cdot 1 \cdot (1 \cdot 1 \cdot 2 \cdot 2)\big) + 1 \\
        % = & 2 + 50 + 20\\
        = & 72 \\    
    \end{split}$$

##### Finder-Reporters.

As we discussed in
§[\[sec:finder_hidden\]](#sec:finder_hidden){reference-type="ref"
reference="sec:finder_hidden"}, the early Finder states are largely
hidden from view from other [CVD]{acronym-label="CVD"
acronym-form="singular+short"} Participants unless they choose to engage
in the [CVD]{acronym-label="CVD" acronym-form="singular+short"} process
in the first place. Therefore, for a [CVD]{acronym-label="CVD"
acronym-form="singular+short"} protocol, we only need to care about
Finder states once they have reached [RM]{acronym-label="RM"
acronym-form="singular+short"} $Accepted$. Coincidentally, this is also
a convenient way to mark the transition from Finder to Reporter.

$$\label{eq:protocol_states_reporter}
    S_{i_{Reporter}} = 
    \begin{cases}
    (S,*,*) \text{\quad \small{(hidden)}}\\
    (R,*,*) \text{\quad \small{(hidden)}}\\
    (I,*,*) \text{\quad \small{(hidden)}}\\
    (V,*,*) \text{\quad \small{(hidden)}}\\
    {} \\
    \begin{bmatrix}
        D \\
        A \\ 
    \end{bmatrix}
    \times 
    % embargo state
    \begin{bmatrix}
        N \\
        P \\
        A \\
        R \\
        X \\
    \end{bmatrix}
    \times 
    % case state
    \begin{bmatrix}
        \begin{bmatrix}
        \varnothing
        \end{bmatrix} 
        \times
        \begin{bmatrix}
            p \\
        \end{bmatrix}
        \times 
        \begin{bmatrix}
            x \\
        \end{bmatrix}
        \times 
        \begin{bmatrix}
            a \\
            A \\
        \end{bmatrix}
    \end{bmatrix} \text{\quad \small{maybe embargoed}} \\
    {}\\
    \begin{bmatrix}
        D \\
        A \\ 
    \end{bmatrix}
    \times 
    % embargo state
    \begin{bmatrix}
        * \\
    \end{bmatrix}
    \times 
    % case state
    \begin{bmatrix}
    \begin{bmatrix}
        \varnothing
    \end{bmatrix}
    \times
        \begin{bmatrix}
            P \\
        \end{bmatrix}
        \times 
        \begin{bmatrix}
            x \\
            X \\
        \end{bmatrix}
        \times 
        \begin{bmatrix}
            a \\
            A \\
        \end{bmatrix}
        
    \end{bmatrix} \text{\quad \small{embargo irrelevant}} \\
    {} \\
    (C,*,*) \\
    \end{cases}$$

Thus, for all practical purposes, we can ignore the hidden states in
[\[eq:protocol_states_reporter\]](#eq:protocol_states_reporter){reference-type="eqref"
reference="eq:protocol_states_reporter"} and conclude that Finders who
go on to become Reporters have only 29 possible states during a
[CVD]{acronym-label="CVD" acronym-form="singular+short"} case.

$$\label{eq:n_states_reporter}
    \begin{split}
        |S_{i_{Reporter}}| = & \big(2 \cdot 5 \cdot (1 \cdot 1 \cdot 1 \cdot 2)\big) + \big(2 \cdot 1 \cdot (1 \cdot 1 \cdot 2 \cdot 2)\big) + 1 \\
        % = & 20 + 8 + 1 \\
        = & 29 \\    
    \end{split}$$

## A Lower Bounds on MPCVD State Space {#sec:upper_lower_state_space}

Now we can touch on the lower bounds of the state space of an
[MPCVD]{acronym-label="MPCVD" acronym-form="singular+short"} case.
Generically, we would expect the state space for $N$ Participants to
take the form of equation
[\[eq:generic_state_space\]](#eq:generic_state_space){reference-type="eqref"
reference="eq:generic_state_space"}.

$$\label{eq:generic_state_space}
    |S_{total}| = \prod_{i=1}^{N} |S_i|$$

The upper bound on the [MPCVD]{acronym-label="MPCVD"
acronym-form="singular+short"} state space is simply
$352^N \approx 10^{2.55N}$. However, because of the Role-specific limits
just described in §[1.3](#sec:protocol_states){reference-type="ref"
reference="sec:protocol_states"}, we already know that this overcounts
the possible states significantly. We can do better still. If we ignore
transient states while Participants converge on a consistent view of the
global state of a case, we can drastically reduce the state space for an
[MPCVD]{acronym-label="MPCVD" acronym-form="singular+short"} case. Why?
There are two reasons:

1.  Because they represent facts about the outside world, the eight
    $\cdot\cdot\cdot pxa \rightarrow \cdot\cdot\cdot PXA$ [CS]{acronym-label="CS"
    acronym-form="singular+short"} substates are global to the case, not
    to individual Participants. This means all Participants should
    rapidly converge to the same substate.

2.  Similarly, the five [EM]{acronym-label="EM"
    acronym-form="singular+short"} states are also global to the case
    and should converge rapidly.

Given these two observations, we can pull those global terms out of the
state calculations for individual Participants,

$$|S_{global}| = 8 \times 5 = 40$$

which leaves

$$|S_{Participant}| =
    \begin{cases}
        Reporter = 1 + 2 = 3 \\
        Vendor =  2 + 3 + (2 \cdot 2) + 3 + (2 \cdot 2 ) = 16 \\
        Vendor/Deployer =  2 + 3 + (2 \cdot 3) + 3 + (2 \cdot 3) = 20 \\
        Coordinator = 2 + 5  = 7 \\
        Deployer = 2 + 3 = 5\\
        Others = 2 + 5  = 7 \\
    \end{cases}$$

So our state space looks like

$$\begin{split}
    |S_{total}| = 40 & \times
        3^{N_{Reporter}} \times
        16^{N_{Vendor}} \times
        20^{N_{\frac{Vendor}{Deployer}}} \\
        & \times
        7^{N_{Coordinator}} \times 
        5^{N_{Deployer}} \times 
        7^{N_{Other}} \\
    \end{split}$$

With these values in mind, we see that

-   A two-party (Finder-Vendor) case might have a lower bound state
    space of $40 \times 3 \times 16 = 1,920$ states.

-   A case like Meltdown/Spectre (with six Vendors and no Coordinators)
    might have $40 \times 3 \times 16^{6} \approx 10^{9}$ states.

-   A large, but not atypical, 200-Vendor case handled by the
    [CERT/CC]{acronym-label="CERT/CC" acronym-form="singular+short"}
    might have $40 \times 3 \times 16^{200} \times 7 \approx 10^{244}$
    possible configurations.

-   In the case of the log4j vulnerability CVE-2021-44228 in December
    2021, the [CERT/CC]{acronym-label="CERT/CC"
    acronym-form="singular+short"} notified around 1,600 Vendors after
    the vulnerability had been made public [@vu930724]. Had this been an
    embargoed disclosure, the case would have a total state space around
    $10^{2000}$.

That said, while these are dramatic numbers, the reader is reminded that
the whole point of the [MPCVD]{acronym-label="MPCVD"
acronym-form="singular+short"} protocol is to *coordinate* the process
so that it is not just hundreds or thousands of Participants behaving
randomly.

## Starting States {#sec:protocol_starting_states}

Each Participant begins a case in the state where the report management
process is in the start state, there is no embargo in place, and the
case has not made any progress.

A formal definition of the Participant start state is shown in
[\[eq:protocol_start_state_participant\]](#eq:protocol_start_state_participant){reference-type="eqref"
reference="eq:protocol_start_state_participant"}.

$$\label{eq:protocol_start_state_participant}
    o_i = (o_i^{rm},~o_i^{em},~o_i^{cs}) = (S,N,vfdpxa)$$

Following the discussion in
§[1.3](#sec:protocol_states){reference-type="ref"
reference="sec:protocol_states"}, the starting states for Vendors,
Deployers, and other Participants are shown in
[\[eq:protocol_start_state_vendor\]](#eq:protocol_start_state_vendor){reference-type="eqref"
reference="eq:protocol_start_state_vendor"}
[\[eq:protocol_start_state_deployer\]](#eq:protocol_start_state_deployer){reference-type="eqref"
reference="eq:protocol_start_state_deployer"}, and
[\[eq:protocol_start_state_other\]](#eq:protocol_start_state_other){reference-type="eqref"
reference="eq:protocol_start_state_other"}, respectively.

$$\label{eq:protocol_start_state_vendor}
    o_{i_{Vendor}} = (S,N,vfdpxa)$$

$$\label{eq:protocol_start_state_deployer}
    o_{i_{Deployer}} = (S,N,dpxa)$$

$$\label{eq:protocol_start_state_other}
    o_{i_{Other}} = (S,N,pxa)$$

For a case to really begin, the Finder must at least reach the $A$
state. Therefore, at the point when a second party finds out about the
vulnerability from a Finder, the Finder is presumed to be already at
$q_{Finder}=(A, N, pxa)$.

$$\label{eq:protocol_start_state_finder}
    o_{i_{Finder}} = (A,N,pxa)$$

We will show in
§[1.7](#sec:protocol_transition_functions){reference-type="ref"
reference="sec:protocol_transition_functions"} how this plays out. But
first, we need to define the message types that can be exchanged between
Participants.

## Message Types {#sec:protocol_message_types}

In §[1.3](#sec:protocol_states){reference-type="ref"
reference="sec:protocol_states"}, we identified four main roles in the
[MPCVD]{acronym-label="MPCVD" acronym-form="singular+short"} process:
Finder/Reporter, Vendor, Coordinator, and Deployer. Here we will examine
the messages passed between them. Revisiting the definitions from
§[1.1](#sec:protocol_definition){reference-type="ref"
reference="sec:protocol_definition"},

> $\langle M_{ij} \rangle_{i,j=1}^N$ are $N^2$ disjoint finite sets with
> $M_{ii}$ empty for all $i$: $M_{ij}$ represents the messages that can
> be sent from process $i$ to process $j$.

The message types in our proposed [MPCVD]{acronym-label="MPCVD"
acronym-form="singular+short"} protocol arise primarily from the
following principle taken directly from the [CVD]{acronym-label="CVD"
acronym-form="singular+short"} Guide [@householder2017cert]:

> **Avoid Surprise** -- As with most situations in which multiple
> parties are engaged in a potentially stressful and contentious
> negotiation, surprise tends to increase the risk of a negative
> outcome. The importance of clearly communicating expectations across
> all parties involved in a CVD process cannot be overemphasized. If we
> expect cooperation between all parties and stakeholders, we should do
> our best to match their expectations of being "in the loop" and
> minimize their surprise. Publicly disclosing a vulnerability without
> coordinating first can result in panic and an aversion to future
> cooperation from Vendors and Finders alike. CVD promotes continued
> cooperation and increases the likelihood that future vulnerabilities
> will also be addressed and remedied.

Now we condense that principle into the following protocol
recommendation:

-   Participants whose state changes in the [RM]{acronym-label="RM"
    acronym-form="singular+short"}, [EM]{acronym-label="EM"
    acronym-form="singular+short"}, or [CVD]{acronym-label="CVD"
    acronym-form="singular+short"} State Models SHOULD send a message to
    other Participants for each transition.

If you are looking for a one-sentence summary of the entire
[MPCVD]{acronym-label="MPCVD" acronym-form="singular+short"} protocol,
that was it.

As a reminder, those transitions are

-   RM state transitions $\Sigma^{rm} = \{ r,v,a,i,d,c\}$

-   EM state transitions $\Sigma^{em} = \{ p,a,r,t\}$

-   CVD state transitions
    $\Sigma^{cs} = \{\mathbf{V},\mathbf{F},\mathbf{D},\mathbf{P},\mathbf{X},\mathbf{A}\}$

We will address the specific circumstances when each message should be
emitted in
§[1.7](#sec:protocol_transition_functions){reference-type="ref"
reference="sec:protocol_transition_functions"}, but first we need to
introduce the message types this recommendation implies. We cover
messages associated with each state model, in turn, below, concluding
the section with a few message types not directly connected to any
particular state model.

### RM Message Types {#sec:rm_message_types}

With the exception of the Finder/Reporter, each Participant's
involvement in a [CVD]{acronym-label="CVD"
acronym-form="singular+short"} case starts with the receipt of a report
from another Participant who is already in the $Accepted$
($q^{rm} \in A$) state.[^1]

Report Submission

:   ($RS$) is a message from one Participant to a new Participant
    containing a vulnerability report.

We continue with a list of state-change messages *originating* from a
Participant in the [RM]{acronym-label="RM"
acronym-form="singular+short"} process:

Report Invalid

:   ($RI$) is a message indicating the Participant has designated the
    report as invalid.

Report Valid

:   ($RV$) is a message indicating the Participant has designated the
    report as valid.

Report Deferred

:   ($RD$) is a message indicating the Participant is deferring further
    action on a report.

Report Accepted

:   ($RA$) is a message indicating the Participant has accepted the
    report for further action.

Report Closed

:   ($RC$) is a message indicating the Participant has closed the
    report.

Report Acknowledgement

:   ($RK$) is a message acknowledging the receipt of a report.

Report Error

:   ($RE$) is a message indicating a Participant received an unexpected
    [RM]{acronym-label="RM" acronym-form="singular+short"} message.

A summary of the [RM]{acronym-label="RM" acronym-form="singular+short"}
message types is shown in [\[eq:m_rm\]](#eq:m_rm){reference-type="eqref"
reference="eq:m_rm"}.

$$\label{eq:m_rm}
M^{rm} = \{RS,RI,RV,RD,RA,RC,RK,RE\}$$

All state changes are from the Participant's (sender's) perspective, not
the recipient's perspective. We will see in
§[1.7](#sec:protocol_transition_functions){reference-type="ref"
reference="sec:protocol_transition_functions"} that the receipt of a
*Report Submission* is the only message whose *receipt* directly
triggers an [RM]{acronym-label="RM" acronym-form="singular+short"} state
change in the receiver. All other [RM]{acronym-label="RM"
acronym-form="singular+short"} messages are used to convey the sender's
status.

-   Participants SHOULD act in accordance with their own policy and
    process in deciding when to transition states in the
    [RM]{acronym-label="RM" acronym-form="singular+short"} model.

-   Participants SHOULD NOT mark duplicate reports as invalid.

-   Instead, duplicate reports SHOULD pass through $Valid$
    ($q^{rm} \in V$), although they MAY be subsequently (immediately or
    otherwise) deferred ($q^{rm} \in V \xrightarrow{d} D$) in favor of
    the original.

-   Participants SHOULD track the [RM]{acronym-label="RM"
    acronym-form="singular+short"} states of the other Participants in
    the case.

An example object model for such tracking is described in
§[\[sec:case_object\]](#sec:case_object){reference-type="ref"
reference="sec:case_object"}. Furthermore, while these messages are
expected to inform the receiving Participant's choices in their own
[RM]{acronym-label="RM" acronym-form="singular+short"} process, this
protocol intentionally does not specify any other recipient
[RM]{acronym-label="RM" acronym-form="singular+short"} state changes
upon receipt of an [RM]{acronym-label="RM"
acronym-form="singular+short"} message.

### EM Message Types {#sec:em_message_types}

Whereas the [RM]{acronym-label="RM" acronym-form="singular+short"}
process is unique to each Participant, the [EM]{acronym-label="EM"
acronym-form="singular+short"} process is global to the case. Therefore,
we begin with the list of message types a Participant SHOULD emit when
their [EM]{acronym-label="EM" acronym-form="singular+short"} state
changes.

Embargo Proposal

:   ($EP$) is a message containing proposed embargo terms (e.g.,
    date/time of expiration).

Embargo Proposal Rejection

:   ($ER$) is a message indicating the Participant has rejected an
    embargo proposal.

Embargo Proposal Acceptance

:   ($EA$) is a message indicating the Participant has accepted an
    embargo proposal.

Embargo Revision Proposal

:   ($EV$) is a message containing a proposed revision to embargo terms
    (e.g., date/time of expiration).

Embargo Revision Rejection

:   ($EJ$) is a message indicating the Participant has rejected a
    proposed embargo revision.

Embargo Revision Acceptance

:   ($EC$) is a message indicating the Participant has accepted a
    proposed embargo revision.

Embargo Termination

:   ($ET$) is a message indicating the Participant has terminated an
    embargo (including the reason for termination). Note that an
    *Embargo Termination* message is intended to have immediate effect.

    -   If an early termination is desired but the termination date/time
        is in the future, this SHOULD be achieved through an *Embargo
        Revision Proposal* and additional communication as necessary to
        convey the constraints on the proposal.

Embargo Acknowledgement

:   ($EK$) is a message acknowledging receipt of an
    [EM]{acronym-label="EM" acronym-form="singular+short"} message.

Embargo Error

:   ($EE$) is a message indicating a Participant received an unexpected
    [EM]{acronym-label="EM" acronym-form="singular+short"} message.

A summary of the [EM]{acronym-label="EM" acronym-form="singular+short"}
message types is shown in [\[eq:m_em\]](#eq:m_em){reference-type="eqref"
reference="eq:m_em"}.

$$\label{eq:m_em}
M^{em} = \{ EP,ER,EA,EV,EJ,EC,ET,EK,EE \}$$

### CS Message Types {#sec:cs_message_types}

From the [CS]{acronym-label="CS" acronym-form="singular+short"} process
in §[\[sec:model\]](#sec:model){reference-type="ref"
reference="sec:model"}, the following is the list of messages associated
with [CS]{acronym-label="CS" acronym-form="singular+short"} state
changes:

Vendor Awareness

:   ($CV$) is a message to other Participants indicating that a report
    has been delivered to a specific Vendor. Note that this is an
    announcement of a state change for a Vendor, not the actual report
    to the Vendor, which is covered in the **Report Submission** ($RS$)
    above.

    -   **Vendor Awareness** messages SHOULD be sent only by
        Participants with direct knowledge of the notification (i.e.,
        either by the Participant who sent the report to the Vendor or
        by the Vendor upon receipt of the report).

Fix Readiness

:   ($CF$) is a message from a Participant (usually a Vendor) indicating
    that a specific Vendor has a fix ready.

Fix Deployed

:   ($CD$) is a message from a Participant (usually a Deployer)
    indicating that they have completed their fix deployment process.
    This message is expected to be rare in most
    [MPCVD]{acronym-label="MPCVD" acronym-form="singular+short"} cases
    because Deployers are rarely included in the coordination effort.

Public Awareness

:   ($CP$) is a message from a Participant indicating that they have
    evidence that the vulnerability is known to the public. This message
    might be sent after a Participant has published their own advisory
    or if they have observed public discussion of the vulnerability.

Exploit Public

:   ($CX$) is a message from a Participant indicating that they have
    evidence that an exploit for the vulnerability is publicly
    available. This message might be sent after a Participant has
    published their own exploit code, or if they have observed exploit
    code available to the public.

Attacks Observed

:   ($CA$) is a message from a Participant indicating that they have
    evidence that attackers are exploiting the vulnerability in attacks.

[CS]{acronym-label="CS" acronym-form="singular+long"} Acknowledgement

:   ($CK$) is a message acknowledging receipt of a
    [CS]{acronym-label="CS" acronym-form="singular+short"} message.

[CS]{acronym-label="CS" acronym-form="singular+long"} Error

:   ($CE$) is a message indicating a Participant received an unexpected
    [CS]{acronym-label="CS" acronym-form="singular+short"} message.

A summary of the [CS]{acronym-label="CS" acronym-form="singular+short"}
message types is shown in [\[eq:m_cs\]](#eq:m_cs){reference-type="eqref"
reference="eq:m_cs"}.

$$\label{eq:m_cs}
M^{cs} = \{CV,CF,CD,CP,CX,CA,CK,CE \}$$

### Other Message Types {#sec:gen_message_types}

Finally, there are a few additional message types required to tie the
coordination process together. Most of these message types are *not*
associated with a specific state change, although they might trigger
activities or events that could cause a state change in a Participant
(and therefore trigger one or more of the above message types to be
sent).

General Inquiry

:   ($GI$) is a message from a Participant to one or more other
    Participants to communicate non-state-change information. Examples
    of general inquiry messages include but are not limited to

    -   asking or responding to a question

    -   requesting an update on a Participant's status

    -   requesting review of a draft publication

    -   suggesting a potential Participant to be added to a case

    -   coordinating other events

    -   resolving a loss of Participant state synchronization

General Acknowledgement

:   ($GK$) is a message from a Participant indicating their receipt of
    any of the other messages listed here.

General Error

:   ($GE$) is a message indicating a general error has occurred.

A summary of the General message types is shown in
[\[eq:m_gm\]](#eq:m_gm){reference-type="eqref" reference="eq:m_gm"}.

$$\label{eq:m_gm}
M^{*} = \{ GI,GK,GE \}$$

### Message Type Redux

Thus, the complete set of possible messages between processes is
$M_{i,j} = M^{rm} \cup M^{em} \cup M^{cs} \cup M^{*}$. For convenience,
we collected these into
[\[eq:message_types\]](#eq:message_types){reference-type="eqref"
reference="eq:message_types"} and provide a summary in Table
[\[tab:message_types\]](#tab:message_types){reference-type="ref"
reference="tab:message_types"}.

$$\label{eq:message_types}
    M_{i,j} =
        \left\{ 
        \begin{array}{l}
                RS,RI,RV,RD,RA,RC,RK,\\
                RE,EP,ER,EA,EV,EJ,EC,\\
                ET,EK,EE,CV,CF,CD,CP,\\
                CX,CA,CK,CE,GI,GK,GE\\
        \end{array}
        \right\}\text{\quad}
        \parbox{10em}{ where $i \neq j$; \\
        $\varnothing$ otherwise;
        \\for $i,j \leq N$}$$

Message formats are left as future work in
§[\[sec:msg_formats\]](#sec:msg_formats){reference-type="ref"
reference="sec:msg_formats"}.

## Transition Functions {#sec:protocol_transition_functions}

Revisiting the formal protocol definition from the beginning of the
chapter,

> $succ$ is a partial function mapping for each $i$ and $j$,
> $$S_i \times M_{ij} \rightarrow S_i \textrm{ and } S_i \times M_{ji} \rightarrow S_i$$
> $succ(s,x)$ is the state entered after a process transmits or receives
> message $x$ in state $s$. It is a transmission if $x$ is from $M_{ij}$
> and a reception if $x$ is from $M_{ji}$.

In this section, we describe the transition functions for the
[RM]{acronym-label="RM" acronym-form="singular+short"},
[EM]{acronym-label="EM" acronym-form="singular+short"}, and
[CVD]{acronym-label="CVD" acronym-form="singular+short"} Case processes,
respectively. Note that while the [RM]{acronym-label="RM"
acronym-form="singular+short"} process is largely independent of the
other two process models, the [EM]{acronym-label="EM"
acronym-form="singular+short"} and [CVD]{acronym-label="CVD"
acronym-form="singular+short"} process models have some noteworthy
interactions, which we will cover in detail.

### RM Transition Functions

Because it only reflects an individual Participant's report handling
status, the [RM]{acronym-label="RM" acronym-form="singular+short"}
process operates largely independent of both the [EM]{acronym-label="EM"
acronym-form="singular+short"} and [CS]{acronym-label="CS"
acronym-form="singular+short"} processes. Otherwise,

-   Participants MUST be in [RM]{acronym-label="RM"
    acronym-form="singular+short"} $Accepted$ to send a report ($RS$) to
    someone else.

-   Participants SHOULD send $RI$ when the report validation process
    ends in an $invalid$ determination.

-   Participants SHOULD send $RV$ when the report validation process
    ends in a $valid$ determination.

-   Participants SHOULD send $RD$ when the report prioritization process
    ends in a $deferred$ decision.

-   Participants SHOULD send $RA$ when the report prioritization process
    ends in an $accept$ decision.

-   Participants SHOULD send $RC$ when the report is closed.

-   Participants SHOULD send $RE$ regardless of the state when any error
    is encountered.

-   Recipients MAY ignore messages received on $Closed$ cases.

-   Recipients SHOULD send $RK$ in acknowledgment of any $R*$ message
    except $RK$ itself.

-   Vendor Recipients should send both $CV$ and $RK$ in response to a
    report submission ($RS$). If the report is new to the Vendor, it
    MUST transition $q^{cs} \xrightarrow{\mathbf{V}}Vfd\cdot\cdot\cdot$.

-   Any $R*$ message, aside from $RS$, received by recipient in
    $q^{rm} \in S$ is an error because it indicates the sender thought
    the receiver was aware of a report they had no knowledge of. The
    Recipient SHOULD respond with both an $RE$ to signal the error and
    $GI$ to find out what the sender expected.

-   Recipients SHOULD acknowledge $RE$ messages ($RK$) and inquire
    ($GI$) as to the nature of the error.

Table [\[tab:rm_send\]](#tab:rm_send){reference-type="ref"
reference="tab:rm_send"} lists each [RM]{acronym-label="RM"
acronym-form="singular+short"} message type and the states in which that
message is appropriate to send along with the corresponding sender state
transition. Table
[\[tab:rm_receive\]](#tab:rm_receive){reference-type="ref"
reference="tab:rm_receive"} lists the effects of receiving
[RM]{acronym-label="RM" acronym-form="singular+short"} messages on the
receiving Participant's state coupled with the expected response
message.

### EM Transition Functions

The appropriate Participant behavior in the [EM]{acronym-label="EM"
acronym-form="singular+short"} process depends on whether the case state
$q^{cs}$ is in $\cdot\cdot\cdot pxa$ or not.

-   Participants SHALL NOT negotiate embargoes where the vulnerability
    or its exploit is public or attacks are known to have occurred.

-   Participants MAY begin embargo negotiations before sending the
    report itself in an $RS$ message. Therefore, it is *not* an error
    for an $E*$ message to arrive while the Recipient is unaware of the
    report ($q^{rm} \in S$).

-   Participants MAY reject any embargo proposals or revisions for any
    reason.

-   If information about the vulnerability or an exploit for it has been
    made public, Participants SHALL terminate the embargo
    ($q^{cs} \in \{\cdot\cdot\cdot P \cdot\cdot, \cdot\cdot\cdot\cdot X \cdot\}$).

-   If attacks are known to have occurred, Participants SHOULD terminate
    the embargo ($q^{cs} \in \cdot\cdot\cdot\cdot\cdot A$).

-   Participants SHOULD send $EK$ in acknowledgment of any other $E*$
    message except $EK$ itself.

-   Participants SHOULD acknowledge ($EK$) and inquire ($GI$) about the
    nature of any error reported by an incoming $EE$ message.

Table [\[tab:em_send\]](#tab:em_send){reference-type="ref"
reference="tab:em_send"} lists each [EM]{acronym-label="EM"
acronym-form="singular+short"} message type and the states in which that
message is appropriate to send along with the corresponding sender state
transition. Table
[\[tab:em_receive\]](#tab:em_receive){reference-type="ref"
reference="tab:em_receive"} lists the effects of receiving an
[EM]{acronym-label="EM" acronym-form="singular+short"} message to the
receiving Participant's state, grouped by the [EM]{acronym-label="EM"
acronym-form="singular+short"} message type received.

### CVD Transition Functions

The Vendor-specific portions of the [CS]{acronym-label="CS"
acronym-form="singular+short"} (*Vendor Awareness*, *Fix Ready*, and
*Fix Deployed*) are per-Participant states. Therefore, the receiver of a
message indicating another Participant has changed their $\{v,V\}$,
$\{f,F\}$ or $\{d,D\}$ status is not expected to change their own state
as a result.[^2]

However, this is not the case for the remainder of the
[CS]{acronym-label="CS" acronym-form="singular+short"} substates. As
above, the appropriate Participant response to receiving
[CS]{acronym-label="CS" acronym-form="singular+short"} messages (namely,
those surrounding *Public Awareness*, *Exploit Public*, or *Attacks
Observed*) depends on the state of the [EM]{acronym-label="EM"
acronym-form="singular+short"} process.

-   Participants SHALL initiate embargo termination upon becoming aware
    of publicly available information about the vulnerability or its
    exploit code.

-   Participants SHOULD initiate embargo termination upon becoming aware
    of attacks against an otherwise unpublished vulnerability.

Table [\[tab:cvd_send\]](#tab:cvd_send){reference-type="ref"
reference="tab:cvd_send"} lists each [CVD]{acronym-label="CVD"
acronym-form="singular+short"} message type and the states in which that
message is appropriate to send along with the corresponding sender state
transition. Table
[\[tab:cvd_receive\]](#tab:cvd_receive){reference-type="ref"
reference="tab:cvd_receive"} lists the effects of receiving a
[CS]{acronym-label="CS" acronym-form="singular+short"} message to the
receiving Participant's state coupled with the expected response
message.

### General Transition Functions

Finally, for the sake of completeness, in Tables
[\[tab:gen_send\]](#tab:gen_send){reference-type="ref"
reference="tab:gen_send"} and
[\[tab:gen_receive\]](#tab:gen_receive){reference-type="ref"
reference="tab:gen_receive"}, we show that general inquiries,
acknowledgments, and errors are otherwise independent of the rest of the
processes. No state changes are expected to occur based on the receipt
of a General message. Note that we do not mean to imply that the
*content* of such a message is expected to have no effect on the
progression of a case, merely that the act of sending or receiving a
general message itself does not imply any necessary state change to
either the sender or receiver Participants.

Table [\[tab:gen_send\]](#tab:gen_send){reference-type="ref"
reference="tab:gen_send"} lists each general message and the states in
which it is appropriate to send along with the corresponding sender
state. Table
[\[tab:gen_receive\]](#tab:gen_receive){reference-type="ref"
reference="tab:gen_receive"} lists the effects of receiving a general
message to the receiving Participant's state coupled with the expected
response message.

## Formal MPCVD Protocol Redux {#sec:formal_protocol_redux}

In this chapter, we have formally defined an
[MPCVD]{acronym-label="MPCVD" acronym-form="singular+short"} protocol

$${protocol}_{MPCVD} = 
    \Big \langle 
        { \langle S_i \rangle }^N_{i=1}, 
        { \langle o_i \rangle }^N_{i=1},
        { \langle M_{i,j} \rangle}^N_{i,j=1},
        { succ }
    \Big \rangle$$

where

-   $N$ is a positive integer representing the number of
    [MPCVD]{acronym-label="MPCVD" acronym-form="singular+short"}
    Participants in a case and

-   $\langle S_i \rangle_{i=1}^N$ are $N$ disjoint finite sets in which
    each $S_i$ represents the set of states of a given Participant $i$
    [\[eq:protocol_states_reduced\]](#eq:protocol_states_reduced){reference-type="eqref"
    reference="eq:protocol_states_reduced"}, as refined by
    [\[eq:protocol_states_vendor\]](#eq:protocol_states_vendor){reference-type="eqref"
    reference="eq:protocol_states_vendor"},
    [\[eq:protocol_states_nonvendor_deployer\]](#eq:protocol_states_nonvendor_deployer){reference-type="eqref"
    reference="eq:protocol_states_nonvendor_deployer"},
    [\[eq:protocol_states_reporter\]](#eq:protocol_states_reporter){reference-type="eqref"
    reference="eq:protocol_states_reporter"}, and
    [\[eq:protocol_states_other\]](#eq:protocol_states_other){reference-type="eqref"
    reference="eq:protocol_states_other"}.

-   ${ \langle o_i \rangle }^N_{i=1}$ is the set of starting states
    across all Participants in which each $o_i$ is an element of $S_i$
    representing the initial state of each Participant $i$, as detailed
    in
    [\[eq:protocol_start_state_vendor\]](#eq:protocol_start_state_vendor){reference-type="eqref"
    reference="eq:protocol_start_state_vendor"}
    [\[eq:protocol_start_state_deployer\]](#eq:protocol_start_state_deployer){reference-type="eqref"
    reference="eq:protocol_start_state_deployer"},
    [\[eq:protocol_start_state_other\]](#eq:protocol_start_state_other){reference-type="eqref"
    reference="eq:protocol_start_state_other"}, and
    [\[eq:protocol_start_state_finder\]](#eq:protocol_start_state_finder){reference-type="eqref"
    reference="eq:protocol_start_state_finder"}.

-   $\langle M_{ij} \rangle_{i,j=1}^N$ are $N^2$ disjoint finite sets
    with $M_{ii}$ empty for all $i$. $M_{ij}$ represents the messages
    that can be sent from process $i$ to process $j$. A list of message
    types is defined in
    [\[eq:message_types\]](#eq:message_types){reference-type="eqref"
    reference="eq:message_types"} and summarized in Table
    [\[tab:message_types\]](#tab:message_types){reference-type="ref"
    reference="tab:message_types"}.

-   $succ$ is a partial function mapping for each $i$ and $j$,
    $$S_i \times M_{ij} \rightarrow S_i \textrm{ and } S_i \times M_{ji} \rightarrow S_i$$
    indicating the state changes arising from the sending and receiving
    of messages between Participants. The full set of transition
    function definitions for our protocol is shown in Tables
    [\[tab:rm_send\]](#tab:rm_send){reference-type="ref"
    reference="tab:rm_send"},
    [\[tab:rm_receive\]](#tab:rm_receive){reference-type="ref"
    reference="tab:rm_receive"},
    [\[tab:em_send\]](#tab:em_send){reference-type="ref"
    reference="tab:em_send"},
    [\[tab:em_receive\]](#tab:em_receive){reference-type="ref"
    reference="tab:em_receive"},
    [\[tab:cvd_send\]](#tab:cvd_send){reference-type="ref"
    reference="tab:cvd_send"},
    [\[tab:cvd_receive\]](#tab:cvd_receive){reference-type="ref"
    reference="tab:cvd_receive"},
    [\[tab:gen_send\]](#tab:gen_send){reference-type="ref"
    reference="tab:gen_send"}, and
    [\[tab:gen_receive\]](#tab:gen_receive){reference-type="ref"
    reference="tab:gen_receive"}.

A summary diagram of the [MPCVD]{acronym-label="MPCVD"
acronym-form="singular+short"} state model $S_i$ for an individual
Participant is shown in Figure
[\[fig:bingo_card\]](#fig:bingo_card){reference-type="ref"
reference="fig:bingo_card"}.


[^1]: As we discuss in
    §[\[sec:finder_hidden\]](#sec:finder_hidden){reference-type="ref"
    reference="sec:finder_hidden"}, the Finder's states
    $q^{rm} \in \{R,I,V\}$ are not observable to the
    [CVD]{acronym-label="CVD" acronym-form="singular+short"} process
    because Finders start coordination only when they have already
    reached $q^{rm} = A$.

[^2]: Effective coordination is usually improved with Participants'
    mutual awareness of each other's state, of course.

[^3]: "Yes-And" is a heuristic taken from improvisational theatre in
    which Participants are encouraged to agree with whatever their
    counterpart suggests and add to it rather than reject it outright.
    It serves as a good model for cooperation among parties who share an
    interest in a positive outcome.
