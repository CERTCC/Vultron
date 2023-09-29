# A State-based model for CVD {#sec:model}

Our goal is to create a toy model of the MPCVD process that can shed light on the more
complicated real thing. We begin by building up a state map of what
FIRST refers to
as bilateral CVD [@first2020mpcvd], which we will later
expand into the MPCVD space. We start by defining a set of
events of interest. We then use these to construct model states and the
transitions between them.

## Events in a Vulnerability Lifecycle {#sec:events}

::: {#tab:lifecycle_events}
  -------------------------------------------------------------------------------------------
      Arbaugh et al.      Frei et                   Bilge et                 Our Model
   [@arbaugh2000windows]  al. [@frei2010modeling]   al. [@bilge2012before]   
  ----------------------- ------------------------- ------------------------ ----------------
           Birth          creation ($t_{creat}$)    introduced ($t_c$)       (implied)

         Discovery        discovery ($t_{disco}$)   n/a                      (implied)

        Disclosure        n/a                       discovered by vendor     Vendor Awareness
                                                    ($t_d$)                  ($\mathbf{V}$)

            n/a           patch availability        n/a                      Fix Ready
                          ($t_{patch}$)                                      ($\mathbf{F}$)

        Fix Release       n/a                       patch released ($t_p$)   Fix Ready and
                                                                             Public Awareness

        Publication       public disclosure         disclosed publicly       Public Awareness
                          ($t_{discl}$)             ($t_0$)                  ($\mathbf{P}$)

            n/a           patch installation        patch deployment         Fix Deployed
                          ($t_{insta}$)             completed ($t_a$)        ($\mathbf{D}$)

    Exploit Automation    exploit availability      Exploit released in wild n/a
                          ($t_{explo}$)             ($t_e$)                  

    Exploit Automation    n/a                       n/a                      Exploit Public
                                                                             ($\mathbf{X}$)

    Exploit Automation    n/a                       n/a                      Attacks Observed
                                                                             ($\mathbf{A}$)

            n/a           n/a                       anti-virus signatures    n/a
                                                    released ($t_s$)         
  -------------------------------------------------------------------------------------------

  : Vulnerability Lifecycle Events: Comparing Models. Symbols for our
  model are defined in §[2.4](#sec:transitions){reference-type="ref"
  reference="sec:transitions"}.
:::

The goal of this section is to establish a model of events that affect
the outcomes of vulnerability disclosure. Our model builds on previous
models of the vulnerability lifecycle, specifically those of Arbaugh et
al. [@arbaugh2000windows], Frei et al. [@frei2010modeling], and Bilge
and et al. [@bilge2012before]. A more thorough literature review of
vulnerability lifecycle models can be found in [@lewis2017global]. We
are primarily interested in events that are usually observable to the
stakeholders of a CVD case. Stakeholders include software
vendors, vulnerability finder/reporters, coordinators, and
deployers [@householder2017cert]. A summary of this model comparison is
shown in Table [2.1](#tab:lifecycle_events){reference-type="ref"
reference="tab:lifecycle_events"}.

Since we are modeling only the disclosure process, we assume the
vulnerability both exists and is known to at least someone. Therefore we
ignore the *birth* (*creation*, *introduced*) and *discovery* states as
they are implied at the beginning of all possible vulnerability
disclosure histories. We also omit the *anti-virus signatures released*
event from [@bilge2012before] since we are not attempting to model
vulnerability management operations in detail.

The first event we are interested in modeling is *Vendor Awareness*.
This event corresponds to *Disclosure* in [@arbaugh2000windows] and
*vulnerability discovered by vendor* in [@bilge2012before] (this event
is not modeled in [@frei2010modeling]). In the interest of model
simplicity, we are not concerned with *how* the vendor came to find out
about the vulnerability's existence---whether it was found via internal
testing, reported by a security researcher, or noticed as the result of
incident analysis.

The second event we include is *Public Awareness* of the vulnerability.
This event corresponds to *Publication* in [@arbaugh2000windows], *time
of public disclosure* in [@frei2010modeling], and *vulnerability
disclosed publicly* in [@bilge2012before]. The public might find out
about a vulnerability through the vendor's announcement of a fix, a news
report about a security breach, a conference presentation by a
researcher, by comparing released software versions as
in [@xu2020patch; @xiao2020mvp], or a variety of other means. As above,
we are primarily concerned with the occurrence of the event itself
rather than the details of *how* the public awareness event arises.

The third event we address is *Fix Readiness*, by which we refer to the
vendor's creation and possession of a fix that *could* be deployed to a
vulnerable system, *if* the system owner knew of its existence. Here we
differ somewhat
from [@arbaugh2000windows; @frei2010modeling; @bilge2012before] in that
their models address the *release* of the fix rather than its
*readiness* for release.

The reason for this distinction will be made clear, but first we must
mention that *Fix Deployed* is simply that: the fix exists, and it has
been deployed.

We chose to include the *Fix Ready*, *Fix Deployed*, and *Public
Awareness* events so that our model could better accommodate two common
modes of modern software deployment:

-   *shrinkwrap* - The traditional distribution mode in which the vendor
    and deployer are distinct entities and deployers must be made aware
    of the fix before it can be deployed. In this case, which
    corresponds to the previously mentioned *fix release* event, both
    fix readiness and public awareness are necessary for the fix to be
    deployed.

-   *SaaS* - A more recent delivery mode in which the vendor also plays
    the role of deployer. In this distribution mode, fix readiness can
    lead directly to fix deployed with no dependency on public
    awareness.

We note that so-called *silent fixes* by vendors can sometimes result in
a fix being deployed without public awareness even if the vendor is not
the deployer. Thus, it is possible (but unlikely) for *fix deployed* to
occur before *public awareness* even in the *shrinkwrap* case above. It
is also possible, and somewhat more likely, for *public awareness* to
occur before *fix deployed* in the *SaaS* case as well.

We diverge
from [@arbaugh2000windows; @frei2010modeling; @bilge2012before] again in
our treatment of exploits and attacks. Because attacks and exploit
publication are often discretely observable events, the broader concept
of *exploit automation* in [@arbaugh2000windows] is insufficiently
precise for our use. Both [@frei2010modeling; @bilge2012before] focus on
the availability of exploits rather than attacks, but the observability
of their chosen events is hampered by attackers' incentives to maintain
stealth. Frei et al. [@frei2010modeling] uses *exploit availability*,
whereas Bilge et al. [@bilge2012before] calls it *exploit released in
wild*. Both refer to the state in which an exploit is known to exist.
This can arise for at least two distinct reasons, which we wish to
differentiate:

-   *exploit public*---the method of exploitation for a vulnerability
    was made public in sufficient detail to be reproduced by others.
    Posting PoC
    code to a widely available site or including the exploit in a
    commonly available exploit tool meets this criteria; privately held
    exploits do not.

-   *attacks observed*---the vulnerability was observed to be exploited
    in attacks. This case requires evidence that the vulnerability was
    exploited; we can then presume the existence of an exploit
    regardless of its availability to the public. Analysis of malware
    from an incident might meet *attacks observed* but not *exploit
    public*, depending on how closely the attacker holds the malware.
    Use of a public exploit in an attack meets both *exploit public* and
    *attacks observed*.

Therefore, while we appreciate the existence of a hidden *exploit
exists* event as causal predecessor of both *exploit public* and
*attacks observed*, we assert no causal relationship between exploit
public and attacks observed in our model. We make this choice in the
interest of observability. The *exploit exists* event is difficult to
consistently observe independently. Its occurrence is nearly always
inferred from the observation of either *exploit public* or *attacks
observed*.

Further discussion of related work can be found in
§[7](#sec:related_work){reference-type="ref"
reference="sec:related_work"}.

## Notation {#sec:notation}

Before we discuss CVD states
(§[2.3](#sec:states){reference-type="ref" reference="sec:states"}),
transitions (§[2.4](#sec:transitions){reference-type="ref"
reference="sec:transitions"}), or possible histories
(§[3](#sec:poss_hist){reference-type="ref" reference="sec:poss_hist"})
in the vulnerability life cycle, we need to formally define our terms.
In all of these definitions, we take standard Zermelo-Fraenkel set
theory. The concept of sequences extends set theory to include a concept
of ordered sets. From them, we adopt the following notation:

-   $\{ \dots \}$An unordered set which makes no assertions about
    sequence

-   $( \dots )$An ordered set in which the items occur in that sequence

-   The normal proper subset ($\subset$), equality ($=$), and subset
    ($\subseteq$) relations between sets

-   The precedes ($\prec$) relation on members of an ordered set:
    $\sigma_i \prec \sigma_j \textrm{ if and only if } \sigma_i,\sigma_j \in s \textrm{ and } i < j$
    where $s$ is a sequence as defined in
    [\[eq:sequence\]](#eq:sequence){reference-type="eqref"
    reference="eq:sequence"}

## Deterministic Finite State Automata {#sec:states}

Transitions during CVD resemble in that the transitions
available to the current state are dependent on the state itself.
Although DFAs are
often used to determine whether the final or end state is acceptable,
for analyzing CVD
we are more interested in the order of the transitions. The usual
DFA notation will
still be effective for this modeling goal.

is defined as a 5-tuple $(\mathcal{Q},\Sigma,\delta,q_0,F)
~$[@kandar2013automata].

-   $\mathcal{Q}$ is a finite set of states

-   $\Sigma$ is a finite set of input symbols

-   $\delta$ is a transition function
    $\delta: \mathcal{Q} \times \Sigma \xrightarrow{} \mathcal{Q}$

-   $q_0 \in \mathcal{Q}$ is an initial state

-   $\mathcal{F} \subseteq \mathcal{Q}$ is a set of final (or accepting)
    states

In our model, the state of the world is a specification of the current
status of all the events in the vulnerability lifecycle model described
in §[2.1](#sec:events){reference-type="ref" reference="sec:events"}. We
represent each of these statuses in vulnerability coordination by a
letter for that part of the state of the world. For example, $v$ means
no vendor awareness and $V$ means vendor is aware. The complete set of
status labels is given in
Table [2.2](#tab:event_status){reference-type="ref"
reference="tab:event_status"}.

::: {#tab:event_status}
   Status  Meaning
  -------- --------------------------------------
    $v$    Vendor is not aware of vulnerability
    $V$    Vendor is aware of vulnerability
    $f$    Fix is not ready
    $F$    Fix is ready
    $d$    Fix is not deployed
    $D$    Fix is deployed
    $p$    Public is not aware of vulnerability
    $P$    Public is aware of vulnerability
    $x$    No exploit has been made public
    $X$    Exploit has been made public
    $a$    No attacks have been observed
    $A$    Attacks have been observed

  : Event status labels
:::

A state $q$ represents the status of each of the six events. The
possible states are all the combinations of the six event statuses. For
state labels, lowercase letters designate events that have not occurred
and uppercase letters designate events that have occurred in a
particular state. For example, the state $VFdpXa$ represents vendor is
aware, fix is ready, fix not deployed, no public awareness, exploit is
public, and no attacks. The order in which the events occurred does not
matter when defining the state. However, we will observe a notation
convention keeping the letter names in the same case-insensitive order
$(v,f,d,p,x,a)$.

All vulnerabilities start in the base state $q_0$ in which no events
have occurred. $$\label{eq:q_0}
    q_0 = vfdpxa$$ The lone final state in which all events have
occurred is $VFDPXA$. $$\label{eq:F}
\mathcal{F} = \{ VFDPXA \}$$ Note that this is a place where our model
of vulnerability lifecycle histories diverges from what we expect to
observe in vulnerability cases in the real world. There is ample
evidence that most vulnerabilities never have exploits published or
attacks observed [@householder2020historical; @jacobs2019exploit].
Therefore, practically speaking we might expect vulnerabilities to wind
up in one of
$$\mathcal{F}^\prime = \{ {VFDPxa}, {VFDPxA}, {VFDPXa}, {VFDPXA} \}$$ at
the time a case is closed. However, because we are modeling the
observation of events as the transitions of a DFA, we allow for the
possibility that an observed history remains incomplete at the time of
case closure---in other words, it remains possible for exploits to be
published or attacks to be observed long after a
CVD case has been
closed.

Intermediate states can be any combination of statuses, with the caveats
elaborated in §[2.4](#sec:transitions){reference-type="ref"
reference="sec:transitions"}. In other words, valid states must contain
one of the following strings: $vfd$, $Vfd$, $VFd$, or $VFD$.

As a result, there are thirty-two possible states, which we define as
the set of all states $\mathcal{Q}$ in
[\[eq:all_states\]](#eq:all_states){reference-type="eqref"
reference="eq:all_states"}.

$$\begin{split}    
% \begin{align*}
\label{eq:all_states}
    \mathcal{Q} \stackrel{\mathsf{def}}{=}\{&vfdpxa, vfdPxa, vfdpXa, vfdPXa, \\
    &vfdpxA, vfdPxA, vfdpXA, vfdPXA, \\
 &Vfdpxa, VfdPxa, VfdpXa, VfdPXa, \\
 &VfdpxA, VfdPxA, VfdpXA, VfdPXA, \\
 &VFdpxa, VFdPxa, VFdpXa, VFdPXa, \\
 &VFdpxA, VFdPxA, VFdpXA, VFdPXA, \\
&VFDpxa, VFDPxa, VFDpXa, VFDPXa, \\
&VFDpxA, VFDPxA, VFDpXA, VFDPXA \}
% \end{align*}
\end{split}$$

When referring to a subset of states from $\mathcal{Q}$, any unlisted
status remains unconstrained. For example,
$$\mathcal{Q}_{VFdP} = {VFdP} = \{{VFdPxa}, {VFdPxA}, {VFdPXa}, {VFdPXA}\}$$
In most cases, we will use the non-subscripted notation (e.g., $VFdP$).
We will use the subscripted notation when it is needed to avoid
confusion---for example, to disambiguate the status $v$ from the set of
states $\mathcal{Q}_v \subset \mathcal{Q}$ in which the status $v$
holds.

## State Transitions {#sec:transitions}

In this section, we elaborate on the input symbols and transition
function for our DFA.

### Input Symbols

The input symbols to our DFA correspond to observations of the events
outlined in Table [2.1](#tab:lifecycle_events){reference-type="ref"
reference="tab:lifecycle_events"}. For our model, an input symbol
$\sigma$ is "read" when a participant observes a change in status (the
vendor is notified, an exploit has been published, etc.). For the sake
of simplicity, we begin with the assumption that observations are
globally known---that is, a status change observed by any
CVD participant is
known to all. In the real world, the CVD process itself is well poised to ensure
eventual consistency with this assumption through the communication of
perceived case state across coordinating parties. We define the set of
input symbols for our DFA as:

$$\label{eq:events}
    \Sigma \stackrel{\mathsf{def}}{=}\{\mathbf{V},\mathbf{F},\mathbf{D},\mathbf{P},\mathbf{X},\mathbf{A}\}$$

### Transition Function {#sec:transition_function}

transitions between states according to its transition function $\delta$
based on which symbol is input to $\delta$. On our way to defining the
transition function $\delta$ for the complete model, we build up the
allowed state transitions according to subsets of the complete set of
six event statuses. State transitions correspond to the occurrence of a
single event $\sigma \in \Sigma$. Because states correspond to the
status of events that have or have not occurred, and all state
transitions are non-reversible, the result will be an acyclic directed
graph of states beginning at $q_0={vfdpxa}$ and ending at
$\mathcal{F}=\{VFDPXA\}$ with allowed transitions as the edges.

In our model, many inputs would represent errors because no transition
is possible given the model constraints we are about to describe. Yet
requires a transition from every state for every possible input value.
In the transition function tables to follow, we represent these
transitions as "-". In an implementation these would result in an error
condition and rejection of the input string. The state diagrams likewise
omit the error state, although it is implied for any transition not
explicitly depicted.

It is common to use subscripts on the transition function $\delta$
corresponding to the partial function $\delta_\sigma$ on states for a
specific symbol $\sigma \in \Sigma$. However, because the symbols in
$\Sigma$ are so closely tied to both the state names and the transitions
between them, we will avoid the subscripts and just use the symbols
themselves (bold capital letters) as proxies for the subscripted
transition function. For notation purposes, transitions between sets of
states will use an arrow with the specific event $\sigma \in \Sigma$ as
its label ($\xrightarrow{\sigma}$). For example,
$${vfdpxa} \xrightarrow{\mathbf{V}} {Vfdpxa}$$ is equivalent to
$$\delta_{V}(vfdpxa) = {Vfdpxa} \mathrm{~and~also~}\delta({vfdpxa},\mathbf{V})={Vfdpxa}$$
and indicates the transition from the base state caused by notifying the
vendor ($\mathbf{V}$).

##### Vendor Fix Path {#sec:vendor_axis}

::: {#tab:delta_vfd}
   State ($q$)   $\mathbf{V}$   $\mathbf{F}$   $\mathbf{D}$
  ------------- -------------- -------------- --------------
      $vfd$         $Vfd$            \-             \-
      $Vfd$           \-           $VFd$            \-
      $VFd$           \-             \-           $VFD$
      $VFD$           \-             \-             \-

  : Transition function $\delta_{VFD}$ for the vendor fix path
:::

<figure id="fig:vfd_map">

<figcaption>Submap of vendor fix path state transitions (<span
class="math inline"><strong>V</strong></span>, <span
class="math inline"><strong>F</strong></span>, <span
class="math inline"><strong>D</strong></span>)</figcaption>
</figure>

The primary aspect of our model is the vendor fix flow. The relevant
events and corresponding transitions in this dimension are Vendor
Awareness ($\mathbf{V}$), Fix Available ($\mathbf{F}$), and Fix Deployed
($\mathbf{D}$). A vendor cannot produce a fix and make it ready if the
vendor is not aware of the problem, and the fix cannot be deployed if it
is not ready. Therefore, we take the precedence relation
$\mathbf{V} \prec \mathbf{F} \prec \mathbf{D}$ as a strong constraint on
possible sequences.

The DFA specification for this submodel is given in
[\[eq:vfd_dfa\]](#eq:vfd_dfa){reference-type="eqref"
reference="eq:vfd_dfa"}. The resulting state subsets and transitions are
as shown in Table [2.3](#tab:delta_vfd){reference-type="ref"
reference="tab:delta_vfd"} and Figure
[2.1](#fig:vfd_map){reference-type="ref" reference="fig:vfd_map"}. The
double circle in Figure [2.1](#fig:vfd_map){reference-type="ref"
reference="fig:vfd_map"} and subsequent state diagrams indicates the
final state $\mathcal{F}$ for that submap.

$$\label{eq:vfd_dfa}
\begin{split}
    \mathcal{Q}_{VFD} =&\,\{vfd,Vfd,VFd,VFD\}\\
    \Sigma_{VFD} =&\,\{\mathbf{V},\mathbf{F},\mathbf{D}\}\\
    \delta_{VFD} =&\,\textrm{see~Table~\ref{tab:delta_vfd}}\\
    q^0_{VFD} =&\,vfd\\
    \mathcal{F}_{VFD} =&\,\{VFD\}
\end{split}$$

##### Private vs Public Awareness

A second aspect of vulnerability disclosure is whether or not a
vulnerability is known to the public. The public may become aware of a
vulnerability for a number of reasons, including:

-   the vendor publishes a fix

-   the researcher publishes a report about the vulnerability

-   exploit code is made available to the public

-   attackers are found to be exploiting the vulnerability and this
    information is made public

::: {#tab:delta_vfdp}
   State    $\mathbf{V}$   $\mathbf{F}$   $\mathbf{D}$   $\mathbf{P}$
  -------- -------------- -------------- -------------- --------------
   $vfdp$      $Vfdp$           \-             \-           $vfdP$
   $Vfdp$        \-           $VFdp$           \-           $VfdP$
   $VFdp$        \-             \-           $VFDp$         $VFdP$
   $VFDp$        \-             \-             \-           $VFDP$
   $vfdP$      $VfdP$           \-             \-             \-
   $VfdP$        \-           $VFdP$           \-             \-
   $VFdP$        \-             \-           $VFDP$           \-
   $VFDP$        \-             \-             \-             \-

  : Transition function $\delta_{VFDP}$ for the vendor fix path
  incorporating public awareness
:::

<figure id="fig:vfdp_map">

<figcaption>Submap of vendor fix path state transitions with public
awareness (<span class="math inline"><strong>V</strong></span>, <span
class="math inline"><strong>F</strong></span>, <span
class="math inline"><strong>D</strong></span>, <span
class="math inline"><strong>P</strong></span>)</figcaption>
</figure>

Our model assumes that vendors immediately become aware of what the
public is aware of. Therefore, all states in ${vP}$ are unstable, and
must lead to the corresponding state in ${VP}$ in the next step.

CVD attempts to
move vulnerabilities through states belonging to $p$ until the process
reaches a state in $VFdp$ at least. Vendors that can control deployment
will likely prefer the transition from
${VFDp} \xrightarrow{\mathbf{P}} {VFDP}$. On the other hand,
vulnerabilities requiring system owner action to deploy fixes will be
forced to transition through
$VFdp \xrightarrow{\mathbf{P}} VFdP \xrightarrow{\mathbf{D}} VFDP$
instead since public awareness is required in order to prompt such
action. This implies that states in $VFDp$ are unreachable to vendors
whose distribution model requires system owner action to deploy fixes.

The DFA specification for this submodel is given in
[\[eq:vfdp_dfa\]](#eq:vfdp_dfa){reference-type="eqref"
reference="eq:vfdp_dfa"}. Table
[2.4](#tab:delta_vfdp){reference-type="ref" reference="tab:delta_vfdp"}
shows the transition function $\delta_{VFDP}$, while Figure
[2.2](#fig:vfdp_map){reference-type="ref" reference="fig:vfdp_map"}
depicts the transitions among these states. $$\label{eq:vfdp_dfa}
\begin{split}
    \mathcal{Q}_{VFDP} =&\,\{vfdp,vfdP,Vfdp,VfdP,\\
                         &\,~VFdp,VFdP,VFDp,VFDP\}\\
    \Sigma_{VFDP} =&\,\{\mathbf{V},\mathbf{F},\mathbf{D},\mathbf{P}\}\\
    \delta_{VFDP} =&\,\textrm{see~Table~\ref{tab:delta_vfdp}}\\
    q^0_{VFDP} =&\,vfdp\\
    \mathcal{F}_{VFDP} =&\,\{VFDP\}
\end{split}$$

##### Public awareness, exploits, and attacks

Before fully integrating all thirty two states, we pause here to develop
a three dimensional sub-model that highlights the interaction of public
awareness, exploit publication, and attacks. Unlike the causal
relationship representing the vendor process in Figure
[2.1](#fig:vfd_map){reference-type="ref" reference="fig:vfd_map"}, these
three transitions can occur independently. We therefore treat them as
their own dimensions, as shown in Figure
[2.3](#fig:pxa_map){reference-type="ref" reference="fig:pxa_map"}.

::: {#tab:delta_pxa}
   State   $\mathbf{P}$   $\mathbf{X}$   $\mathbf{A}$
  ------- -------------- -------------- --------------
   $pxa$      $Pxa$          $pXa$          $pxA$
   $pxA$      $PxA$          $pXA$            \-
   $pXa$      $PXa$            \-             \-
   $pXA$      $PXA$            \-             \-
   $Pxa$        \-           $PXa$          $PxA$
   $PxA$        \-           $PXA$            \-
   $PXa$        \-             \-           $PXA$
   $PXA$        \-             \-             \-

  : Transition function $\delta_{PXA}$ for the non-fix path transitions
:::

<figure id="fig:pxa_map">

<figcaption>Submap of non-fix path state transitions (<span
class="math inline"><strong>P</strong></span>, <span
class="math inline"><strong>X</strong></span>, <span
class="math inline"><strong>A</strong></span>)</figcaption>
</figure>

Because we defined $\mathbf{X}$ to correspond to the public availability
of an exploit, as a simplification we impose the constraint that exploit
publication leads directly to public awareness when the public was
previously unaware of the vulnerability. For practical purposes, this
constraint means that all states in ${pX}$ are unstable and must lead to
the corresponding state in ${PX}$ in the subsequent step. As a result,
transitions from ${pXa}$ to ${pXA}$ are disallowed, as reflected in
Figure [2.3](#fig:pxa_map){reference-type="ref"
reference="fig:pxa_map"}. The transition function $\delta_{PXA}$ is
given in Table [2.5](#tab:delta_pxa){reference-type="ref"
reference="tab:delta_pxa"}. Further discussion of this transition can be
found in §[6.5.1](#sec:zerodays){reference-type="ref"
reference="sec:zerodays"}.

$$\label{eq:pxa_dfa}
\begin{split}
    \mathcal{Q}_{PXA} =&\,\{pxa,pxA,pXa,pXA,\\
                         &\,~Pxa,PxA,PXa,PXA\}\\
    \Sigma_{PXA} =&\,\{\mathbf{P},\mathbf{X},\mathbf{A}\}\\
    \delta_{PXA} =&\,\textrm{see~Table~\ref{tab:delta_pxa}}\\
    q^0_{PXA} =&\,pxa\\
    \mathcal{F}_{PXA} =&\,\{PXA\}
\end{split}$$

In this model, attacks observed need not immediately cause public
awareness, although that can happen. Our reasoning is that the
connection between attacks and exploited vulnerabilities is often made
later during incident analysis. While the attack itself may have been
observed much earlier, the knowledge of which vulnerability it targeted
may be delayed until after other events have occurred. In other words,
although $pA$ does not require an immediate transition to $PA$ the way
$pX \xrightarrow{\mathbf{P}} PX$ does, it does seem plausible that the
likelihood of $\mathbf{P}$ occurring increases when attacks are
occurring. Logically, this is a result of there being more ways for the
public to discover the vulnerability when attacks are happening than
when they are not. For states in $pa$, the public depends on the normal
vulnerability discovery and reporting process. States in $pA$ include
that possibility and add the potential for discovery as a result of
security incident analysis.

##### Five Dimensions of CVD {#para:5d}

By composing these sub-parts, we arrive at our complete state transition
model, which we construct by combining the vendor fix path
$vfd \rightarrow Vfd \rightarrow VFd \rightarrow VFD$ defined by
[\[eq:vfd_dfa\]](#eq:vfd_dfa){reference-type="eqref"
reference="eq:vfd_dfa"} and its extension in
[\[eq:vfdp_dfa\]](#eq:vfdp_dfa){reference-type="eqref"
reference="eq:vfdp_dfa"} with the $PXA$ cube defined by
[\[eq:pxa_dfa\]](#eq:pxa_dfa){reference-type="eqref"
reference="eq:pxa_dfa"}. The complete map is shown in Figure
[2.4](#fig:vfdpxa_map){reference-type="ref" reference="fig:vfdpxa_map"}.
We also can now define the transition function $\delta$ for the entire
model, as shown in Table [2.6](#tab:delta_vfdpxa){reference-type="ref"
reference="tab:delta_vfdpxa"}. A summary of the complete
DFA specification
is given in [\[eq:vfdpxa_dfa\]](#eq:vfdpxa_dfa){reference-type="eqref"
reference="eq:vfdpxa_dfa"}.

$$\label{eq:vfdpxa_dfa}
\begin{split}
    \mathcal{Q} =&\,\textrm{see~\eqref{eq:all_states}}\\
    \Sigma =&\,\textrm{see~\eqref{eq:events}}\\
    \delta =&\,\textrm{see~Table~\ref{tab:delta_vfdpxa}}\\
    q_0 =&\,\textrm{see~\eqref{eq:q_0}}\\
    \mathcal{F} =&\,\textrm{see~\eqref{eq:F}}
\end{split}$$

::: {#tab:delta_vfdpxa}
  ---------- -------------- -------------- -------------- -------------- -------------- --------------
    State       $\Sigma$                                                                
     $q$      $\mathbf{V}$   $\mathbf{F}$   $\mathbf{D}$   $\mathbf{P}$   $\mathbf{X}$   $\mathbf{A}$
   $vfdpxa$     $Vfdpxa$          \-             \-          $vfdPxa$       $vfdpXa$       $vfdpxA$
   $vfdpxA$     $VfdpxA$          \-             \-          $vfdPxA$       $vfdpXA$          \-
   $vfdpXa$        \-             \-             \-          $vfdPXa$          \-             \-
   $vfdpXA$        \-             \-             \-          $vfdPXA$          \-             \-
   $vfdPxa$     $VfdPxa$          \-             \-             \-             \-             \-
   $vfdPxA$     $VfdPxA$          \-             \-             \-             \-             \-
   $vfdPXa$     $VfdPXa$          \-             \-             \-             \-             \-
   $vfdPXA$     $VfdPXA$          \-             \-             \-             \-             \-
   $Vfdpxa$        \-          $VFdpxa$          \-          $VfdPxa$       $VfdpXa$       $VfdpxA$
   $VfdpxA$        \-          $VFdpxA$          \-          $VfdPxA$       $VfdpXA$          \-
   $VfdpXa$        \-             \-             \-          $VfdPXa$          \-             \-
   $VfdpXA$        \-             \-             \-          $VfdPXA$          \-             \-
   $VfdPxa$        \-          $VFdPxa$          \-             \-          $VfdPXa$       $VfdPxA$
   $VfdPxA$        \-          $VFdPxA$          \-             \-          $VfdPXA$          \-
   $VfdPXa$        \-          $VFdPXa$          \-             \-             \-          $VfdPXA$
   $VfdPXA$        \-          $VFdPXA$          \-             \-             \-             \-
   $VFdpxa$        \-             \-          $VFDpxa$       $VFdPxa$       $VFdpXa$       $VFdpxA$
   $VFdpxA$        \-             \-          $VFDpxA$       $VFdPxA$       $VFdpXA$          \-
   $VFdpXa$        \-             \-             \-          $VFdPXa$          \-             \-
   $VFdpXA$        \-             \-             \-          $VFdPXA$          \-             \-
   $VFdPxa$        \-             \-          $VFDPxa$          \-          $VFdPXa$       $VFdPxA$
   $VFdPxA$        \-             \-          $VFDPxA$          \-          $VFdPXA$          \-
   $VFdPXa$        \-             \-          $VFDPXa$          \-             \-          $VFdPXA$
   $VFdPXA$        \-             \-          $VFDPXA$          \-             \-             \-
   $VFDpxa$        \-             \-             \-          $VFDPxa$       $VFDpXa$       $VFDpxA$
   $VFDpxA$        \-             \-             \-          $VFDPxA$       $VFDpXA$          \-
   $VFDpXa$        \-             \-             \-          $VFDPXa$          \-             \-
   $VFDpXA$        \-             \-             \-          $VFDPXA$          \-             \-
   $VFDPxa$        \-             \-             \-             \-          $VFDPXa$       $VFDPxA$
   $VFDPxA$        \-             \-             \-             \-          $VFDPXA$          \-
   $VFDPXa$        \-             \-             \-             \-             \-          $VFDPXA$
   $VFDPXA$        \-             \-             \-             \-             \-             \-
  ---------- -------------- -------------- -------------- -------------- -------------- --------------

  : Transition function $\delta$ for the full model
:::

<figure id="fig:vfdpxa_map">

<figcaption>Complete map of the 32 possible states in our model of
vulnerability disclosure and their allowed transitions (<span
class="math inline"><strong>V</strong></span>, <span
class="math inline"><strong>F</strong></span>, <span
class="math inline"><strong>D</strong></span>, <span
class="math inline"><strong>P</strong></span>, <span
class="math inline"><strong>X</strong></span>, <span
class="math inline"><strong>A</strong></span>)</figcaption>
</figure>

In this combined model, each point along the vendor fix flow in Figure
[2.1](#fig:vfd_map){reference-type="ref" reference="fig:vfd_map"}
corresponds to an instance of the public/exploit/attack cube from Figure
[2.3](#fig:pxa_map){reference-type="ref" reference="fig:pxa_map"}.
Figure [2.4](#fig:vfdpxa_map){reference-type="ref"
reference="fig:vfdpxa_map"} shows each of these as distinct cubes
embedded in the larger model.

The *ignorant vendor* cube ($vfd$)

:   Found at the lower right of Figure
    [2.4](#fig:vfdpxa_map){reference-type="ref"
    reference="fig:vfdpxa_map"}, the $vfd$ cube is the least stable of
    the four because many of its internal transitions are disallowed,
    owing to the instability of both $pX$ and $vP$. The effect is a
    higher likelihood of exiting this cube than the others. The
    practical interpretation is that vendors are likely to become aware
    of vulnerabilities that exist in their products barring significant
    effort on the part of adversaries to prevent exiting the $vfd$
    states.

The *vendor aware* cube ($Vfd$)

:   In this cube, the vendor is aware of the vulnerability, but the fix
    is not yet ready. Vulnerabilities remain in $Vfd$ until the vendor
    produces a fix.

The *fix available* cube ($VFd$)

:   States in this cube share the fact that a fix is available but not
    yet deployed. Many publicly-disclosed vulnerabilities spend a
    sizable amount of time in this cube as they await system owner or
    deployer action to deploy the fix.

The *fix deployed* cube ($VFD$)

:   This cube is a sink: once it is reached, there are no exits. Attacks
    attempted in this cube are expected to fail. The broader the scope
    of one's concern in terms of number of systems, the less certain one
    can be of having reached this cube. It is rather easy to tell when a
    single installed instance of vulnerable software has been patched.
    It is less easy to tell when the last of thousands or even millions
    of vulnerable software instances across an enterprise has been
    fixed.

::: {#tab:state_encoding}
   Bit Position                     0                              1
  -------------- ---------------------------------------- --------------------
        0         $\mathcal{Q}_{v} \cup \mathcal{Q}_{D}$   $\mathcal{Q}_{Vd}$
        1                    $\mathcal{Q}_f$                $\mathcal{Q}_F$
        2                    $\mathcal{Q}_p$                $\mathcal{Q}_P$
        3                    $\mathcal{Q}_x$                $\mathcal{Q}_X$
        4                    $\mathcal{Q}_a$                $\mathcal{Q}_A$

  : Semantic encoding of states in $\mathcal{S}$
:::

The states and transitions of the model can be represented as a partial
Hamming cube in in 5 dimensions. In this representation, each state maps
onto a binary value between 00000 and 11111, corresponding to the 32
vertices of the 5-dimensional Hamming Cube. The semantics of each bit
position from left to right are given in Table
[2.7](#tab:state_encoding){reference-type="ref"
reference="tab:state_encoding"}. Correspondingly, each transition
represents a single bit flip in the state encoding. Some edges
(transitions) are disallowed by the causal requirements described in
this section and formalized in the next section (see
[\[eq:history_vfd_rule\]](#eq:history_vfd_rule){reference-type="eqref"
reference="eq:history_vfd_rule"},
[\[eq:history_vp_rule\]](#eq:history_vp_rule){reference-type="eqref"
reference="eq:history_vp_rule"}, and
[\[eq:history_px_rule\]](#eq:history_px_rule){reference-type="eqref"
reference="eq:history_px_rule"}). This observation serves as the basis
of the visualization given in
Figure [2.4](#fig:vfdpxa_map){reference-type="ref"
reference="fig:vfdpxa_map"}.

