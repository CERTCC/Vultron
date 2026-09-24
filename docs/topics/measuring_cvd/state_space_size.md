---
description: How large the Vultron protocol state space is for each participant role and for a whole case, and why coordination keeps it tractable.
stakeholder_type: [process-researcher]
level: 500
---

# About the Size of the Protocol State Space

The [States](../../reference/formal_protocol/states.md) reference page defines each participant's state as a triple $(q^{rm}, q^{em}, q^{cs})$ of its Report Management (RM), Embargo Management (EM), and Case State (CS) states.
This page asks a different question: how many of those states can a participant actually occupy, and how large does the state space of a whole Multi-Party Coordinated Vulnerability Disclosure (MPCVD) case become?
The answers explain why a protocol that coordinates participants matters: left uncoordinated, even a modest case has more possible states than anyone could reason about.

## Counting every combination

Taking the Cartesian product of the three state sets at face value, one might conclude that a total of 1,400 states is possible for each participant.

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

However, this dramatically overstates the possibilities for individual Coordinated Vulnerability Disclosure (CVD) participant roles, because many of these states are unreachable.

## Removing unreachable states

The [unreachable-state constraints](../../reference/formal_protocol/states.md#unreachable-states) on the States page remove combinations that cannot occur: nothing matters for a participant whose RM state is $Start$ or $Closed$, a public exploit implies a public vulnerability, and the EM state no longer matters once the vulnerability is public.
Once those combinations are removed, each participant must be in one of 352 possible states.

!!! note "Participant State Space Size With Unreachable States Removed"

    $$\begin{split}
    |S_i| &= 1 + \big(5 \cdot 5 \cdot (5 \cdot 1 \cdot 1 \cdot 2)\big) + \big(5 \cdot 1 \cdot (5 \cdot 1 \cdot 2 \cdot 2\big) + 1 \\
        %   &= 2 + 250 + 100
          &= 352
    \end{split}$$

The role a participant plays narrows this further, as the following sections show.
"Finder" is used below in its everyday sense of whoever discovered the vulnerability; the protocol's roles are listed in the [Vultron specification](../../reference/vultron-spec/index.md#22-roles), where a finder takes part as a Reporter.

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

???+ note "Vendor CS States When RM is in *Received*, *Invalid*, or *Valid*"

    $$q^{rm}_{Vendor} \in \{R,I,V\} \implies q^{cs}_{Vendor} \in Vfd\cdot\cdot\cdot$$

Vendors with the ability to deploy fixes themselves have access to three states in the fix path: $\{Vfd,~VFd,~VFD\}$.
However, this is not always the case.
Vendor Participants without a deployment capability can only create fixes, limiting them to the middle two states in
the fix path: $\{Vfd,~VFd\}$.
Additional discussion of the distinction between Vendors with and without a deployment capability can be found in [A State-Based Model for Multi-Party Coordinated Vulnerability Disclosure](https://resources.sei.cmu.edu/library/asset-view.cfm?assetid=735513){:target="_blank"}.

Applying these caveats to the [generic Participant state space](../../reference/formal_protocol/states.md) yields the Vendor state shown below.

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

As explained above, not all Vendors are Deployers.
Likewise, not all Deployers are Vendors.
Most CVD cases leave Non-Vendor Deployers entirely out of the CVD process, so their appearance is expected to be rare in
actual cases.
However, there are scenarios when an MPCVD case may include Non-Vendor Deployers, such as when a vulnerability in some
critical infrastructure component is being handled or when the Vultron Protocol is used in the context of a Vulnerability
Disclosure Program (VDP).
These Non-Vendor Deployers participate only in the $d \xrightarrow{\mathbf{D}} D$ transition on the fix path.
Similar to the [Vendor](#vendors-fix-suppliers) scenario above, it is expected that Deployers actually deploy fixes only when they are in the
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
states, as shown next.

!!! note "Non-Vendor Deployer State Space Size"
    $$  \begin{split}
            |S_{i_{Deployer}}| = & 1 + \big(3 \cdot 5 \cdot (1 \cdot 1 \cdot 1 \cdot 2)\big) + \big(2 \cdot 5 \cdot (2 \cdot 1 \cdot 1 \cdot 2)\big) \\
            & + \big(3 \cdot 1 \cdot (1 \cdot 1 \cdot 2 \cdot 2)\big) + \big(2 \cdot 1 \cdot (2 \cdot 1 \cdot 2 \cdot 2)\big) + 1 \\
            % = & 2 + 30 + 40 + 12 + 16 \\
            = & 100 \\
        \end{split}$$

## Non-Vendor, Non-Deployer Participants

Finally, CVD cases often involve Participants who are neither Vendors nor Deployers.
Specifically, Finder/Reporters fall into this category, as do Coordinators.
Other roles, as outlined in the [*CERT Guide to Coordinated Vulnerability Disclosure*](https://certcc.github.io/CERT-Guide-to-CVD){:target="_blank"},
could be included here as well.
Because they do not participate directly in the Vendor fix path, these Non-Vendor, Non-Deployer CVD Participants fall
into the $\varnothing$ case substate that the [generic Participant state space](../../reference/formal_protocol/states.md) adds for them.
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

As discussed in [RM Interactions](../process_models/rm/rm_interactions.md#the-secret-lives-of-finders),
the early Finder states are largely hidden from view from other CVD Participants unless they choose to engage
in the CVD process in the first place.
Therefore, for a CVD protocol, Finder states matter only once they have reached RM $Accepted$.
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

Thus, for all practical purposes, the hidden states above can be ignored: Finders who go on to
become Reporters have only 29 possible states during a CVD case.

!!! note "Finder-Reporter State Space Size"
    $$  \begin{split}
            |S_{i_{Reporter}}| = & \big(2 \cdot 5 \cdot (1 \cdot 1 \cdot 1 \cdot 2)\big) + \big(2 \cdot 1 \cdot (1 \cdot 1 \cdot 2 \cdot 2)\big) + 1 \\
            % = & 20 + 8 + 1 \\
            = & 29 \\
        \end{split}$$

## A Lower Bound on the MPCVD State Space

!!! note inline end "Generic MPCVD State Space Size Formula"

    $$|S_{total}| = \prod_{i=1}^{N} |S_i|$$

The lower bound on the state space of an MPCVD case follows.
Generically, the state space for $N$ Participants
takes the form given at right.

The upper bound on the MPCVD state space is $352^N \approx 10^{2.55N}$.
However, because of the Role-specific limits just described, this overcounts the possible states
significantly.
A tighter bound is possible.
Ignoring transient states while Participants converge on a consistent view of the global state of a case
drastically reduces the state space for an MPCVD case.
Why?
There are two reasons:

1. Because they represent facts about the outside world, the eight
    $\cdot\cdot\cdot pxa \rightarrow \cdot\cdot\cdot PXA$ CS substates are global to the case, not
    to individual Participants. This means all Participants should
    rapidly converge to the same substate.

2. Similarly, the five EM states are also global to the case and should converge rapidly.

Given these two observations, those Participant-agnostic terms can be pulled out of the state calculations for individual Participants,

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

So the state space looks like

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

With these values in mind:

- A two-party (Finder-Vendor) case might have a lower bound state space of $40 \times 3 \times 16 = 1,920$ states.

- A case like Meltdown/Spectre (with six Vendors and no Coordinators) might have $40 \times 3 \times 16^{6} \approx 10^{9}$ states.

- A large, but not atypical, 200-Vendor case handled by the CERT/CC might have
    $40 \times 3 \times 16^{200} \times 7 \approx 10^{244}$ possible configurations.

- In the case of the log4j vulnerability [CVE-2021-44228](https://www.kb.cert.org/vuls/id/930724){:target="_blank"} in December
    2021, the CERT/CC notified around 1,600 Vendors after the vulnerability had been made public. Had this been an
    embargoed disclosure, the case would have a total state space around $10^{2000}$.

That said, while these are dramatic numbers, the reader is reminded that the whole point of the Vultron Protocol is to
*coordinate* the process so that it is not just hundreds or thousands of Participants behaving randomly.

## Where to go next

- [Messages](../../reference/formal_protocol/messages.md) defines the message types participants exchange.
- [Transitions](../../reference/formal_protocol/transitions.md) shows how those messages move each participant through the states counted here.
