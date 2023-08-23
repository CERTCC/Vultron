# States {#sec:protocol_states}

Each Participant in an MPCVD case has a corresponding RM state, an EM state, and an overall CS state.
Therefore, we can represent a Participant's state as a triple comprising the state of each of these models.

!!! note "_Participant State_"

    A Participant's state is a triple comprising the state of each of the RM, EM, and CS models.

    $$q_{Participant} = (q^{rm},q^{em},q^{cs})$$

Good Participant situation awareness makes for good CVD decision making.

!!! note ""

    Participants SHOULD track the state of other Participants in a case
    to inform their own decision making as it pertains to the case.

An example object model to facilitate such tracking is given in
{== §[\[sec:case_object\]](#sec:case_object.md){reference-type="ref"
reference="sec:case_object"} ==}. 
However, the protocol we are developing is expected to function even when incomplete information is available to
any given Participant.

!!! note ""  
   
    Adequate operation of the protocol MUST NOT depend on perfect
    information across all Participants.

A generic state model for a CVD Participant can be composed from the
Cartesian product of $\mathcal{Q}^{rm}$, $\mathcal{Q}^{em}$, and
$\mathcal{Q}^{cs}$ as shown below.

!!! note "_Participant State Space_"

    A Participant's state is a triple comprising the state of each of the RM, EM, and CS models.
    The set of all possible Participant states is the Cartesian product of the RM, EM, and CS state sets.

    $$  S_i 
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

Note that the above definition splits the case state
($\mathcal{Q}^{cs}$) into chunks corresponding to the Vendor fix path
($vfd \xrightarrow{\mathbf{V}} Vfd \xrightarrow{\mathbf{F}} VFd \xrightarrow{\mathbf{D}} VFD$)
and the public-exploit-attack ($pxa \xrightarrow{\dots} PXA$) sub-models
from the [Case State Model](/topics/process_models/cs/index.md).
This is done for two reasons. 
First, it gives us a more compact notation to represent the 32 states of the CS model.
Second, as described in [Model Interactions](/topics/process_models/model_interactions/), it highlights the fact that 
the Vendor fix path represents the state of an individual Participant, whereas the public-exploit-attack sub-model 
represents facts about the world at large.
Because not all Participants
are Vendors or Deployers, Participants might not have a corresponding
state on the $vfd \xrightarrow{} VFD$ axis. Therefore, we add a null
element $\varnothing$ to the set of states representing the Vendor fix
path.

Thus, one might conclude that a total of 1,400 states is possible for each Participant.

!!! note "Participant State Space Size"

    $$  | S_i | = 
            % actor rm state
            | \mathcal{Q}^{rm} | \cdot 
            % embargo state
            | \mathcal{Q}^{em} | \cdot
            % case state
            | \mathcal{Q}^{cs} | 
            % multiply
            = 7 \cdot 5 \cdot (5 \cdot 2 \cdot 2 \cdot 2) = 1400$$

However, this dramatically overstates the possibilities for individual CVD Participant Roles because many of these
states will be unreachable to individual Participants.
In the remainder of this section, we detail these differences.

## Unreachable States

For any Participant, the RM $Closed$ state implies that the EM and CVD Case states do
not matter. 
Similarly, for any Participant, the RM $Start$ state represents a case that the
Participant doesn't even know about yet. 
Therefore, the $Start$ state also implies that the EM and CVD Case states do not matter. 
We use $*$ to represent the "don't care" value.

???+ note "Unreachable EM and CS States when RM is in  _Closed_ or _Start_"

    $$q^{rm} \in \{S,C\} \implies (q^{em} \in *) \cup (q^{cs} \in *)$$

A public exploit implies the vulnerability is public as well. In other
words, $q^{cs} \in \cdot\cdot\cdot pX \cdot$ is an ephemeral state that resolves
quickly to $q^{cs} \in \cdot\cdot\cdot PX \cdot$. (As a reminder, dots ($\cdot$)
in CVD case state notation indicate single-character wildcards.)

???+ note "Unreachable CS States when CS is in _Public_ or _Exploit_"

    $$q^{cs} \in \cdot\cdot\cdot pX \cdot \implies q^{cs} \in \cdot\cdot\cdot PX \cdot$$

Furthermore, when a vulnerability becomes public, the EM state no longer matters.

???+ note "Unreachable EM States when CS is in _Public_"

    $$q^{cs} \in \cdot\cdot\cdot PX \cdot \implies q^{em} \in *$$

Taken together, we can modify our state model to reflect these limitations.
The result is shown below.

!!! note "Participant States With Unreachable States Removed" 

    $$  S_i 
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

!!! note "Participant State Space Size With Unreachable States Removed"

    $$\begin{split}
    |S_i| &= 1 + \big(5 \cdot 5 \cdot (5 \cdot 1 \cdot 1 \cdot 2)\big) + \big(5 \cdot 1 \cdot (5 \cdot 1 \cdot 2 \cdot 2\big) + 1 \\
        %   &= 2 + 250 + 100
          &= 352
    \end{split}$$

## Vendors (Fix Suppliers)

Vendors are the sole providers of fixes.
Therefore, they are the only Participants in a CVD case for which the $Vfd \xrightarrow{\mathbf{F}} VFd \xrightarrow{\mathbf{D}} VFD$ 
path is possible.
Furthermore, since they are Vendors by definition, they do not have access to the $vfd$ state or the $\varnothing$ 
state that was just added.
As a Vendor has a report in $Received$, it is, by definition, at least in the $Vfd$ case state.

Vendors create fixes only when they are in the $Accepted$ RM state.
Because the $Received$, $Invalid$, and $Valid$ states come strictly *before* the $Accepted$ state in the RM DFA,
there is no way for the Vendor to be in either $VFd$ or $VFD$ while in any of those states.

???+ note "Vendor CS States When RM is in _Received_, _Invalid_, or _Valid_"

    $$q^{rm}_{Vendor} \in \{R,I,V\} \implies q^{cs}_{Vendor} \in Vfd\cdot\cdot\cdot$$

Vendors with the ability to deploy fixes themselves have access to three states in the fix path: $\{Vfd,~VFd,~VFD\}$. 
However, this is not always the case.
Vendor Participants without a deployment capability can only create fixes, limiting them to the middle two states in 
the fix path: $\{Vfd,~VFd\}$.
Additional discussion of the distinction between Vendors with and without a deployment capability can be found in the
{== Householder and Spring 2021 report [@householder2021state] ==}.

We apply these caveats to the generic model above to arrive at a Vendor state shown below.

!!! note "Vendor Participant State Space"

    $$  S_{i_{Vendor}} =
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
        \end{bmatrix} \textrm{unprioritized, maybe embargoed} \\
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
        \end{bmatrix}  \textrm{prioritized, maybe embargoed} \\
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
        \end{bmatrix}  \textrm{unprioritized, embargo irrelevant}  \\
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
        \end{bmatrix}  \textrm{prioritized, embargo irrelevant} \\
        {}\\
        (C, *, *) \\
        \end{cases}$$

The $\dagger$ on $VFD$ in the above indicates that the $VFD$ state is accessible only to Vendors with a deployment capability.
As tallied below, there are 128 possible states for a Vendor with deployment capability and 100 for those without.

!!! note "Vendor State Space Size"

    With deployment capability:

    $$  \begin{split}
            |S_{i_{\frac{Vendor}{Deployer}}}| = & 1 + \big(3 \cdot 5 \cdot (1 \cdot 1 \cdot 1 \cdot 2)\big) + \big(2 \cdot 5 \cdot (3 \cdot 1 \cdot 1 \cdot 2)\big) \\
            & + \big(3 \cdot 1 \cdot (1 \cdot 1 \cdot 2 \cdot 2)\big) + \big(2 \cdot 1 \cdot (3 \cdot 1 \cdot 2 \cdot 2)\big) + 1 \\
            % = & 2 + 30 + 60 + 12 + 24 \\
            = & 128 \\    
        \end{split}$$

    Without deployment capability:

    $$  \begin{split}
            |S_{i_{Vendor}}| = & 1 + \big(3 \cdot 5 \cdot (1 \cdot 1 \cdot 1 \cdot 2)\big) + \big(2 \cdot 5 \cdot (2 \cdot 1 \cdot 1 \cdot 2)\big) \\
            & + \big(3 \cdot 1 \cdot (1 \cdot 1 \cdot 2 \cdot 2)\big) + \big(2 \cdot 1 \cdot (2 \cdot 1 \cdot 2 \cdot 2)\big) + 1 \\
            % = & 2 + 30 + 40 + 12 + 16 \\
            = & 100 \\    
        \end{split}$$

## Non-Vendor Deployers

We just explained that not all Vendors are Deployers. 
Likewise, not all Deployers are Vendors.
Most CVD cases leave Non-Vendor Deployers entirely out of the CVD process, so their appearance is expected to be rare in
actual cases.
However, there are scenarios when an MPCVD case may include Non-Vendor Deployers, such as when a vulnerability in some 
critical infrastructure component is being handled or when the MPCVD protocol is used in the context of a Vulnerability
Disclosure Program (VDP).
These Non-Vendor Deployers participate only in the $d \xrightarrow{\mathbf{D}} D$ transition on the fix path.
Similar to the Vendor scenario in {== §[1.3.2](#sec:vendor_states){reference-type="ref"
reference="sec:vendor_states"} ==}, it is expected that Deployers actually deploy fixes only when they are in the 
RM $Accepted$ state (implying their intent to deploy).
Therefore, their set of possible states is even more restricted than Vendors, as shown below.

!!! note "Non-Vendor Deployer Participant State Space"
    $$  S_{i_{Deployer}} =
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
        \end{bmatrix} \textrm{unprioritized, maybe embargoed} \\
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
        \end{bmatrix}\textrm{prioritized, maybe embargoed} \\
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
        \end{bmatrix} \textrm{unprioritized, embargo irrelevant}  \\
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
        \end{bmatrix} \textrm{prioritized, embargo irrelevant} \\
        {}\\
        (C, *, *) \\
        \end{cases}$$

Thus, Non-Vendor Deployers can be expected to be in 1 of 100 possible
states, as we show next.

!!! note "Non-Vendor Deployer State Space Size"
    $$  \begin{split}
            |S_{i_{Deployer}}| = & 1 + \big(3 \cdot 5 \cdot (1 \cdot 1 \cdot 1 \cdot 2)\big) + \big(2 \cdot 5 \cdot (2 \cdot 1 \cdot 1 \cdot 2)\big) \\
            & + \big(3 \cdot 1 \cdot (1 \cdot 1 \cdot 2 \cdot 2)\big) + \big(2 \cdot 1 \cdot (2 \cdot 1 \cdot 2 \cdot 2)\big) + 1 \\
            % = & 2 + 30 + 40 + 12 + 16 \\
            = & 100 \\    
        \end{split}$$

## Non-Vendor, Non-Deployer Participants {#sec:other_participants}

Finally, CVD cases often involve Participants who are neither Vendors nor Deployers.
Specifically, Finder/Reporters fall into this category, as do Coordinators.
Other roles, as outlined in the {== *CERT Guide to Coordinated Vulnerability Disclosure* [@householder2017cert] ==},
could be included here as well.
Because they do not participate directly in the Vendor fix path, these Non-Vendor, Non-Deployer CVD Participants fall
into the $\varnothing$ case substate we added above.
Their state model is shown below.

!!! note "Non-Vendor, Non-Deployer Participant State Space"

    $$  S_{i_{Other}} = 
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
        \end{bmatrix} \textrm{ maybe embargoed}\\
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
        \end{bmatrix} \textrm{ embargo irrelevant} \\
        {} \\
        (C,*,*) \\
        \end{cases}$$

Non-Vendor Non-Deployer CVD Participants (Finder/Reporters, Coordinators, etc.) will be in 1 of 72 states, as calculated
below.

!!! note "Non-Vendor, Non-Deployer Participant State Space Size"

    $$  \begin{split}
            |S_{i_{Other}}| = & 1 + \big(5 \cdot 5 \cdot (1 \cdot 1 \cdot 1 \cdot 2)\big) + \big(5 \cdot 1 \cdot (1 \cdot 1 \cdot 2 \cdot 2)\big) + 1 \\
            % = & 2 + 50 + 20\\
            = & 72 \\    
        \end{split}$$

### Finder-Reporters

As we discussed in [RM Interactions](/topics/process_models/rm/rm_interactions/#the-secret-lives-of-finders),
the early Finder states are largely hidden from view from other CVD Participants unless they choose to engage
in the CVD process in the first place.
Therefore, for a CVD protocol, we only need to care about Finder states once they have reached RM $Accepted$.
Coincidentally, this is also a convenient way to mark the transition from Finder to Reporter.

!!! note "Finder-Reporter State Space"

    $$  S_{i_{Reporter}} = 
        \begin{cases}
        (S,*,*) \textrm{(hidden)}\\
        (R,*,*) \textrm{(hidden)}\\
        (I,*,*) \textrm{(hidden)}\\
        (V,*,*) \textrm{(hidden)}\\
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
        \end{bmatrix} \textrm{maybe embargoed} \\
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
        \end{bmatrix} \textrm{embargo irrelevant} \\
        {} \\
        (C,*,*) \\
        \end{cases}$$

Thus, for all practical purposes, we can ignore the hidden states in the above and conclude that Finders who go on to
become Reporters have only 29 possible states during a CVD case.

!!! note "Finder-Reporter State Space Size"
    $$  \begin{split}
            |S_{i_{Reporter}}| = & \big(2 \cdot 5 \cdot (1 \cdot 1 \cdot 1 \cdot 2)\big) + \big(2 \cdot 1 \cdot (1 \cdot 1 \cdot 2 \cdot 2)\big) + 1 \\
            % = & 20 + 8 + 1 \\
            = & 29 \\    
        \end{split}$$

## A Lower Bounds on MPCVD State Space

!!! note inline end "Generic MPCVD State Space Size Formula"

    $$|S_{total}| = \prod_{i=1}^{N} |S_i|$$

Now we can touch on the lower bounds of the state space of an MPCVD case.
Generically, we would expect the state space for $N$ Participants to
take the form given at right.


The upper bound on the MPCVD state space is simply $352^N \approx 10^{2.55N}$.
However, because of the Role-specific limits just described, we already know that this overcounts the possible states
significantly.
We can do better still.
If we ignore transient states while Participants converge on a consistent view of the global state of a case, we can
drastically reduce the state space for an MPCVD case.
Why?
There are two reasons:

1.  Because they represent facts about the outside world, the eight
    $\cdot\cdot\cdot pxa \rightarrow \cdot\cdot\cdot PXA$ CS substates are global to the case, not
    to individual Participants. This means all Participants should
    rapidly converge to the same substate.

2.  Similarly, the five EM states are also global to the case and should converge rapidly.

Given these two observations, we can pull those Participant-agnostic terms out of the state calculations for individual Participants,

!!! note "MPCVD State Space With Participant-Agnostic Terms Factored Separately"

    $$|S_{total}| = \prod_{i=1}^{N} |S_i| = |S_{global}| \times \prod_{i=1}^{N} |S_{Participant}|$$

    where 

    $$ |S_{global}| = 8 \times 5 = 40 $$

which leaves

!!! note "Participant-Specific State Spaces"

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

!!! note "MPCVD State Space Size Formula"

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

-   A two-party (Finder-Vendor) case might have a lower bound state space of $40 \times 3 \times 16 = 1,920$ states.

-   A case like Meltdown/Spectre (with six Vendors and no Coordinators) might have $40 \times 3 \times 16^{6} \approx 10^{9}$ states.

-   A large, but not atypical, 200-Vendor case handled by the CERT/CC might have
    $40 \times 3 \times 16^{200} \times 7 \approx 10^{244}$ possible configurations.

-   In the case of the log4j vulnerability CVE-2021-44228 in December
    2021, the CERT/CC notified around 1,600 Vendors after
    the vulnerability had been made public {== [@vu930724] ==}. Had this been an
    embargoed disclosure, the case would have a total state space around
    $10^{2000}$.

That said, while these are dramatic numbers, the reader is reminded that the whole point of the MPCVD protocol is to
*coordinate* the process so that it is not just hundreds or thousands of Participants behaving randomly.

## Starting States

Each Participant begins a case in the state where the report management
process is in the start state, there is no embargo in place, and the
case has not made any progress.

!!! note "Participant Start State Formally Defined"

    $$o_i = (o_i^{rm},~o_i^{em},~o_i^{cs}) = (S,N,vfdpxa)$$

Following the discussion above, the starting states for Vendors,
Deployers, and other Participants are shown below.

!!! note "Participant Start States"

    | Participant Role | Start State ($o_i$)|
    |------------------|-------------|
    | Vendor           | $(S,N,vfdpxa)$ |
    | Deployer         | $(S,N,dpxa)$ |
    | Other            | $(S,N,pxa)$ |
    | Finder/Reporter  | $(A,N,pxa)$ |


For a case to really begin, the Finder must at least reach the $A$ state.
Therefore, at the point when a second party finds out about the vulnerability from a Finder,
the Finder/Reporter is presumed to be already at $q_{Finder}=(A, N, pxa)$.

We will show in [Transitions](/reference/formal_protocol/transitions.md) how this plays out.
But first, we need to define the message types that can be exchanged between Participants.
