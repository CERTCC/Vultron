
![image](assets/Software_Engineering_Institute_Unitmark_Red_and_Black.jpg){width="2.5in"}

A State-Based Model for Multi-Party Coordinated Vulnerability Disclosure
(MPCVD)

Allen Householder Allen Householder\
Jonathan Spring Jonathan Spring\
\
\
\
\
\

**July 2021**

\
CMU/SEI-2021-SR-021\
DOI: 10.1184/R1/16416771 DOI: 10.1184/R1/16416771\

**CERT Division**\

\[DISTRIBUTION STATEMENT A\] Approved for public release and unlimited
distribution.\

<http://www.sei.cmu.edu>

Copyright  2021 Carnegie Mellon University.

This material is based upon work funded and supported by the Department
of Homeland Security under Contract No. FA8702-15-D-0002 with Carnegie
Mellon University for the operation of the Software Engineering
Institute, a federally funded research and development center sponsored
by the United States Department of Defense.

The view, opinions, and/or findings contained in this material are those
of the author(s) and should not be construed as an official Government
position, policy, or decision, unless designated by other documentation.

References herein to any specific commercial product, process, or
service by trade name, trade mark, manufacturer, or otherwise, does not
necessarily constitute or imply its endorsement, recommendation, or
favoring by Carnegie Mellon University or its Software Engineering
Institute.

This report was prepared for the SEI Administrative Agent AFLCMC/AZS 5
Eglin Street Hanscom AFB, MA 01731-2100

NO WARRANTY. THIS CARNEGIE MELLON UNIVERSITY AND SOFTWARE ENGINEERING
INSTITUTE MATERIAL IS FURNISHED ON AN \"AS-IS\" BASIS. CARNEGIE MELLON
UNIVERSITY MAKES NO WARRANTIES OF ANY KIND, EITHER EXPRESSED OR IMPLIED,
AS TO ANY MATTER INCLUDING, BUT NOT LIMITED TO, WARRANTY OF FITNESS FOR
PURPOSE OR MERCHANTABILITY, EXCLUSIVITY, OR RESULTS OBTAINED FROM USE OF
THE MATERIAL. CARNEGIE MELLON UNIVERSITY DOES NOT MAKE ANY WARRANTY OF
ANY KIND WITH RESPECT TO FREEDOM FROM PATENT, TRADEMARK, OR COPYRIGHT
INFRINGEMENT.

\[DISTRIBUTION STATEMENT A\] This material has been approved for public
release and unlimited distribution. Please see Copyright notice for
non-US Government use and distribution.

Internal use:

-   Permission to reproduce this material and to prepare derivative
    works from this material for internal use is granted, provided the
    copyright and "No Warranty" statements are included with all
    reproductions and derivative works.

External use:

-   This material may be reproduced in its entirety, without
    modification, and freely distributed in written or electronic form
    without requesting formal permission. Permission is required for any
    other external and/or commercial use. Requests for permission should
    be directed to the Software Engineering Institute at
    permission@sei.cmu.edu.

-   These restrictions do not apply to U.S. government entities.

    Carnegie Mellon, CERT and CERT Coordination Center are registered in
    the U.S. Patent and Trademark Office by Carnegie Mellon University.

DM21-0607

# Acknowledgments {#acknowledgments .unnumbered}

We offer our sincere gratitude to the United States Senators, Members of
Congress, and their staffs, whose insightful questions surrounding the
coordinated disclosure of the Meltdown and Spectre vulnerabilities
prompted us to recognize the need for a better way to reason about and
describe what "good" vulnerability disclosure outcomes look like.

We also thank the anonymous reviewers at the ACM Journal *Digital
Threats: Research and Practice* for their helpful feedback on an earlier
version of this report.

CERT/CC staff were instrumental in reviewing and providing feedback on
the model described in this report as it developed. We are grateful for
the opportunity to have them as colleagues.

# Abstract {#abstract .unnumbered}

[CVD]{acronym-label="CVD" acronym-form="singular+short"} stands as a
consensus response to the persistent fact of vulnerable software, yet
few performance indicators have been proposed to measure its efficacy at
the broadest scales. In this report, we seek to fill that gap. We begin
by deriving a model of all possible [CVD]{acronym-label="CVD"
acronym-form="singular+short"} histories from first principles,
organizing those histories into a partial ordering based on a set of
desired criteria. We then compute a baseline expectation for the
frequency of each desired criteria and propose a new set of performance
indicators to measure the efficacy of [CVD]{acronym-label="CVD"
acronym-form="singular+short"} practices based on the differentiation of
skill and luck in observation data. As a proof of concept, we apply
these indicators to a variety of longitudinal observations of
[CVD]{acronym-label="CVD" acronym-form="singular+short"} practice and
find evidence of significant skill to be prevalent. We conclude with
reflections on how this model and its accompanying performance
indicators could be used by various stakeholders (vendors, system
owners, coordinators, and governments) to interpret the quality of their
[CVD]{acronym-label="CVD" acronym-form="singular+short"} practices.

# Introduction {#sec:introduction}

Software vulnerabilities remain pervasive. To date, there is little
evidence that we are anywhere close to equilibrium between the
introduction and elimination of vulnerabilities in deployed systems. The
practice of [CVD]{acronym-label="CVD" acronym-form="singular+short"}
emerged as part of a growing consensus to develop normative behaviors in
response to the persistent fact of vulnerable software. Yet while the
basic principles of [CVD]{acronym-label="CVD"
acronym-form="singular+short"} have been established
[@christey2002responsible; @ISO29147; @householder2017cert; @ncsc2018cvd],
there has been limited work to measure the efficacy of
[CVD]{acronym-label="CVD" acronym-form="singular+short"} programs,
especially at the scale of industry benchmarks. ISO 29147 [@ISO29147]
sets out the goals of vulnerability disclosure:

> a\) ensuring that identified vulnerabilities are addressed;\
> b) minimizing the risk from vulnerabilities;\
> c) providing users with sufficient information to evaluate risks from
> vulnerabilities to their systems;\
> d) setting expectations to promote positive communication and
> coordination among involved parties.

Meanwhile, the use of third party libraries and shared code components
across vendors and their products creates a need to coordinate across
those parties whenever a vulnerability is found in a shared component.
While it can be difficult for stakeholders to ascertain the prevalence
of components across products---and efforts such as the
[NTIA]{acronym-label="NTIA" acronym-form="singular+short"}'s
[SBOM]{acronym-label="SBOM" acronym-form="singular+short"} [@ntia_sbom]
are working to address the informational aspects of that problem---our
concern here is the coordination of multiple parties in responding to
the vulnerability.

[MPCVD]{acronym-label="MPCVD" acronym-form="singular+short"} is a more
complex form of [CVD]{acronym-label="CVD"
acronym-form="singular+short"}, involving the necessity to coordinate
numerous stakeholders in the process of recognizing and fixing
vulnerable products. Initial guidance from the
[FIRST]{acronym-label="FIRST" acronym-form="singular+full"} acknowledges
the additional complexity that can arise in
[MPCVD]{acronym-label="MPCVD" acronym-form="singular+short"}
cases [@first2020mpcvd]. The need for [MPCVD]{acronym-label="MPCVD"
acronym-form="singular+short"} arises from the complexities of the
software supply chain. Its importance was illustrated by the Senate
hearings about the Meltdown and Spectre
vulnerabilities [@wired2018senate]. Nevertheless, the goals of
[CVD]{acronym-label="CVD" acronym-form="singular+short"} apply to
[MPCVD]{acronym-label="MPCVD" acronym-form="singular+short"}, as the
latter is a generalization of the former.

The difficulty of [MPCVD]{acronym-label="MPCVD"
acronym-form="singular+short"} derives from the diversity of its
stakeholders: different software vendors have different development
budgets, schedules, tempos, and analysis capabilities to help them
isolate, understand, and fix vulnerabilities. Additionally, they face
diverse customer support expectations and obligations, plus an
increasing variety of regulatory regimes governing some stakeholders but
not others. For these reasons and many others, practitioners of
[MPCVD]{acronym-label="MPCVD" acronym-form="singular+short"} highlight
*fairness* as a core difficulty in coordinating disclosures across
vendors [@householder2017cert].

With the goal of minimizing the societal harm that results from the
existence of a vulnerability in multiple products spread across multiple
vendors, our motivating question is, "What does *fair* mean in
[MPCVD]{acronym-label="MPCVD" acronym-form="singular+short"}?"
Optimizing [MPCVD]{acronym-label="MPCVD" acronym-form="singular+short"}
directly is not currently possible, as we lack a utility function to map
from the events that occur in a given case to the impact that case has
on the world. While this document does not fully address that problem,
it sets out a number of steps toward a solution. We seek a way to sort
[MPCVD]{acronym-label="MPCVD" acronym-form="singular+short"} cases into
better outcomes or worse outcomes. Ideally, the sorting criteria should
based on unambiguous principles that are agreed upon and intelligible by
all interested parties. Further, we seek a way to measure relevant
features across [MPCVD]{acronym-label="MPCVD"
acronym-form="singular+short"} cases. Feature observability is a key
factor: our measurement needs to be simple and repeatable without overly
relying on proprietary or easily hidden information.

While a definition of *fairness* in [MPCVD]{acronym-label="MPCVD"
acronym-form="singular+short"} is a responsibility for the broader
community, we focus on evaluating the skill of the coordinator. We
expect this contributes to fairness based on the EthicsfIRST principles
of ethics for incident response teams promoted by
[FIRST]{acronym-label="FIRST" acronym-form="singular+short"}
[@first2019ethics].[^1] To that end, our research questions are:

RQ1

:   : Construct a model of [CVD]{acronym-label="CVD"
    acronym-form="singular+short"} states amenable to analysis and also
    future generalization to [MPCVD]{acronym-label="MPCVD"
    acronym-form="singular+short"}.

RQ2

:   : What is a reasonable baseline expectation for ordering of events
    in the model of [CVD]{acronym-label="CVD"
    acronym-form="singular+short"}?

RQ3

:   : Given this baseline and model, does [CVD]{acronym-label="CVD"
    acronym-form="singular+short"} as observed "in the wild" demonstrate
    skillful behavior?

This paper primarily focuses on the simpler case of
[CVD]{acronym-label="CVD" acronym-form="singular+short"}, with some
initial thoughts towards extending it to [MPCVD]{acronym-label="MPCVD"
acronym-form="singular+short"}. This focus provides an opportunity for
incremental analysis of the success of the model; more detailed
[MPCVD]{acronym-label="MPCVD" acronym-form="singular+short"} modeling
can follow in future work.

## Approach

The [CERT/CC]{acronym-label="CERT/CC" acronym-form="singular+short"} has
a goal to improve the [MPCVD]{acronym-label="MPCVD"
acronym-form="singular+short"} process. Improvement involves automation.
The creation of VINCE[^2] is a significant step toward this goal, as it
has helped us to recognize gaps in our own processes surrounding the
[MPCVD]{acronym-label="MPCVD" acronym-form="singular+short"} services we
provide. As part of the [SEI]{acronym-label="SEI"
acronym-form="singular+short"} at [CMU]{acronym-label="CMU"
acronym-form="singular+short"}, we also recognize that automation is
made better when we can formalize process descriptions. In this report,
we construct a toy model of the [CVD]{acronym-label="CVD"
acronym-form="singular+short"} process with the interest of a better
understanding of how it might be formalized.

Our intent with this report is not to provide a complete solution to
automate either [CVD]{acronym-label="CVD" acronym-form="singular+short"}
or [MPCVD]{acronym-label="MPCVD" acronym-form="singular+short"}. Rather,
this report is an attempt to systematize the basics in a way that can be
extended by future work toward the specification of protocols that
facilitate the automation of coordination tasks within
[MPCVD]{acronym-label="MPCVD" acronym-form="singular+short"}.

The model presented here provides a foundation on which we might build
an [MPCVD]{acronym-label="MPCVD" acronym-form="singular+short"}
protocol. While we stop well short of a full protocol spec, we feel that
this report contributes to improved understanding of the problems that
such a protocol would need to address. And although an actual protocol
would need to support a far more complicated process (i.e., the
coordination and resolution of actual [MPCVD]{acronym-label="MPCVD"
acronym-form="singular+short"} cases), our contention is that we should
be able to derive and learn quite a few of the basics from this toy
model. A protocol that works on the toy model might not work in the real
world. But any proposed real-world protocol should probably work on the
toy model. The model is intended to be a sort of minimum acceptance test
for any future protocol---if a proposed [MPCVD]{acronym-label="MPCVD"
acronym-form="singular+short"} process doesn't improve outcomes even in
the toy model, one might wonder what it *is* doing.

## Organization of This Document

We begin by deriving a model of all possible [CVD]{acronym-label="CVD"
acronym-form="singular+short"} case states and histories from first
principles in §[2](#sec:model){reference-type="ref"
reference="sec:model"} and §[3](#sec:poss_hist){reference-type="ref"
reference="sec:poss_hist"}, organizing those histories into a partial
ordering based on a set of desired criteria in
§[4](#sec:reasoning){reference-type="ref" reference="sec:reasoning"}. We
then compute a baseline expectation for the frequency of each desired
criteria and propose a new set of performance indicators to measure the
efficacy of [CVD]{acronym-label="CVD" acronym-form="singular+short"}
practices based on the differentiation of skill and luck in observation
data in §[5](#sec:skill_luck){reference-type="ref"
reference="sec:skill_luck"}. As a proof of concept, we apply these
indicators to a variety of longitudinal observations of
[CVD]{acronym-label="CVD" acronym-form="singular+short"} practice and
find evidence of significant skill to be prevalent. In
§[6](#sec:discussion){reference-type="ref" reference="sec:discussion"},
we explore some of the implications and uses of such a model in any
[CVD]{acronym-label="CVD" acronym-form="singular+short"} case before
extending it to [MPCVD]{acronym-label="MPCVD"
acronym-form="singular+short"}. The remainder of that section offers
reflections on how this model and its accompanying performance
indicators could be used by various stakeholders (vendors, system
owners, coordinators, and governments) to interpret the quality of their
[CVD]{acronym-label="CVD" acronym-form="singular+short"} and
[MPCVD]{acronym-label="MPCVD" acronym-form="singular+short"} practices
We continue with a review of related work in
§[7](#sec:related_work){reference-type="ref"
reference="sec:related_work"}, future work in
§[8](#sec:limitationsAnd){reference-type="ref"
reference="sec:limitationsAnd"}, and give our conclusions in
§[9](#sec:conclusion){reference-type="ref" reference="sec:conclusion"}.

An appendix summarizing each state in the model in conjunction with the
discussion in §[6](#sec:discussion){reference-type="ref"
reference="sec:discussion"} is also provided.

# A State-based model for CVD {#sec:model}

Our goal is to create a toy model of the [MPCVD]{acronym-label="MPCVD"
acronym-form="singular+short"} process that can shed light on the more
complicated real thing. We begin by building up a state map of what
[FIRST]{acronym-label="FIRST" acronym-form="singular+short"} refers to
as bilateral [CVD]{acronym-label="CVD"
acronym-form="singular+short"} [@first2020mpcvd], which we will later
expand into the [MPCVD]{acronym-label="MPCVD"
acronym-form="singular+short"} space. We start by defining a set of
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
stakeholders of a [CVD]{acronym-label="CVD"
acronym-form="singular+short"} case. Stakeholders include software
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
    Posting [PoC]{acronym-label="PoC" acronym-form="singular+short"}
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

Before we discuss [CVD]{acronym-label="CVD"
acronym-form="singular+short"} states
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

Transitions during [CVD]{acronym-label="CVD"
acronym-form="singular+short"} resemble in that the transitions
available to the current state are dependent on the state itself.
Although [DFAs]{acronym-label="DFA" acronym-form="plural+short"} are
often used to determine whether the final or end state is acceptable,
for analyzing [CVD]{acronym-label="CVD" acronym-form="singular+short"}
we are more interested in the order of the transitions. The usual
[DFA]{acronym-label="DFA" acronym-form="singular+short"} notation will
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
[CVD]{acronym-label="CVD" acronym-form="singular+short"} case has been
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
function for our [DFA]{acronym-label="DFA"
acronym-form="singular+short"}.

### Input Symbols

The input symbols to our [DFA]{acronym-label="DFA"
acronym-form="singular+short"} correspond to observations of the events
outlined in Table [2.1](#tab:lifecycle_events){reference-type="ref"
reference="tab:lifecycle_events"}. For our model, an input symbol
$\sigma$ is "read" when a participant observes a change in status (the
vendor is notified, an exploit has been published, etc.). For the sake
of simplicity, we begin with the assumption that observations are
globally known---that is, a status change observed by any
[CVD]{acronym-label="CVD" acronym-form="singular+short"} participant is
known to all. In the real world, the [CVD]{acronym-label="CVD"
acronym-form="singular+short"} process itself is well poised to ensure
eventual consistency with this assumption through the communication of
perceived case state across coordinating parties. We define the set of
input symbols for our [DFA]{acronym-label="DFA"
acronym-form="singular+short"} as:

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

[CVD]{acronym-label="CVD" acronym-form="singular+short"} attempts to
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

##### Five Dimensions of [CVD]{acronym-label="CVD" acronym-form="singular+short"} {#para:5d}

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
[DFA]{acronym-label="DFA" acronym-form="singular+short"} specification
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

# Sequences of Events and Possible Histories in CVD {#sec:poss_hist}

In §[2](#sec:model){reference-type="ref" reference="sec:model"}, we
began by identifying a set of events of interest in
[CVD]{acronym-label="CVD" acronym-form="singular+short"} cases. Then we
constructed a state model describing how the occurrence of these events
can interact with each other. In this section, we look at paths through
the resulting state model.

A sequence $s$ is an ordered set of some number of events
$\sigma_i \in \Sigma$ for $1 \leq i \leq n$ and the length of $s$ is
$|s| \stackrel{\mathsf{def}}{=}n$. In other words, a sequence $s$ is an
input string to the [DFA]{acronym-label="DFA"
acronym-form="singular+short"} defined in
§[2](#sec:model){reference-type="ref" reference="sec:model"}.

$$\label{eq:sequence}
    s \stackrel{\mathsf{def}}{=}\left( \sigma_1, \sigma_2, \dots \sigma_n \right)$$

A vulnerability disclosure history $h$ is a sequence $s$ containing one
and only one of each of the symbols in $\Sigma$; by definition
$|h| = |\Sigma| = 6$. Note this is a slight abuse of notation;
$|\textrm{ }|$ represents both sequence length and the cardinality of a
set.

$$\label{eq:history_definition}
\begin{split}
    h \stackrel{\mathsf{def}}{=}s : & \forall \sigma_i, \sigma_j \in s \textrm{ it is the case that } \sigma_i \neq \sigma_j \textrm{ and } \\
    & \forall \sigma_k \in \Sigma \textrm{ it is the case that } \exists \sigma_i \in s \textrm{ such that } \sigma_k = \sigma_i 
\end{split}$$

where two members of the set $\Sigma$ are equal if they are represented
by the same symbol and not equal otherwise. The set of all potential
histories, $\mathcal{H}_p$, is a set of all the sequences $h$ that
satisfy this definition.

## The Possible Histories of CVD

Given that a history $h$ contains all six events $\Sigma$ in some order,
there could be at most 720 ($_{6} \mathrm{P}_{6} = 6! = 720$) potential
histories. However, because of the causal requirements outlined in
[2.4.2](#sec:transition_function){reference-type="ref"
reference="sec:transition_function"}, we know that Vendor Awareness
($\mathbf{V}$) must precede Fix Ready ($\mathbf{F}$) and that Fix Ready
must precede Fix Deployed ($\mathbf{D}$).

The [DFA]{acronym-label="DFA" acronym-form="singular+short"} developed
in §[2](#sec:model){reference-type="ref" reference="sec:model"} provides
the mechanism to validate histories: a history $h$ is valid if the
[DFA]{acronym-label="DFA" acronym-form="singular+short"} accepts it as a
valid input string. Once this constraint is applied, only 70 possible
histories $h \in \mathcal{H}p$ remain viable. We denote the set of all
such valid histories as $\mathcal{H}$ and have $|\mathcal{H}| = 70$. The
set of possible histories $\mathcal{H}$ corresponds to the 70 allowable
paths through $\mathcal{Q}$ as can be derived from Table
[2.6](#tab:delta_vfdpxa){reference-type="ref"
reference="tab:delta_vfdpxa"} and Fig.
[2.4](#fig:vfdpxa_map){reference-type="ref" reference="fig:vfdpxa_map"}.

The set of possible histories $\mathcal{H}$ is listed exhaustively in
Table [3.1](#tab:possible_histories){reference-type="ref"
reference="tab:possible_histories"}. Commas and parentheses indicating
ordered sets were omitted from column $h$ for readability. The skill
ranking function on the histories will be defined in
§[4.4](#sec:h_poset_skill){reference-type="ref"
reference="sec:h_poset_skill"}. The desirability of the history
($\mathbb{D}^h$) will be defined in
§[3.2](#sec:desirability){reference-type="ref"
reference="sec:desirability"}. The expected frequency of each history
$f_h$ is explained in
§[4.1](#sec:history_frequency_analysis){reference-type="ref"
reference="sec:history_frequency_analysis"}.

::: {#tab:possible_histories}
<table>
<caption>Possible Histories <span
class="math inline"><em>h</em> ∈ ℋ</span> of CVD</caption>
<thead>
<tr class="header">
<th style="text-align: center;">#</th>
<th style="text-align: center;"><span
class="math inline"><em>h</em></span></th>
<th style="text-align: center;">rank</th>
<th style="text-align: center;"><span
class="math inline">|𝔻<sup><em>h</em></sup>|</span></th>
<th style="text-align: center;"><span
class="math inline"><em>f</em><sub><em>h</em></sub></span></th>
<th style="text-align: center;"><div class="sideways">
<p><span
class="math inline"><strong>D</strong> ≺ <strong>A</strong></span></p>
</div></th>
<th style="text-align: center;"><div class="sideways">
<p><span
class="math inline"><strong>D</strong> ≺ <strong>P</strong></span></p>
</div></th>
<th style="text-align: center;"><div class="sideways">
<p><span
class="math inline"><strong>D</strong> ≺ <strong>X</strong></span></p>
</div></th>
<th style="text-align: center;"><div class="sideways">
<p><span
class="math inline"><strong>F</strong> ≺ <strong>A</strong></span></p>
</div></th>
<th style="text-align: center;"><div class="sideways">
<p><span
class="math inline"><strong>F</strong> ≺ <strong>P</strong></span></p>
</div></th>
<th style="text-align: center;"><div class="sideways">
<p><span
class="math inline"><strong>F</strong> ≺ <strong>X</strong></span></p>
</div></th>
<th style="text-align: center;"><div class="sideways">
<p><span
class="math inline"><strong>P</strong> ≺ <strong>A</strong></span></p>
</div></th>
<th style="text-align: center;"><div class="sideways">
<p><span
class="math inline"><strong>P</strong> ≺ <strong>X</strong></span></p>
</div></th>
<th style="text-align: center;"><div class="sideways">
<p><span
class="math inline"><strong>V</strong> ≺ <strong>A</strong></span></p>
</div></th>
<th style="text-align: center;"><div class="sideways">
<p><span
class="math inline"><strong>V</strong> ≺ <strong>P</strong></span></p>
</div></th>
<th style="text-align: center;"><div class="sideways">
<p><span
class="math inline"><strong>V</strong> ≺ <strong>X</strong></span></p>
</div></th>
<th style="text-align: center;"><div class="sideways">
<p><span
class="math inline"><strong>X</strong> ≺ <strong>A</strong></span></p>
</div></th>
<th style="text-align: center;"></th>
</tr>
</thead>
<tbody>
<tr class="odd">
<td colspan="15" style="text-align: right;"><span>Continued on next
page</span></td>
<td style="text-align: center;"></td>
<td style="text-align: center;"></td>
<td style="text-align: center;"></td>
</tr>
<tr class="even">
<td style="text-align: center;"></td>
<td style="text-align: center;"><span
class="math inline"><strong>A</strong><strong>X</strong><strong>P</strong><strong>V</strong><strong>F</strong><strong>D</strong></span></td>
<td style="text-align: center;">1</td>
<td style="text-align: center;">0</td>
<td style="text-align: center;">0.0833</td>
<td style="text-align: center;">0</td>
<td style="text-align: center;">0</td>
<td style="text-align: center;">0</td>
<td style="text-align: center;">0</td>
<td style="text-align: center;">0</td>
<td style="text-align: center;">0</td>
<td style="text-align: center;">0</td>
<td style="text-align: center;">0</td>
<td style="text-align: center;">0</td>
<td style="text-align: center;">0</td>
<td style="text-align: center;">0</td>
<td style="text-align: center;">0</td>
<td style="text-align: center;"></td>
</tr>
<tr class="odd">
<td style="text-align: center;">1</td>
<td style="text-align: center;"><span
class="math inline"><strong>A</strong><strong>P</strong><strong>V</strong><strong>X</strong><strong>F</strong><strong>D</strong></span></td>
<td style="text-align: center;">2</td>
<td style="text-align: center;">2</td>
<td style="text-align: center;">0.0417</td>
<td style="text-align: center;">0</td>
<td style="text-align: center;">0</td>
<td style="text-align: center;">0</td>
<td style="text-align: center;">0</td>
<td style="text-align: center;">0</td>
<td style="text-align: center;">0</td>
<td style="text-align: center;">0</td>
<td style="text-align: center;">1</td>
<td style="text-align: center;">0</td>
<td style="text-align: center;">0</td>
<td style="text-align: center;">1</td>
<td style="text-align: center;">0</td>
<td style="text-align: center;"></td>
</tr>
<tr class="even">
<td style="text-align: center;">2</td>
<td style="text-align: center;"><span
class="math inline"><strong>A</strong><strong>V</strong><strong>X</strong><strong>P</strong><strong>F</strong><strong>D</strong></span></td>
<td style="text-align: center;">3</td>
<td style="text-align: center;">2</td>
<td style="text-align: center;">0.0278</td>
<td style="text-align: center;">0</td>
<td style="text-align: center;">0</td>
<td style="text-align: center;">0</td>
<td style="text-align: center;">0</td>
<td style="text-align: center;">0</td>
<td style="text-align: center;">0</td>
<td style="text-align: center;">0</td>
<td style="text-align: center;">0</td>
<td style="text-align: center;">0</td>
<td style="text-align: center;">1</td>
<td style="text-align: center;">1</td>
<td style="text-align: center;">0</td>
<td style="text-align: center;"></td>
</tr>
<tr class="odd">
<td style="text-align: center;">3</td>
<td style="text-align: center;"><span
class="math inline"><strong>X</strong><strong>P</strong><strong>V</strong><strong>A</strong><strong>F</strong><strong>D</strong></span></td>
<td style="text-align: center;">4</td>
<td style="text-align: center;">3</td>
<td style="text-align: center;">0.1250</td>
<td style="text-align: center;">0</td>
<td style="text-align: center;">0</td>
<td style="text-align: center;">0</td>
<td style="text-align: center;">0</td>
<td style="text-align: center;">0</td>
<td style="text-align: center;">0</td>
<td style="text-align: center;">1</td>
<td style="text-align: center;">0</td>
<td style="text-align: center;">1</td>
<td style="text-align: center;">0</td>
<td style="text-align: center;">0</td>
<td style="text-align: center;">1</td>
<td style="text-align: center;"></td>
</tr>
<tr class="even">
<td style="text-align: center;">4</td>
<td style="text-align: center;"><span
class="math inline"><strong>V</strong><strong>A</strong><strong>X</strong><strong>P</strong><strong>F</strong><strong>D</strong></span></td>
<td style="text-align: center;">5</td>
<td style="text-align: center;">3</td>
<td style="text-align: center;">0.0208</td>
<td style="text-align: center;">0</td>
<td style="text-align: center;">0</td>
<td style="text-align: center;">0</td>
<td style="text-align: center;">0</td>
<td style="text-align: center;">0</td>
<td style="text-align: center;">0</td>
<td style="text-align: center;">0</td>
<td style="text-align: center;">0</td>
<td style="text-align: center;">1</td>
<td style="text-align: center;">1</td>
<td style="text-align: center;">1</td>
<td style="text-align: center;">0</td>
<td style="text-align: center;"></td>
</tr>
<tr class="odd">
<td style="text-align: center;">5</td>
<td style="text-align: center;"><span
class="math inline"><strong>P</strong><strong>V</strong><strong>A</strong><strong>X</strong><strong>F</strong><strong>D</strong></span></td>
<td style="text-align: center;">6</td>
<td style="text-align: center;">4</td>
<td style="text-align: center;">0.0417</td>
<td style="text-align: center;">0</td>
<td style="text-align: center;">0</td>
<td style="text-align: center;">0</td>
<td style="text-align: center;">0</td>
<td style="text-align: center;">0</td>
<td style="text-align: center;">0</td>
<td style="text-align: center;">1</td>
<td style="text-align: center;">1</td>
<td style="text-align: center;">1</td>
<td style="text-align: center;">0</td>
<td style="text-align: center;">1</td>
<td style="text-align: center;">0</td>
<td style="text-align: center;"></td>
</tr>
<tr class="even">
<td style="text-align: center;">6</td>
<td style="text-align: center;"><span
class="math inline"><strong>A</strong><strong>V</strong><strong>P</strong><strong>X</strong><strong>F</strong><strong>D</strong></span></td>
<td style="text-align: center;">7</td>
<td style="text-align: center;">3</td>
<td style="text-align: center;">0.0139</td>
<td style="text-align: center;">0</td>
<td style="text-align: center;">0</td>
<td style="text-align: center;">0</td>
<td style="text-align: center;">0</td>
<td style="text-align: center;">0</td>
<td style="text-align: center;">0</td>
<td style="text-align: center;">0</td>
<td style="text-align: center;">1</td>
<td style="text-align: center;">0</td>
<td style="text-align: center;">1</td>
<td style="text-align: center;">1</td>
<td style="text-align: center;">0</td>
<td style="text-align: center;"></td>
</tr>
<tr class="odd">
<td style="text-align: center;">7</td>
<td style="text-align: center;"><span
class="math inline"><strong>A</strong><strong>P</strong><strong>V</strong><strong>F</strong><strong>X</strong><strong>D</strong></span></td>
<td style="text-align: center;">7</td>
<td style="text-align: center;">3</td>
<td style="text-align: center;">0.0208</td>
<td style="text-align: center;">0</td>
<td style="text-align: center;">0</td>
<td style="text-align: center;">0</td>
<td style="text-align: center;">0</td>
<td style="text-align: center;">0</td>
<td style="text-align: center;">1</td>
<td style="text-align: center;">0</td>
<td style="text-align: center;">1</td>
<td style="text-align: center;">0</td>
<td style="text-align: center;">0</td>
<td style="text-align: center;">1</td>
<td style="text-align: center;">0</td>
<td style="text-align: center;"></td>
</tr>
<tr class="even">
<td style="text-align: center;">8</td>
<td style="text-align: center;"><span
class="math inline"><strong>X</strong><strong>P</strong><strong>V</strong><strong>F</strong><strong>A</strong><strong>D</strong></span></td>
<td style="text-align: center;">8</td>
<td style="text-align: center;">4</td>
<td style="text-align: center;">0.0625</td>
<td style="text-align: center;">0</td>
<td style="text-align: center;">0</td>
<td style="text-align: center;">0</td>
<td style="text-align: center;">1</td>
<td style="text-align: center;">0</td>
<td style="text-align: center;">0</td>
<td style="text-align: center;">1</td>
<td style="text-align: center;">0</td>
<td style="text-align: center;">1</td>
<td style="text-align: center;">0</td>
<td style="text-align: center;">0</td>
<td style="text-align: center;">1</td>
<td style="text-align: center;"></td>
</tr>
<tr class="odd">
<td style="text-align: center;">9</td>
<td style="text-align: center;"><span
class="math inline"><strong>V</strong><strong>A</strong><strong>P</strong><strong>X</strong><strong>F</strong><strong>D</strong></span></td>
<td style="text-align: center;">9</td>
<td style="text-align: center;">4</td>
<td style="text-align: center;">0.0104</td>
<td style="text-align: center;">0</td>
<td style="text-align: center;">0</td>
<td style="text-align: center;">0</td>
<td style="text-align: center;">0</td>
<td style="text-align: center;">0</td>
<td style="text-align: center;">0</td>
<td style="text-align: center;">0</td>
<td style="text-align: center;">1</td>
<td style="text-align: center;">1</td>
<td style="text-align: center;">1</td>
<td style="text-align: center;">1</td>
<td style="text-align: center;">0</td>
<td style="text-align: center;"></td>
</tr>
<tr class="even">
<td style="text-align: center;">10</td>
<td style="text-align: center;"><span
class="math inline"><strong>P</strong><strong>V</strong><strong>X</strong><strong>A</strong><strong>F</strong><strong>D</strong></span></td>
<td style="text-align: center;">10</td>
<td style="text-align: center;">5</td>
<td style="text-align: center;">0.0417</td>
<td style="text-align: center;">0</td>
<td style="text-align: center;">0</td>
<td style="text-align: center;">0</td>
<td style="text-align: center;">0</td>
<td style="text-align: center;">0</td>
<td style="text-align: center;">0</td>
<td style="text-align: center;">1</td>
<td style="text-align: center;">1</td>
<td style="text-align: center;">1</td>
<td style="text-align: center;">0</td>
<td style="text-align: center;">1</td>
<td style="text-align: center;">1</td>
<td style="text-align: center;"></td>
</tr>
<tr class="odd">
<td style="text-align: center;">11</td>
<td style="text-align: center;"><span
class="math inline"><strong>V</strong><strong>P</strong><strong>A</strong><strong>X</strong><strong>F</strong><strong>D</strong></span></td>
<td style="text-align: center;">11</td>
<td style="text-align: center;">5</td>
<td style="text-align: center;">0.0104</td>
<td style="text-align: center;">0</td>
<td style="text-align: center;">0</td>
<td style="text-align: center;">0</td>
<td style="text-align: center;">0</td>
<td style="text-align: center;">0</td>
<td style="text-align: center;">0</td>
<td style="text-align: center;">1</td>
<td style="text-align: center;">1</td>
<td style="text-align: center;">1</td>
<td style="text-align: center;">1</td>
<td style="text-align: center;">1</td>
<td style="text-align: center;">0</td>
<td style="text-align: center;"></td>
</tr>
<tr class="even">
<td style="text-align: center;">12</td>
<td style="text-align: center;"><span
class="math inline"><strong>P</strong><strong>V</strong><strong>A</strong><strong>F</strong><strong>X</strong><strong>D</strong></span></td>
<td style="text-align: center;">11</td>
<td style="text-align: center;">5</td>
<td style="text-align: center;">0.0208</td>
<td style="text-align: center;">0</td>
<td style="text-align: center;">0</td>
<td style="text-align: center;">0</td>
<td style="text-align: center;">0</td>
<td style="text-align: center;">0</td>
<td style="text-align: center;">1</td>
<td style="text-align: center;">1</td>
<td style="text-align: center;">1</td>
<td style="text-align: center;">1</td>
<td style="text-align: center;">0</td>
<td style="text-align: center;">1</td>
<td style="text-align: center;">0</td>
<td style="text-align: center;"></td>
</tr>
<tr class="odd">
<td style="text-align: center;">13</td>
<td style="text-align: center;"><span
class="math inline"><strong>V</strong><strong>X</strong><strong>P</strong><strong>A</strong><strong>F</strong><strong>D</strong></span></td>
<td style="text-align: center;">11</td>
<td style="text-align: center;">5</td>
<td style="text-align: center;">0.0312</td>
<td style="text-align: center;">0</td>
<td style="text-align: center;">0</td>
<td style="text-align: center;">0</td>
<td style="text-align: center;">0</td>
<td style="text-align: center;">0</td>
<td style="text-align: center;">0</td>
<td style="text-align: center;">1</td>
<td style="text-align: center;">0</td>
<td style="text-align: center;">1</td>
<td style="text-align: center;">1</td>
<td style="text-align: center;">1</td>
<td style="text-align: center;">1</td>
<td style="text-align: center;"></td>
</tr>
<tr class="even">
<td style="text-align: center;">14</td>
<td style="text-align: center;"><span
class="math inline"><strong>A</strong><strong>V</strong><strong>P</strong><strong>F</strong><strong>X</strong><strong>D</strong></span></td>
<td style="text-align: center;">12</td>
<td style="text-align: center;">4</td>
<td style="text-align: center;">0.0069</td>
<td style="text-align: center;">0</td>
<td style="text-align: center;">0</td>
<td style="text-align: center;">0</td>
<td style="text-align: center;">0</td>
<td style="text-align: center;">0</td>
<td style="text-align: center;">1</td>
<td style="text-align: center;">0</td>
<td style="text-align: center;">1</td>
<td style="text-align: center;">0</td>
<td style="text-align: center;">1</td>
<td style="text-align: center;">1</td>
<td style="text-align: center;">0</td>
<td style="text-align: center;"></td>
</tr>
<tr class="odd">
<td style="text-align: center;">15</td>
<td style="text-align: center;"><span
class="math inline"><strong>A</strong><strong>P</strong><strong>V</strong><strong>F</strong><strong>D</strong><strong>X</strong></span></td>
<td style="text-align: center;">13</td>
<td style="text-align: center;">4</td>
<td style="text-align: center;">0.0208</td>
<td style="text-align: center;">0</td>
<td style="text-align: center;">0</td>
<td style="text-align: center;">1</td>
<td style="text-align: center;">0</td>
<td style="text-align: center;">0</td>
<td style="text-align: center;">1</td>
<td style="text-align: center;">0</td>
<td style="text-align: center;">1</td>
<td style="text-align: center;">0</td>
<td style="text-align: center;">0</td>
<td style="text-align: center;">1</td>
<td style="text-align: center;">0</td>
<td style="text-align: center;"></td>
</tr>
<tr class="even">
<td style="text-align: center;">16</td>
<td style="text-align: center;"><span
class="math inline"><strong>V</strong><strong>A</strong><strong>P</strong><strong>F</strong><strong>X</strong><strong>D</strong></span></td>
<td style="text-align: center;">14</td>
<td style="text-align: center;">5</td>
<td style="text-align: center;">0.0052</td>
<td style="text-align: center;">0</td>
<td style="text-align: center;">0</td>
<td style="text-align: center;">0</td>
<td style="text-align: center;">0</td>
<td style="text-align: center;">0</td>
<td style="text-align: center;">1</td>
<td style="text-align: center;">0</td>
<td style="text-align: center;">1</td>
<td style="text-align: center;">1</td>
<td style="text-align: center;">1</td>
<td style="text-align: center;">1</td>
<td style="text-align: center;">0</td>
<td style="text-align: center;"></td>
</tr>
<tr class="odd">
<td style="text-align: center;">17</td>
<td style="text-align: center;"><span
class="math inline"><strong>X</strong><strong>P</strong><strong>V</strong><strong>F</strong><strong>D</strong><strong>A</strong></span></td>
<td style="text-align: center;">15</td>
<td style="text-align: center;">5</td>
<td style="text-align: center;">0.0625</td>
<td style="text-align: center;">1</td>
<td style="text-align: center;">0</td>
<td style="text-align: center;">0</td>
<td style="text-align: center;">1</td>
<td style="text-align: center;">0</td>
<td style="text-align: center;">0</td>
<td style="text-align: center;">1</td>
<td style="text-align: center;">0</td>
<td style="text-align: center;">1</td>
<td style="text-align: center;">0</td>
<td style="text-align: center;">0</td>
<td style="text-align: center;">1</td>
<td style="text-align: center;"></td>
</tr>
<tr class="even">
<td style="text-align: center;">18</td>
<td style="text-align: center;"><span
class="math inline"><strong>P</strong><strong>V</strong><strong>X</strong><strong>F</strong><strong>A</strong><strong>D</strong></span></td>
<td style="text-align: center;">16</td>
<td style="text-align: center;">6</td>
<td style="text-align: center;">0.0208</td>
<td style="text-align: center;">0</td>
<td style="text-align: center;">0</td>
<td style="text-align: center;">0</td>
<td style="text-align: center;">1</td>
<td style="text-align: center;">0</td>
<td style="text-align: center;">0</td>
<td style="text-align: center;">1</td>
<td style="text-align: center;">1</td>
<td style="text-align: center;">1</td>
<td style="text-align: center;">0</td>
<td style="text-align: center;">1</td>
<td style="text-align: center;">1</td>
<td style="text-align: center;"></td>
</tr>
<tr class="odd">
<td style="text-align: center;">19</td>
<td style="text-align: center;"><span
class="math inline"><strong>A</strong><strong>V</strong><strong>F</strong><strong>X</strong><strong>P</strong><strong>D</strong></span></td>
<td style="text-align: center;">17</td>
<td style="text-align: center;">4</td>
<td style="text-align: center;">0.0093</td>
<td style="text-align: center;">0</td>
<td style="text-align: center;">0</td>
<td style="text-align: center;">0</td>
<td style="text-align: center;">0</td>
<td style="text-align: center;">1</td>
<td style="text-align: center;">1</td>
<td style="text-align: center;">0</td>
<td style="text-align: center;">0</td>
<td style="text-align: center;">0</td>
<td style="text-align: center;">1</td>
<td style="text-align: center;">1</td>
<td style="text-align: center;">0</td>
<td style="text-align: center;"></td>
</tr>
<tr class="even">
<td style="text-align: center;">20</td>
<td style="text-align: center;"><span
class="math inline"><strong>V</strong><strong>P</strong><strong>X</strong><strong>A</strong><strong>F</strong><strong>D</strong></span></td>
<td style="text-align: center;">18</td>
<td style="text-align: center;">6</td>
<td style="text-align: center;">0.0104</td>
<td style="text-align: center;">0</td>
<td style="text-align: center;">0</td>
<td style="text-align: center;">0</td>
<td style="text-align: center;">0</td>
<td style="text-align: center;">0</td>
<td style="text-align: center;">0</td>
<td style="text-align: center;">1</td>
<td style="text-align: center;">1</td>
<td style="text-align: center;">1</td>
<td style="text-align: center;">1</td>
<td style="text-align: center;">1</td>
<td style="text-align: center;">1</td>
<td style="text-align: center;"></td>
</tr>
<tr class="odd">
<td style="text-align: center;">21</td>
<td style="text-align: center;"><span
class="math inline"><strong>P</strong><strong>V</strong><strong>F</strong><strong>A</strong><strong>X</strong><strong>D</strong></span></td>
<td style="text-align: center;">19</td>
<td style="text-align: center;">6</td>
<td style="text-align: center;">0.0139</td>
<td style="text-align: center;">0</td>
<td style="text-align: center;">0</td>
<td style="text-align: center;">0</td>
<td style="text-align: center;">1</td>
<td style="text-align: center;">0</td>
<td style="text-align: center;">1</td>
<td style="text-align: center;">1</td>
<td style="text-align: center;">1</td>
<td style="text-align: center;">1</td>
<td style="text-align: center;">0</td>
<td style="text-align: center;">1</td>
<td style="text-align: center;">0</td>
<td style="text-align: center;"></td>
</tr>
<tr class="even">
<td style="text-align: center;">22</td>
<td style="text-align: center;"><span
class="math inline"><strong>V</strong><strong>X</strong><strong>P</strong><strong>F</strong><strong>A</strong><strong>D</strong></span></td>
<td style="text-align: center;">19</td>
<td style="text-align: center;">6</td>
<td style="text-align: center;">0.0156</td>
<td style="text-align: center;">0</td>
<td style="text-align: center;">0</td>
<td style="text-align: center;">0</td>
<td style="text-align: center;">1</td>
<td style="text-align: center;">0</td>
<td style="text-align: center;">0</td>
<td style="text-align: center;">1</td>
<td style="text-align: center;">0</td>
<td style="text-align: center;">1</td>
<td style="text-align: center;">1</td>
<td style="text-align: center;">1</td>
<td style="text-align: center;">1</td>
<td style="text-align: center;"></td>
</tr>
<tr class="odd">
<td style="text-align: center;">23</td>
<td style="text-align: center;"><span
class="math inline"><strong>V</strong><strong>P</strong><strong>A</strong><strong>F</strong><strong>X</strong><strong>D</strong></span></td>
<td style="text-align: center;">20</td>
<td style="text-align: center;">6</td>
<td style="text-align: center;">0.0052</td>
<td style="text-align: center;">0</td>
<td style="text-align: center;">0</td>
<td style="text-align: center;">0</td>
<td style="text-align: center;">0</td>
<td style="text-align: center;">0</td>
<td style="text-align: center;">1</td>
<td style="text-align: center;">1</td>
<td style="text-align: center;">1</td>
<td style="text-align: center;">1</td>
<td style="text-align: center;">1</td>
<td style="text-align: center;">1</td>
<td style="text-align: center;">0</td>
<td style="text-align: center;"></td>
</tr>
<tr class="even">
<td style="text-align: center;">24</td>
<td style="text-align: center;"><span
class="math inline"><strong>V</strong><strong>A</strong><strong>F</strong><strong>X</strong><strong>P</strong><strong>D</strong></span></td>
<td style="text-align: center;">21</td>
<td style="text-align: center;">5</td>
<td style="text-align: center;">0.0069</td>
<td style="text-align: center;">0</td>
<td style="text-align: center;">0</td>
<td style="text-align: center;">0</td>
<td style="text-align: center;">0</td>
<td style="text-align: center;">1</td>
<td style="text-align: center;">1</td>
<td style="text-align: center;">0</td>
<td style="text-align: center;">0</td>
<td style="text-align: center;">1</td>
<td style="text-align: center;">1</td>
<td style="text-align: center;">1</td>
<td style="text-align: center;">0</td>
<td style="text-align: center;"></td>
</tr>
<tr class="odd">
<td style="text-align: center;">25</td>
<td style="text-align: center;"><span
class="math inline"><strong>P</strong><strong>V</strong><strong>A</strong><strong>F</strong><strong>D</strong><strong>X</strong></span></td>
<td style="text-align: center;">22</td>
<td style="text-align: center;">6</td>
<td style="text-align: center;">0.0208</td>
<td style="text-align: center;">0</td>
<td style="text-align: center;">0</td>
<td style="text-align: center;">1</td>
<td style="text-align: center;">0</td>
<td style="text-align: center;">0</td>
<td style="text-align: center;">1</td>
<td style="text-align: center;">1</td>
<td style="text-align: center;">1</td>
<td style="text-align: center;">1</td>
<td style="text-align: center;">0</td>
<td style="text-align: center;">1</td>
<td style="text-align: center;">0</td>
<td style="text-align: center;"></td>
</tr>
<tr class="even">
<td style="text-align: center;">26</td>
<td style="text-align: center;"><span
class="math inline"><strong>A</strong><strong>V</strong><strong>P</strong><strong>F</strong><strong>D</strong><strong>X</strong></span></td>
<td style="text-align: center;">23</td>
<td style="text-align: center;">5</td>
<td style="text-align: center;">0.0069</td>
<td style="text-align: center;">0</td>
<td style="text-align: center;">0</td>
<td style="text-align: center;">1</td>
<td style="text-align: center;">0</td>
<td style="text-align: center;">0</td>
<td style="text-align: center;">1</td>
<td style="text-align: center;">0</td>
<td style="text-align: center;">1</td>
<td style="text-align: center;">0</td>
<td style="text-align: center;">1</td>
<td style="text-align: center;">1</td>
<td style="text-align: center;">0</td>
<td style="text-align: center;"></td>
</tr>
<tr class="odd">
<td style="text-align: center;">27</td>
<td style="text-align: center;"><span
class="math inline"><strong>A</strong><strong>V</strong><strong>F</strong><strong>P</strong><strong>X</strong><strong>D</strong></span></td>
<td style="text-align: center;">24</td>
<td style="text-align: center;">5</td>
<td style="text-align: center;">0.0046</td>
<td style="text-align: center;">0</td>
<td style="text-align: center;">0</td>
<td style="text-align: center;">0</td>
<td style="text-align: center;">0</td>
<td style="text-align: center;">1</td>
<td style="text-align: center;">1</td>
<td style="text-align: center;">0</td>
<td style="text-align: center;">1</td>
<td style="text-align: center;">0</td>
<td style="text-align: center;">1</td>
<td style="text-align: center;">1</td>
<td style="text-align: center;">0</td>
<td style="text-align: center;"></td>
</tr>
<tr class="even">
<td style="text-align: center;">28</td>
<td style="text-align: center;"><span
class="math inline"><strong>P</strong><strong>V</strong><strong>F</strong><strong>X</strong><strong>A</strong><strong>D</strong></span></td>
<td style="text-align: center;">25</td>
<td style="text-align: center;">7</td>
<td style="text-align: center;">0.0139</td>
<td style="text-align: center;">0</td>
<td style="text-align: center;">0</td>
<td style="text-align: center;">0</td>
<td style="text-align: center;">1</td>
<td style="text-align: center;">0</td>
<td style="text-align: center;">1</td>
<td style="text-align: center;">1</td>
<td style="text-align: center;">1</td>
<td style="text-align: center;">1</td>
<td style="text-align: center;">0</td>
<td style="text-align: center;">1</td>
<td style="text-align: center;">1</td>
<td style="text-align: center;"></td>
</tr>
<tr class="odd">
<td style="text-align: center;">29</td>
<td style="text-align: center;"><span
class="math inline"><strong>V</strong><strong>P</strong><strong>X</strong><strong>F</strong><strong>A</strong><strong>D</strong></span></td>
<td style="text-align: center;">25</td>
<td style="text-align: center;">7</td>
<td style="text-align: center;">0.0052</td>
<td style="text-align: center;">0</td>
<td style="text-align: center;">0</td>
<td style="text-align: center;">0</td>
<td style="text-align: center;">1</td>
<td style="text-align: center;">0</td>
<td style="text-align: center;">0</td>
<td style="text-align: center;">1</td>
<td style="text-align: center;">1</td>
<td style="text-align: center;">1</td>
<td style="text-align: center;">1</td>
<td style="text-align: center;">1</td>
<td style="text-align: center;">1</td>
<td style="text-align: center;"></td>
</tr>
<tr class="even">
<td style="text-align: center;">30</td>
<td style="text-align: center;"><span
class="math inline"><strong>V</strong><strong>A</strong><strong>P</strong><strong>F</strong><strong>D</strong><strong>X</strong></span></td>
<td style="text-align: center;">26</td>
<td style="text-align: center;">6</td>
<td style="text-align: center;">0.0052</td>
<td style="text-align: center;">0</td>
<td style="text-align: center;">0</td>
<td style="text-align: center;">1</td>
<td style="text-align: center;">0</td>
<td style="text-align: center;">0</td>
<td style="text-align: center;">1</td>
<td style="text-align: center;">0</td>
<td style="text-align: center;">1</td>
<td style="text-align: center;">1</td>
<td style="text-align: center;">1</td>
<td style="text-align: center;">1</td>
<td style="text-align: center;">0</td>
<td style="text-align: center;"></td>
</tr>
<tr class="odd">
<td style="text-align: center;">31</td>
<td style="text-align: center;"><span
class="math inline"><strong>V</strong><strong>A</strong><strong>F</strong><strong>P</strong><strong>X</strong><strong>D</strong></span></td>
<td style="text-align: center;">27</td>
<td style="text-align: center;">6</td>
<td style="text-align: center;">0.0035</td>
<td style="text-align: center;">0</td>
<td style="text-align: center;">0</td>
<td style="text-align: center;">0</td>
<td style="text-align: center;">0</td>
<td style="text-align: center;">1</td>
<td style="text-align: center;">1</td>
<td style="text-align: center;">0</td>
<td style="text-align: center;">1</td>
<td style="text-align: center;">1</td>
<td style="text-align: center;">1</td>
<td style="text-align: center;">1</td>
<td style="text-align: center;">0</td>
<td style="text-align: center;"></td>
</tr>
<tr class="even">
<td style="text-align: center;">32</td>
<td style="text-align: center;"><span
class="math inline"><strong>P</strong><strong>V</strong><strong>X</strong><strong>F</strong><strong>D</strong><strong>A</strong></span></td>
<td style="text-align: center;">28</td>
<td style="text-align: center;">7</td>
<td style="text-align: center;">0.0208</td>
<td style="text-align: center;">1</td>
<td style="text-align: center;">0</td>
<td style="text-align: center;">0</td>
<td style="text-align: center;">1</td>
<td style="text-align: center;">0</td>
<td style="text-align: center;">0</td>
<td style="text-align: center;">1</td>
<td style="text-align: center;">1</td>
<td style="text-align: center;">1</td>
<td style="text-align: center;">0</td>
<td style="text-align: center;">1</td>
<td style="text-align: center;">1</td>
<td style="text-align: center;"></td>
</tr>
<tr class="odd">
<td style="text-align: center;">33</td>
<td style="text-align: center;"><span
class="math inline"><strong>V</strong><strong>P</strong><strong>F</strong><strong>A</strong><strong>X</strong><strong>D</strong></span></td>
<td style="text-align: center;">29</td>
<td style="text-align: center;">7</td>
<td style="text-align: center;">0.0035</td>
<td style="text-align: center;">0</td>
<td style="text-align: center;">0</td>
<td style="text-align: center;">0</td>
<td style="text-align: center;">1</td>
<td style="text-align: center;">0</td>
<td style="text-align: center;">1</td>
<td style="text-align: center;">1</td>
<td style="text-align: center;">1</td>
<td style="text-align: center;">1</td>
<td style="text-align: center;">1</td>
<td style="text-align: center;">1</td>
<td style="text-align: center;">0</td>
<td style="text-align: center;"></td>
</tr>
<tr class="even">
<td style="text-align: center;">34</td>
<td style="text-align: center;"><span
class="math inline"><strong>V</strong><strong>F</strong><strong>A</strong><strong>X</strong><strong>P</strong><strong>D</strong></span></td>
<td style="text-align: center;">30</td>
<td style="text-align: center;">6</td>
<td style="text-align: center;">0.0052</td>
<td style="text-align: center;">0</td>
<td style="text-align: center;">0</td>
<td style="text-align: center;">0</td>
<td style="text-align: center;">1</td>
<td style="text-align: center;">1</td>
<td style="text-align: center;">1</td>
<td style="text-align: center;">0</td>
<td style="text-align: center;">0</td>
<td style="text-align: center;">1</td>
<td style="text-align: center;">1</td>
<td style="text-align: center;">1</td>
<td style="text-align: center;">0</td>
<td style="text-align: center;"></td>
</tr>
<tr class="odd">
<td style="text-align: center;">35</td>
<td style="text-align: center;"><span
class="math inline"><strong>V</strong><strong>X</strong><strong>P</strong><strong>F</strong><strong>D</strong><strong>A</strong></span></td>
<td style="text-align: center;">31</td>
<td style="text-align: center;">7</td>
<td style="text-align: center;">0.0156</td>
<td style="text-align: center;">1</td>
<td style="text-align: center;">0</td>
<td style="text-align: center;">0</td>
<td style="text-align: center;">1</td>
<td style="text-align: center;">0</td>
<td style="text-align: center;">0</td>
<td style="text-align: center;">1</td>
<td style="text-align: center;">0</td>
<td style="text-align: center;">1</td>
<td style="text-align: center;">1</td>
<td style="text-align: center;">1</td>
<td style="text-align: center;">1</td>
<td style="text-align: center;"></td>
</tr>
<tr class="even">
<td style="text-align: center;">36</td>
<td style="text-align: center;"><span
class="math inline"><strong>P</strong><strong>V</strong><strong>F</strong><strong>A</strong><strong>D</strong><strong>X</strong></span></td>
<td style="text-align: center;">32</td>
<td style="text-align: center;">7</td>
<td style="text-align: center;">0.0139</td>
<td style="text-align: center;">0</td>
<td style="text-align: center;">0</td>
<td style="text-align: center;">1</td>
<td style="text-align: center;">1</td>
<td style="text-align: center;">0</td>
<td style="text-align: center;">1</td>
<td style="text-align: center;">1</td>
<td style="text-align: center;">1</td>
<td style="text-align: center;">1</td>
<td style="text-align: center;">0</td>
<td style="text-align: center;">1</td>
<td style="text-align: center;">0</td>
<td style="text-align: center;"></td>
</tr>
<tr class="odd">
<td style="text-align: center;">37</td>
<td style="text-align: center;"><span
class="math inline"><strong>V</strong><strong>P</strong><strong>A</strong><strong>F</strong><strong>D</strong><strong>X</strong></span></td>
<td style="text-align: center;">33</td>
<td style="text-align: center;">7</td>
<td style="text-align: center;">0.0052</td>
<td style="text-align: center;">0</td>
<td style="text-align: center;">0</td>
<td style="text-align: center;">1</td>
<td style="text-align: center;">0</td>
<td style="text-align: center;">0</td>
<td style="text-align: center;">1</td>
<td style="text-align: center;">1</td>
<td style="text-align: center;">1</td>
<td style="text-align: center;">1</td>
<td style="text-align: center;">1</td>
<td style="text-align: center;">1</td>
<td style="text-align: center;">0</td>
<td style="text-align: center;"></td>
</tr>
<tr class="even">
<td style="text-align: center;">38</td>
<td style="text-align: center;"><span
class="math inline"><strong>V</strong><strong>P</strong><strong>F</strong><strong>X</strong><strong>A</strong><strong>D</strong></span></td>
<td style="text-align: center;">34</td>
<td style="text-align: center;">8</td>
<td style="text-align: center;">0.0035</td>
<td style="text-align: center;">0</td>
<td style="text-align: center;">0</td>
<td style="text-align: center;">0</td>
<td style="text-align: center;">1</td>
<td style="text-align: center;">0</td>
<td style="text-align: center;">1</td>
<td style="text-align: center;">1</td>
<td style="text-align: center;">1</td>
<td style="text-align: center;">1</td>
<td style="text-align: center;">1</td>
<td style="text-align: center;">1</td>
<td style="text-align: center;">1</td>
<td style="text-align: center;"></td>
</tr>
<tr class="odd">
<td style="text-align: center;">39</td>
<td style="text-align: center;"><span
class="math inline"><strong>A</strong><strong>V</strong><strong>F</strong><strong>P</strong><strong>D</strong><strong>X</strong></span></td>
<td style="text-align: center;">35</td>
<td style="text-align: center;">6</td>
<td style="text-align: center;">0.0046</td>
<td style="text-align: center;">0</td>
<td style="text-align: center;">0</td>
<td style="text-align: center;">1</td>
<td style="text-align: center;">0</td>
<td style="text-align: center;">1</td>
<td style="text-align: center;">1</td>
<td style="text-align: center;">0</td>
<td style="text-align: center;">1</td>
<td style="text-align: center;">0</td>
<td style="text-align: center;">1</td>
<td style="text-align: center;">1</td>
<td style="text-align: center;">0</td>
<td style="text-align: center;"></td>
</tr>
<tr class="even">
<td style="text-align: center;">40</td>
<td style="text-align: center;"><span
class="math inline"><strong>V</strong><strong>F</strong><strong>A</strong><strong>P</strong><strong>X</strong><strong>D</strong></span></td>
<td style="text-align: center;">36</td>
<td style="text-align: center;">7</td>
<td style="text-align: center;">0.0026</td>
<td style="text-align: center;">0</td>
<td style="text-align: center;">0</td>
<td style="text-align: center;">0</td>
<td style="text-align: center;">1</td>
<td style="text-align: center;">1</td>
<td style="text-align: center;">1</td>
<td style="text-align: center;">0</td>
<td style="text-align: center;">1</td>
<td style="text-align: center;">1</td>
<td style="text-align: center;">1</td>
<td style="text-align: center;">1</td>
<td style="text-align: center;">0</td>
<td style="text-align: center;"></td>
</tr>
<tr class="odd">
<td style="text-align: center;">41</td>
<td style="text-align: center;"><span
class="math inline"><strong>V</strong><strong>P</strong><strong>X</strong><strong>F</strong><strong>D</strong><strong>A</strong></span></td>
<td style="text-align: center;">37</td>
<td style="text-align: center;">8</td>
<td style="text-align: center;">0.0052</td>
<td style="text-align: center;">1</td>
<td style="text-align: center;">0</td>
<td style="text-align: center;">0</td>
<td style="text-align: center;">1</td>
<td style="text-align: center;">0</td>
<td style="text-align: center;">0</td>
<td style="text-align: center;">1</td>
<td style="text-align: center;">1</td>
<td style="text-align: center;">1</td>
<td style="text-align: center;">1</td>
<td style="text-align: center;">1</td>
<td style="text-align: center;">1</td>
<td style="text-align: center;"></td>
</tr>
<tr class="even">
<td style="text-align: center;">42</td>
<td style="text-align: center;"><span
class="math inline"><strong>P</strong><strong>V</strong><strong>F</strong><strong>X</strong><strong>D</strong><strong>A</strong></span></td>
<td style="text-align: center;">37</td>
<td style="text-align: center;">8</td>
<td style="text-align: center;">0.0139</td>
<td style="text-align: center;">1</td>
<td style="text-align: center;">0</td>
<td style="text-align: center;">0</td>
<td style="text-align: center;">1</td>
<td style="text-align: center;">0</td>
<td style="text-align: center;">1</td>
<td style="text-align: center;">1</td>
<td style="text-align: center;">1</td>
<td style="text-align: center;">1</td>
<td style="text-align: center;">0</td>
<td style="text-align: center;">1</td>
<td style="text-align: center;">1</td>
<td style="text-align: center;"></td>
</tr>
<tr class="odd">
<td style="text-align: center;">43</td>
<td style="text-align: center;"><span
class="math inline"><strong>V</strong><strong>A</strong><strong>F</strong><strong>P</strong><strong>D</strong><strong>X</strong></span></td>
<td style="text-align: center;">38</td>
<td style="text-align: center;">7</td>
<td style="text-align: center;">0.0035</td>
<td style="text-align: center;">0</td>
<td style="text-align: center;">0</td>
<td style="text-align: center;">1</td>
<td style="text-align: center;">0</td>
<td style="text-align: center;">1</td>
<td style="text-align: center;">1</td>
<td style="text-align: center;">0</td>
<td style="text-align: center;">1</td>
<td style="text-align: center;">1</td>
<td style="text-align: center;">1</td>
<td style="text-align: center;">1</td>
<td style="text-align: center;">0</td>
<td style="text-align: center;"></td>
</tr>
<tr class="even">
<td style="text-align: center;">44</td>
<td style="text-align: center;"><span
class="math inline"><strong>V</strong><strong>P</strong><strong>F</strong><strong>A</strong><strong>D</strong><strong>X</strong></span></td>
<td style="text-align: center;">39</td>
<td style="text-align: center;">8</td>
<td style="text-align: center;">0.0035</td>
<td style="text-align: center;">0</td>
<td style="text-align: center;">0</td>
<td style="text-align: center;">1</td>
<td style="text-align: center;">1</td>
<td style="text-align: center;">0</td>
<td style="text-align: center;">1</td>
<td style="text-align: center;">1</td>
<td style="text-align: center;">1</td>
<td style="text-align: center;">1</td>
<td style="text-align: center;">1</td>
<td style="text-align: center;">1</td>
<td style="text-align: center;">0</td>
<td style="text-align: center;"></td>
</tr>
<tr class="odd">
<td style="text-align: center;">45</td>
<td style="text-align: center;"><span
class="math inline"><strong>V</strong><strong>F</strong><strong>P</strong><strong>A</strong><strong>X</strong><strong>D</strong></span></td>
<td style="text-align: center;">40</td>
<td style="text-align: center;">8</td>
<td style="text-align: center;">0.0026</td>
<td style="text-align: center;">0</td>
<td style="text-align: center;">0</td>
<td style="text-align: center;">0</td>
<td style="text-align: center;">1</td>
<td style="text-align: center;">1</td>
<td style="text-align: center;">1</td>
<td style="text-align: center;">1</td>
<td style="text-align: center;">1</td>
<td style="text-align: center;">1</td>
<td style="text-align: center;">1</td>
<td style="text-align: center;">1</td>
<td style="text-align: center;">0</td>
<td style="text-align: center;"></td>
</tr>
<tr class="even">
<td style="text-align: center;">46</td>
<td style="text-align: center;"><span
class="math inline"><strong>V</strong><strong>F</strong><strong>X</strong><strong>P</strong><strong>A</strong><strong>D</strong></span></td>
<td style="text-align: center;">41</td>
<td style="text-align: center;">8</td>
<td style="text-align: center;">0.0078</td>
<td style="text-align: center;">0</td>
<td style="text-align: center;">0</td>
<td style="text-align: center;">0</td>
<td style="text-align: center;">1</td>
<td style="text-align: center;">1</td>
<td style="text-align: center;">1</td>
<td style="text-align: center;">1</td>
<td style="text-align: center;">0</td>
<td style="text-align: center;">1</td>
<td style="text-align: center;">1</td>
<td style="text-align: center;">1</td>
<td style="text-align: center;">1</td>
<td style="text-align: center;"></td>
</tr>
<tr class="odd">
<td style="text-align: center;">47</td>
<td style="text-align: center;"><span
class="math inline"><strong>A</strong><strong>V</strong><strong>F</strong><strong>D</strong><strong>X</strong><strong>P</strong></span></td>
<td style="text-align: center;">42</td>
<td style="text-align: center;">6</td>
<td style="text-align: center;">0.0046</td>
<td style="text-align: center;">0</td>
<td style="text-align: center;">1</td>
<td style="text-align: center;">1</td>
<td style="text-align: center;">0</td>
<td style="text-align: center;">1</td>
<td style="text-align: center;">1</td>
<td style="text-align: center;">0</td>
<td style="text-align: center;">0</td>
<td style="text-align: center;">0</td>
<td style="text-align: center;">1</td>
<td style="text-align: center;">1</td>
<td style="text-align: center;">0</td>
<td style="text-align: center;"></td>
</tr>
<tr class="even">
<td style="text-align: center;">48</td>
<td style="text-align: center;"><span
class="math inline"><strong>P</strong><strong>V</strong><strong>F</strong><strong>D</strong><strong>A</strong><strong>X</strong></span></td>
<td style="text-align: center;">43</td>
<td style="text-align: center;">8</td>
<td style="text-align: center;">0.0139</td>
<td style="text-align: center;">1</td>
<td style="text-align: center;">0</td>
<td style="text-align: center;">1</td>
<td style="text-align: center;">1</td>
<td style="text-align: center;">0</td>
<td style="text-align: center;">1</td>
<td style="text-align: center;">1</td>
<td style="text-align: center;">1</td>
<td style="text-align: center;">1</td>
<td style="text-align: center;">0</td>
<td style="text-align: center;">1</td>
<td style="text-align: center;">0</td>
<td style="text-align: center;"></td>
</tr>
<tr class="odd">
<td style="text-align: center;">49</td>
<td style="text-align: center;"><span
class="math inline"><strong>V</strong><strong>A</strong><strong>F</strong><strong>D</strong><strong>X</strong><strong>P</strong></span></td>
<td style="text-align: center;">44</td>
<td style="text-align: center;">7</td>
<td style="text-align: center;">0.0035</td>
<td style="text-align: center;">0</td>
<td style="text-align: center;">1</td>
<td style="text-align: center;">1</td>
<td style="text-align: center;">0</td>
<td style="text-align: center;">1</td>
<td style="text-align: center;">1</td>
<td style="text-align: center;">0</td>
<td style="text-align: center;">0</td>
<td style="text-align: center;">1</td>
<td style="text-align: center;">1</td>
<td style="text-align: center;">1</td>
<td style="text-align: center;">0</td>
<td style="text-align: center;"></td>
</tr>
<tr class="even">
<td style="text-align: center;">50</td>
<td style="text-align: center;"><span
class="math inline"><strong>V</strong><strong>P</strong><strong>F</strong><strong>X</strong><strong>D</strong><strong>A</strong></span></td>
<td style="text-align: center;">45</td>
<td style="text-align: center;">9</td>
<td style="text-align: center;">0.0035</td>
<td style="text-align: center;">1</td>
<td style="text-align: center;">0</td>
<td style="text-align: center;">0</td>
<td style="text-align: center;">1</td>
<td style="text-align: center;">0</td>
<td style="text-align: center;">1</td>
<td style="text-align: center;">1</td>
<td style="text-align: center;">1</td>
<td style="text-align: center;">1</td>
<td style="text-align: center;">1</td>
<td style="text-align: center;">1</td>
<td style="text-align: center;">1</td>
<td style="text-align: center;"></td>
</tr>
<tr class="odd">
<td style="text-align: center;">51</td>
<td style="text-align: center;"><span
class="math inline"><strong>V</strong><strong>F</strong><strong>A</strong><strong>P</strong><strong>D</strong><strong>X</strong></span></td>
<td style="text-align: center;">46</td>
<td style="text-align: center;">8</td>
<td style="text-align: center;">0.0026</td>
<td style="text-align: center;">0</td>
<td style="text-align: center;">0</td>
<td style="text-align: center;">1</td>
<td style="text-align: center;">1</td>
<td style="text-align: center;">1</td>
<td style="text-align: center;">1</td>
<td style="text-align: center;">0</td>
<td style="text-align: center;">1</td>
<td style="text-align: center;">1</td>
<td style="text-align: center;">1</td>
<td style="text-align: center;">1</td>
<td style="text-align: center;">0</td>
<td style="text-align: center;"></td>
</tr>
<tr class="even">
<td style="text-align: center;">52</td>
<td style="text-align: center;"><span
class="math inline"><strong>V</strong><strong>F</strong><strong>P</strong><strong>X</strong><strong>A</strong><strong>D</strong></span></td>
<td style="text-align: center;">46</td>
<td style="text-align: center;">9</td>
<td style="text-align: center;">0.0026</td>
<td style="text-align: center;">0</td>
<td style="text-align: center;">0</td>
<td style="text-align: center;">0</td>
<td style="text-align: center;">1</td>
<td style="text-align: center;">1</td>
<td style="text-align: center;">1</td>
<td style="text-align: center;">1</td>
<td style="text-align: center;">1</td>
<td style="text-align: center;">1</td>
<td style="text-align: center;">1</td>
<td style="text-align: center;">1</td>
<td style="text-align: center;">1</td>
<td style="text-align: center;"></td>
</tr>
<tr class="odd">
<td style="text-align: center;">53</td>
<td style="text-align: center;"><span
class="math inline"><strong>A</strong><strong>V</strong><strong>F</strong><strong>D</strong><strong>P</strong><strong>X</strong></span></td>
<td style="text-align: center;">47</td>
<td style="text-align: center;">7</td>
<td style="text-align: center;">0.0046</td>
<td style="text-align: center;">0</td>
<td style="text-align: center;">1</td>
<td style="text-align: center;">1</td>
<td style="text-align: center;">0</td>
<td style="text-align: center;">1</td>
<td style="text-align: center;">1</td>
<td style="text-align: center;">0</td>
<td style="text-align: center;">1</td>
<td style="text-align: center;">0</td>
<td style="text-align: center;">1</td>
<td style="text-align: center;">1</td>
<td style="text-align: center;">0</td>
<td style="text-align: center;"></td>
</tr>
<tr class="even">
<td style="text-align: center;">54</td>
<td style="text-align: center;"><span
class="math inline"><strong>P</strong><strong>V</strong><strong>F</strong><strong>D</strong><strong>X</strong><strong>A</strong></span></td>
<td style="text-align: center;">48</td>
<td style="text-align: center;">9</td>
<td style="text-align: center;">0.0139</td>
<td style="text-align: center;">1</td>
<td style="text-align: center;">0</td>
<td style="text-align: center;">1</td>
<td style="text-align: center;">1</td>
<td style="text-align: center;">0</td>
<td style="text-align: center;">1</td>
<td style="text-align: center;">1</td>
<td style="text-align: center;">1</td>
<td style="text-align: center;">1</td>
<td style="text-align: center;">0</td>
<td style="text-align: center;">1</td>
<td style="text-align: center;">1</td>
<td style="text-align: center;"></td>
</tr>
<tr class="odd">
<td style="text-align: center;">55</td>
<td style="text-align: center;"><span
class="math inline"><strong>V</strong><strong>P</strong><strong>F</strong><strong>D</strong><strong>A</strong><strong>X</strong></span></td>
<td style="text-align: center;">49</td>
<td style="text-align: center;">9</td>
<td style="text-align: center;">0.0035</td>
<td style="text-align: center;">1</td>
<td style="text-align: center;">0</td>
<td style="text-align: center;">1</td>
<td style="text-align: center;">1</td>
<td style="text-align: center;">0</td>
<td style="text-align: center;">1</td>
<td style="text-align: center;">1</td>
<td style="text-align: center;">1</td>
<td style="text-align: center;">1</td>
<td style="text-align: center;">1</td>
<td style="text-align: center;">1</td>
<td style="text-align: center;">0</td>
<td style="text-align: center;"></td>
</tr>
<tr class="even">
<td style="text-align: center;">56</td>
<td style="text-align: center;"><span
class="math inline"><strong>V</strong><strong>F</strong><strong>X</strong><strong>P</strong><strong>D</strong><strong>A</strong></span></td>
<td style="text-align: center;">50</td>
<td style="text-align: center;">9</td>
<td style="text-align: center;">0.0078</td>
<td style="text-align: center;">1</td>
<td style="text-align: center;">0</td>
<td style="text-align: center;">0</td>
<td style="text-align: center;">1</td>
<td style="text-align: center;">1</td>
<td style="text-align: center;">1</td>
<td style="text-align: center;">1</td>
<td style="text-align: center;">0</td>
<td style="text-align: center;">1</td>
<td style="text-align: center;">1</td>
<td style="text-align: center;">1</td>
<td style="text-align: center;">1</td>
<td style="text-align: center;"></td>
</tr>
<tr class="odd">
<td style="text-align: center;">57</td>
<td style="text-align: center;"><span
class="math inline"><strong>V</strong><strong>F</strong><strong>P</strong><strong>A</strong><strong>D</strong><strong>X</strong></span></td>
<td style="text-align: center;">51</td>
<td style="text-align: center;">9</td>
<td style="text-align: center;">0.0026</td>
<td style="text-align: center;">0</td>
<td style="text-align: center;">0</td>
<td style="text-align: center;">1</td>
<td style="text-align: center;">1</td>
<td style="text-align: center;">1</td>
<td style="text-align: center;">1</td>
<td style="text-align: center;">1</td>
<td style="text-align: center;">1</td>
<td style="text-align: center;">1</td>
<td style="text-align: center;">1</td>
<td style="text-align: center;">1</td>
<td style="text-align: center;">0</td>
<td style="text-align: center;"></td>
</tr>
<tr class="even">
<td style="text-align: center;">58</td>
<td style="text-align: center;"><span
class="math inline"><strong>V</strong><strong>A</strong><strong>F</strong><strong>D</strong><strong>P</strong><strong>X</strong></span></td>
<td style="text-align: center;">52</td>
<td style="text-align: center;">8</td>
<td style="text-align: center;">0.0035</td>
<td style="text-align: center;">0</td>
<td style="text-align: center;">1</td>
<td style="text-align: center;">1</td>
<td style="text-align: center;">0</td>
<td style="text-align: center;">1</td>
<td style="text-align: center;">1</td>
<td style="text-align: center;">0</td>
<td style="text-align: center;">1</td>
<td style="text-align: center;">1</td>
<td style="text-align: center;">1</td>
<td style="text-align: center;">1</td>
<td style="text-align: center;">0</td>
<td style="text-align: center;"></td>
</tr>
<tr class="odd">
<td style="text-align: center;">59</td>
<td style="text-align: center;"><span
class="math inline"><strong>V</strong><strong>F</strong><strong>A</strong><strong>D</strong><strong>X</strong><strong>P</strong></span></td>
<td style="text-align: center;">53</td>
<td style="text-align: center;">8</td>
<td style="text-align: center;">0.0026</td>
<td style="text-align: center;">0</td>
<td style="text-align: center;">1</td>
<td style="text-align: center;">1</td>
<td style="text-align: center;">1</td>
<td style="text-align: center;">1</td>
<td style="text-align: center;">1</td>
<td style="text-align: center;">0</td>
<td style="text-align: center;">0</td>
<td style="text-align: center;">1</td>
<td style="text-align: center;">1</td>
<td style="text-align: center;">1</td>
<td style="text-align: center;">0</td>
<td style="text-align: center;"></td>
</tr>
<tr class="even">
<td style="text-align: center;">60</td>
<td style="text-align: center;"><span
class="math inline"><strong>V</strong><strong>P</strong><strong>F</strong><strong>D</strong><strong>X</strong><strong>A</strong></span></td>
<td style="text-align: center;">54</td>
<td style="text-align: center;">10</td>
<td style="text-align: center;">0.0035</td>
<td style="text-align: center;">1</td>
<td style="text-align: center;">0</td>
<td style="text-align: center;">1</td>
<td style="text-align: center;">1</td>
<td style="text-align: center;">0</td>
<td style="text-align: center;">1</td>
<td style="text-align: center;">1</td>
<td style="text-align: center;">1</td>
<td style="text-align: center;">1</td>
<td style="text-align: center;">1</td>
<td style="text-align: center;">1</td>
<td style="text-align: center;">1</td>
<td style="text-align: center;"></td>
</tr>
<tr class="odd">
<td style="text-align: center;">61</td>
<td style="text-align: center;"><span
class="math inline"><strong>V</strong><strong>F</strong><strong>P</strong><strong>X</strong><strong>D</strong><strong>A</strong></span></td>
<td style="text-align: center;">55</td>
<td style="text-align: center;">10</td>
<td style="text-align: center;">0.0026</td>
<td style="text-align: center;">1</td>
<td style="text-align: center;">0</td>
<td style="text-align: center;">0</td>
<td style="text-align: center;">1</td>
<td style="text-align: center;">1</td>
<td style="text-align: center;">1</td>
<td style="text-align: center;">1</td>
<td style="text-align: center;">1</td>
<td style="text-align: center;">1</td>
<td style="text-align: center;">1</td>
<td style="text-align: center;">1</td>
<td style="text-align: center;">1</td>
<td style="text-align: center;"></td>
</tr>
<tr class="even">
<td style="text-align: center;">62</td>
<td style="text-align: center;"><span
class="math inline"><strong>V</strong><strong>F</strong><strong>A</strong><strong>D</strong><strong>P</strong><strong>X</strong></span></td>
<td style="text-align: center;">56</td>
<td style="text-align: center;">9</td>
<td style="text-align: center;">0.0026</td>
<td style="text-align: center;">0</td>
<td style="text-align: center;">1</td>
<td style="text-align: center;">1</td>
<td style="text-align: center;">1</td>
<td style="text-align: center;">1</td>
<td style="text-align: center;">1</td>
<td style="text-align: center;">0</td>
<td style="text-align: center;">1</td>
<td style="text-align: center;">1</td>
<td style="text-align: center;">1</td>
<td style="text-align: center;">1</td>
<td style="text-align: center;">0</td>
<td style="text-align: center;"></td>
</tr>
<tr class="odd">
<td style="text-align: center;">63</td>
<td style="text-align: center;"><span
class="math inline"><strong>V</strong><strong>F</strong><strong>P</strong><strong>D</strong><strong>A</strong><strong>X</strong></span></td>
<td style="text-align: center;">57</td>
<td style="text-align: center;">10</td>
<td style="text-align: center;">0.0026</td>
<td style="text-align: center;">1</td>
<td style="text-align: center;">0</td>
<td style="text-align: center;">1</td>
<td style="text-align: center;">1</td>
<td style="text-align: center;">1</td>
<td style="text-align: center;">1</td>
<td style="text-align: center;">1</td>
<td style="text-align: center;">1</td>
<td style="text-align: center;">1</td>
<td style="text-align: center;">1</td>
<td style="text-align: center;">1</td>
<td style="text-align: center;">0</td>
<td style="text-align: center;"></td>
</tr>
<tr class="even">
<td style="text-align: center;">64</td>
<td style="text-align: center;"><span
class="math inline"><strong>V</strong><strong>F</strong><strong>D</strong><strong>A</strong><strong>X</strong><strong>P</strong></span></td>
<td style="text-align: center;">58</td>
<td style="text-align: center;">9</td>
<td style="text-align: center;">0.0026</td>
<td style="text-align: center;">1</td>
<td style="text-align: center;">1</td>
<td style="text-align: center;">1</td>
<td style="text-align: center;">1</td>
<td style="text-align: center;">1</td>
<td style="text-align: center;">1</td>
<td style="text-align: center;">0</td>
<td style="text-align: center;">0</td>
<td style="text-align: center;">1</td>
<td style="text-align: center;">1</td>
<td style="text-align: center;">1</td>
<td style="text-align: center;">0</td>
<td style="text-align: center;"></td>
</tr>
<tr class="odd">
<td style="text-align: center;">65</td>
<td style="text-align: center;"><span
class="math inline"><strong>V</strong><strong>F</strong><strong>P</strong><strong>D</strong><strong>X</strong><strong>A</strong></span></td>
<td style="text-align: center;">59</td>
<td style="text-align: center;">11</td>
<td style="text-align: center;">0.0026</td>
<td style="text-align: center;">1</td>
<td style="text-align: center;">0</td>
<td style="text-align: center;">1</td>
<td style="text-align: center;">1</td>
<td style="text-align: center;">1</td>
<td style="text-align: center;">1</td>
<td style="text-align: center;">1</td>
<td style="text-align: center;">1</td>
<td style="text-align: center;">1</td>
<td style="text-align: center;">1</td>
<td style="text-align: center;">1</td>
<td style="text-align: center;">1</td>
<td style="text-align: center;"></td>
</tr>
<tr class="even">
<td style="text-align: center;">66</td>
<td style="text-align: center;"><span
class="math inline"><strong>V</strong><strong>F</strong><strong>D</strong><strong>A</strong><strong>P</strong><strong>X</strong></span></td>
<td style="text-align: center;">60</td>
<td style="text-align: center;">10</td>
<td style="text-align: center;">0.0026</td>
<td style="text-align: center;">1</td>
<td style="text-align: center;">1</td>
<td style="text-align: center;">1</td>
<td style="text-align: center;">1</td>
<td style="text-align: center;">1</td>
<td style="text-align: center;">1</td>
<td style="text-align: center;">0</td>
<td style="text-align: center;">1</td>
<td style="text-align: center;">1</td>
<td style="text-align: center;">1</td>
<td style="text-align: center;">1</td>
<td style="text-align: center;">0</td>
<td style="text-align: center;"></td>
</tr>
<tr class="odd">
<td style="text-align: center;">67</td>
<td style="text-align: center;"><span
class="math inline"><strong>V</strong><strong>F</strong><strong>D</strong><strong>X</strong><strong>P</strong><strong>A</strong></span></td>
<td style="text-align: center;">61</td>
<td style="text-align: center;">11</td>
<td style="text-align: center;">0.0052</td>
<td style="text-align: center;">1</td>
<td style="text-align: center;">1</td>
<td style="text-align: center;">1</td>
<td style="text-align: center;">1</td>
<td style="text-align: center;">1</td>
<td style="text-align: center;">1</td>
<td style="text-align: center;">1</td>
<td style="text-align: center;">0</td>
<td style="text-align: center;">1</td>
<td style="text-align: center;">1</td>
<td style="text-align: center;">1</td>
<td style="text-align: center;">1</td>
<td style="text-align: center;"></td>
</tr>
<tr class="even">
<td style="text-align: center;">68</td>
<td style="text-align: center;"><span
class="math inline"><strong>V</strong><strong>F</strong><strong>D</strong><strong>P</strong><strong>A</strong><strong>X</strong></span></td>
<td style="text-align: center;">61</td>
<td style="text-align: center;">11</td>
<td style="text-align: center;">0.0026</td>
<td style="text-align: center;">1</td>
<td style="text-align: center;">1</td>
<td style="text-align: center;">1</td>
<td style="text-align: center;">1</td>
<td style="text-align: center;">1</td>
<td style="text-align: center;">1</td>
<td style="text-align: center;">1</td>
<td style="text-align: center;">1</td>
<td style="text-align: center;">1</td>
<td style="text-align: center;">1</td>
<td style="text-align: center;">1</td>
<td style="text-align: center;">0</td>
<td style="text-align: center;"></td>
</tr>
<tr class="odd">
<td style="text-align: center;">69</td>
<td style="text-align: center;"><span
class="math inline"><strong>V</strong><strong>F</strong><strong>D</strong><strong>P</strong><strong>X</strong><strong>A</strong></span></td>
<td style="text-align: center;">62</td>
<td style="text-align: center;">12</td>
<td style="text-align: center;">0.0026</td>
<td style="text-align: center;">1</td>
<td style="text-align: center;">1</td>
<td style="text-align: center;">1</td>
<td style="text-align: center;">1</td>
<td style="text-align: center;">1</td>
<td style="text-align: center;">1</td>
<td style="text-align: center;">1</td>
<td style="text-align: center;">1</td>
<td style="text-align: center;">1</td>
<td style="text-align: center;">1</td>
<td style="text-align: center;">1</td>
<td style="text-align: center;">1</td>
<td style="text-align: center;"></td>
</tr>
</tbody>
</table>

: Possible Histories $h \in \mathcal{H}$ of CVD
:::

Now that we have defined the set of histories $\mathcal{H}$, we can
summarize the effects of the transition function $\delta$ developed in
§[2.4](#sec:transitions){reference-type="ref"
reference="sec:transitions"} (Table
[2.6](#tab:delta_vfdpxa){reference-type="ref"
reference="tab:delta_vfdpxa"}) as a set of patterns it imposes on all
histories $h \in \mathcal{H}$. First, the causality constraint of the
vendor fix path must hold. $$\label{eq:history_vfd_rule}
\mathbf{V} \prec \mathbf{F} \prec \mathbf{D}$$

Second, the model makes the simplifying assumption that vendors know at
least as much as the public does. In other words, all histories must
meet one of two criteria: either Vendor Awareness precedes Public
Awareness ($\mathbf{P}$) or Vendor Awareness must immediately follow it.

$$\label{eq:history_vp_rule}
    \mathbf{V} \prec \mathbf{P} \textrm{ or } \mathbf{P} \rightarrow \mathbf{V}$$

Third, the model assumes that the public can be informed about a
vulnerability by a public exploit. Therefore, either Public Awareness
precedes Exploit Public ($\mathbf{X}$) or must immediately follow it.

$$\label{eq:history_px_rule}
    \mathbf{P} \prec \mathbf{X} \textrm{ or } \mathbf{X} \rightarrow \mathbf{P}$$

This model is amenable for analysis of [CVD]{acronym-label="CVD"
acronym-form="singular+short"}, but we need to add a way to express
preferences before it is complete. Thus we are part way through **RQ1**.
§[6.2](#sec:mpcvd){reference-type="ref" reference="sec:mpcvd"} will
address how this model can generalize from [CVD]{acronym-label="CVD"
acronym-form="singular+short"} to [MPCVD]{acronym-label="MPCVD"
acronym-form="singular+short"}.

## On the Desirability of Possible Histories {#sec:desirability}

All histories are not equally preferable. Some are quite badfor example,
those in which attacks precede vendor awareness
($\mathbf{A} \prec \mathbf{V}$). Others are very desirablefor example,
those in which fixes are deployed before either an exploit is made
public ($\mathbf{D} \prec \mathbf{X}$) or attacks occur
($\mathbf{D} \prec \mathbf{A}$).

In pursuit of a way to reason about our preferences for some histories
over others, we define the following preference criteria: history $h_a$
is preferred over history $h_b$ if, all else being equal, a more
desirable event $\sigma_1$ precedes a less desirable event $\sigma_2$.
This preference is denoted as $\sigma_1 \prec \sigma_2$. We define the
following ordering preferences:

-   $\mathbf{V} \prec \mathbf{P}$, $\mathbf{V} \prec \mathbf{X}$, or
    $\mathbf{V} \prec \mathbf{A}$---Vendors can take no action to
    produce a fix if they are unaware of the vulnerability. Public
    awareness prior to vendor awareness can cause increased support
    costs for vendors at the same time they are experiencing increased
    pressure to prepare a fix. If public awareness of the vulnerability
    prior to vendor awareness is bad, then a public exploit is at least
    as bad because it encompasses the former and makes it readily
    evident that adversaries have exploit code available for use.
    Attacks prior to vendor awareness represent a complete failure of
    the vulnerability remediation process because they indicate that
    adversaries are far ahead of defenders.

-   $\mathbf{F} \prec \mathbf{P}$, $\mathbf{F} \prec \mathbf{X}$, or
    $\mathbf{F} \prec \mathbf{A}$---As noted above, the public can take
    no action until a fix is ready. Because public awareness also
    implies adversary awareness, the vendor/adversary race becomes even
    more critical if this condition is not met. When fixes exist before
    exploits or attacks, defenders are better able to protect their
    users.

-   $\mathbf{D} \prec \mathbf{P}$, $\mathbf{D} \prec \mathbf{X}$, or
    $\mathbf{D} \prec \mathbf{A}$---Even better than vendor awareness
    and fix availability prior to public awareness, exploit publication
    or attacks are scenarios in which fixes are deployed prior to one or
    more of those transitions.

-   $\mathbf{P} \prec \mathbf{X}$ or $\mathbf{P} \prec \mathbf{A}$---In
    many cases, fix deployment ($\mathbf{D}$) requires system owners to
    take action, which implies a need for public awareness of the
    vulnerability. We therefore prefer histories in which public
    awareness happens prior to either exploit publication or attacks.

-   $\mathbf{X} \prec \mathbf{A}$---This criteria is not about whether
    exploits should be published or not.[^3] It is about whether we
    should prefer histories in which exploits are published *before*
    attacks happen over histories in which exploits are published
    *after* attacks happen. Our position is that attackers have more
    advantages in the latter case than the former, and therefore we
    should prefer histories in which $\mathbf{X} \prec \mathbf{A}$.

Equation [\[eq:desiderata\]](#eq:desiderata){reference-type="ref"
reference="eq:desiderata"} formalizes our definition of desired
orderings $\mathbb{D}$. Table
[3.3](#tab:ordered_pairs){reference-type="ref"
reference="tab:ordered_pairs"} displays all 36 possible orderings of
paired transitions and whether they are considered impossible, required
(as defined by
[\[eq:history_vfd_rule\]](#eq:history_vfd_rule){reference-type="eqref"
reference="eq:history_vfd_rule"},
[\[eq:history_vp_rule\]](#eq:history_vp_rule){reference-type="eqref"
reference="eq:history_vp_rule"}, and
[\[eq:history_px_rule\]](#eq:history_px_rule){reference-type="eqref"
reference="eq:history_px_rule"}), desirable (as defined by
[\[eq:desiderata\]](#eq:desiderata){reference-type="eqref"
reference="eq:desiderata"}), or undesirable (the complement of the set
defined in [\[eq:desiderata\]](#eq:desiderata){reference-type="eqref"
reference="eq:desiderata"}).

Before proceeding, we note that our model focuses on the ordering of
transitions, not their timing. We acknowledge that in some situations,
the interval between transitions may be of more interest than merely the
order of those transitions, as a rapid tempo of transitions can alter
the options available to stakeholders in their response. We discuss this
limitation further in §[8](#sec:limitationsAnd){reference-type="ref"
reference="sec:limitationsAnd"}; however, the following model posits
event sequence timing on a human-oriented timescale measured in minutes
to weeks.

$$\label{eq:desiderata}
\begin{split}
 \mathbb{D} \stackrel{\mathsf{def}}{=}\{
\mathbf{V} \prec \mathbf{P}, \mathbf{V} \prec \mathbf{X}, \mathbf{V} \prec \mathbf{A},\\
\mathbf{F} \prec \mathbf{P}, \mathbf{F} \prec \mathbf{X}, \mathbf{F} \prec \mathbf{A},\\
\mathbf{D} \prec \mathbf{P}, \mathbf{D} \prec \mathbf{X}, \mathbf{D} \prec \mathbf{A},\\
\mathbf{P} \prec \mathbf{X}, \mathbf{P} \prec \mathbf{A}, \mathbf{X} \prec \mathbf{A} \}
\end{split}$$ An element $d \in \mathbb{D}$ is of the form
$\sigma_i \prec \sigma_j$. More formally, $d$ is a relation of the form
$d\left(\sigma_1, \sigma_2, \prec \right)$. $\mathbb{D}$ is a set of
such relations.

##### Some states are preferable to others {#sec:state_preference}

The desiderata in
[\[eq:desiderata\]](#eq:desiderata){reference-type="eqref"
reference="eq:desiderata"} address the preferred ordering of transitions
in [CVD]{acronym-label="CVD" acronym-form="singular+short"} histories,
which imply that one should prefer to pass through some states and avoid
others. For example, $\mathbf{V} \prec \mathbf{P}$ implies that we
prefer the paths
${vp} \xrightarrow{\mathbf{V}} {Vp} \xrightarrow{\mathbf{P}} {VP}$ over
the paths
${vp} \xrightarrow{\mathbf{P}} {vP} \xrightarrow{\mathbf{V}} {VP}$. In
Table [3.2](#tab:desired_states){reference-type="ref"
reference="tab:desired_states"} we adapt those desiderata into specific
subsets of states that should be preferred or avoided if the criteria is
to be met.

::: {#tab:desired_states}
      Event Precedence ($d$)       State Subsets to Prefer   State Subsets to Avoid
  ------------------------------- ------------------------- ------------------------
   $\mathbf{V} \prec \mathbf{X}$           ${Vx}$                    ${vX}$
   $\mathbf{V} \prec \mathbf{A}$           ${Va}$                    ${vA}$
   $\mathbf{V} \prec \mathbf{P}$           ${Vp}$                    ${vP}$
   $\mathbf{P} \prec \mathbf{X}$           ${Px}$                    ${pX}$
   $\mathbf{F} \prec \mathbf{X}$           ${VFx}$                  ${fdX}$
   $\mathbf{P} \prec \mathbf{A}$           ${Pa}$                    ${pA}$
   $\mathbf{F} \prec \mathbf{A}$           ${VFa}$                  ${fdA}$
   $\mathbf{F} \prec \mathbf{P}$           ${VFp}$                  ${fdP}$
   $\mathbf{D} \prec \mathbf{X}$          ${VFDx}$                   ${dX}$
   $\mathbf{X} \prec \mathbf{A}$           ${Xa}$                    ${xA}$
   $\mathbf{D} \prec \mathbf{A}$          ${VFDa}$                   ${dA}$
   $\mathbf{D} \prec \mathbf{P}$          ${VFDp}$                   ${dP}$

  : Desired event precedence mapped to subsets of states
:::

##### A partial order over possible histories

Given the desired preferences over orderings of transitions
($\mathbb{D}$ in
[\[eq:desiderata\]](#eq:desiderata){reference-type="eqref"
reference="eq:desiderata"}), we can construct a partial ordering over
all possible histories $\mathcal{H}$, as defined in
[\[eq:ordering\]](#eq:ordering){reference-type="eqref"
reference="eq:ordering"}. This partial order requires a formal
definition of which desiderata are met by a given history, provided by
[\[eq:desiderata_h\]](#eq:desiderata_h){reference-type="eqref"
reference="eq:desiderata_h"}. $$\label{eq:desiderata_h}
\setlength{\jot}{-1pt} % decrease vertical line spacing inside the following split.
\begin{split}
    \mathbb{D}^{h} \stackrel{\mathsf{def}}{=}\{ d \in \mathbb{D} \textrm{ such that } d \textrm{ is true for } h \} \textrm{, for } h \in \mathcal{H} \\
    \textrm{where } d\left(\sigma_1,\sigma_2,\prec\right) \textrm{ is true for } h \textrm{ if and only if: } \\
    \exists \sigma_i, \sigma_j \in h \textrm{ such that } \sigma_i = \sigma_1 \textrm{ and } \sigma_j = \sigma_2 \textrm{ and } h \textrm{ satisfies the relation } d\left(\sigma_i,\sigma_j,\prec\right)
\end{split}$$

$$\label{eq:ordering}
%    \textrm{The pre-order relation } > \textrm{ is defined over } H \textrm{ as:} \\
   (\mathcal{H},\leq_{H}) \stackrel{\mathsf{def}}{=}\forall h_a, h_b \in \mathcal{H} \textrm{ it is the case that } h_b \leq_{H} h_a \textrm{ if and only if } \mathbb{D}^{h_b} \subseteq \mathbb{D}^{h_a}$$

A visualization of the resulting partially ordered set, or poset,
$(\mathcal{H},\leq_{H})$ is shown as a Hasse Diagram in Figure
[3.1](#fig:poset){reference-type="ref" reference="fig:poset"}. Hasse
Diagrams represent the transitive reduction of a poset. Each node in the
diagram represents an individual history $h_a$ from
Table [3.1](#tab:possible_histories){reference-type="ref"
reference="tab:possible_histories"}; labels correspond to the index of
the table. Figure [3.1](#fig:poset){reference-type="ref"
reference="fig:poset"} follows
[\[eq:ordering\]](#eq:ordering){reference-type="eqref"
reference="eq:ordering"}, in that $h_a$ is higher in the order than
$h_b$ when $h_a$ contains all the desiderata from $h_b$ and at least one
more. Histories that do not share a path are incomparable (formally, two
histories incomparable if both
$\mathbb{D}^{h_a} \not\supset \mathbb{D}^{h_b}$ and
$\mathbb{D}^{h_a} \not\subset \mathbb{D}^{h_b}$). The diagram flows from
least desirable histories at the bottom to most desirable at the top.
This model satisfies **RQ1**; §[4](#sec:reasoning){reference-type="ref"
reference="sec:reasoning"} and
§[5](#sec:skill_luck){reference-type="ref" reference="sec:skill_luck"}
will demonstrate that the model is amenable to analysis and
§[6.2.2](#sec:mpcvd criteria){reference-type="ref"
reference="sec:mpcvd criteria"} will lay out the criteria for extending
it to cover [MPCVD]{acronym-label="MPCVD"
acronym-form="singular+short"}.

The poset $(\mathcal{H},\leq_{H})$, has as its upper bound
$$h_{69} = (\mathbf{V}, \mathbf{F}, \mathbf{D}, \mathbf{P}, \mathbf{X}, \mathbf{A})$$
while its lower bound is
$$h_{0} = (\mathbf{A}, \mathbf{X}, \mathbf{P}, \mathbf{V}, \mathbf{F}, \mathbf{D}).$$

::: {#tab:ordered_pairs}
                  $\mathbf{V}$   $\mathbf{F}$   $\mathbf{D}$   $\mathbf{P}$   $\mathbf{X}$   $\mathbf{A}$
  -------------- -------------- -------------- -------------- -------------- -------------- --------------
   $\mathbf{V}$        \-             r              r              d              d              d
   $\mathbf{F}$        \-             \-             r              d              d              d
   $\mathbf{D}$        \-             \-             \-             d              d              d
   $\mathbf{P}$        u              u              u              \-             d              d
   $\mathbf{X}$        u              u              u              u              \-             d
   $\mathbf{A}$        u              u              u              u              u              \-

  : Ordered pairs of events where ${row} \prec {col}$ (Key: - =
  impossible, r = required, d = desired, u = undesired)
:::

Thus far, we have made no assertions about the relative desirability of
any two desiderata (that is, $d_i,d_j \in \mathbb{D}$ where $i \neq j$).
In the next section we will expand the model to include a partial order
over our desiderata, but for now it is sufficient to note that any
simple ordering over $\mathbb{D}$ would remain compatible with the
partial order given in
[\[eq:ordering\]](#eq:ordering){reference-type="eqref"
reference="eq:ordering"}. In fact, a total order on $\mathbb{D}$ would
create a linear extension of the poset defined here, whereas a partial
order on $\mathbb{D}$ would result in a more constrained poset of which
this poset would be a subset.

![The Lattice of Possible [CVD]{acronym-label="CVD"
acronym-form="singular+short"} Histories: A Hasse Diagram of the partial
ordering $(\mathcal{H}, \leq_{H})$ of $h_a \in \mathcal{H}$ given
$\mathbb{D}$ as defined in
[\[eq:ordering\]](#eq:ordering){reference-type="eqref"
reference="eq:ordering"}. The diagram flows from least desirable
histories at the bottom to most desirable at the top. Histories that do
not share a path are incomparable. Labels indicate the index (row
number) $a$ of $h_a$ in Table
[3.1](#tab:possible_histories){reference-type="ref"
reference="tab:possible_histories"}.](figures/h_poset.png){#fig:poset
width="140mm"}

## A Random Walk through CVD States {#sec:random_walk}

To begin to differentiate skill from chance in the next few sections, we
need a model of what the CVD world would look like without any skill. We
cannot derive this model by observation. Even when CVD was first
practiced in the 1980s, some people may have had social, technical, or
organizational skills that transferred to better CVD. We follow the
principle of indifference, as stated in [@pittphilsci16041]:

> **Principle of Indifference:** Let $X = \{x_1,x_2,...,x_n\}$ be a
> partition of the set $W$ of possible worlds into $n$ mutually
> exclusive and jointly exhaustive possibilities. In the absence of any
> relevant evidence pertaining to which cell of the partition is the
> true one, a rational agent should assign an equal initial credence of
> $n$ to each cell.

While the principle of indifference is rather strong, it is inherently
difficult to reason about absolutely skill-less
[CVD]{acronym-label="CVD" acronym-form="singular+short"} when the work
of [CVD]{acronym-label="CVD" acronym-form="singular+short"} is, by its
nature, a skilled job. Given the set of states and allowable transitions
between them, we can apply the principle of indifference to define a
baseline against which measurement can be meaningful.

##### Estimating State Transition Probabilities

Our assumption is that *transitions* are equally probable, not that
*states* or *histories* are. The events $\sigma \in \Sigma$ trigger
state transitions according to $\delta$ and the histories
$h \in \mathcal{H}$ are paths (traces) through the states. This meets
the definition above because each $\sigma \in \Sigma$ is unique
(mutually exclusive) and $\delta$ defines an exhaustive set of valid
$\sigma$ at each state $q \in \mathcal{Q}$. For example, because
[\[eq:history_vfd_rule\]](#eq:history_vfd_rule){reference-type="eqref"
reference="eq:history_vfd_rule"} requires $\mathbf{V} \prec \mathbf{F}$
and $\mathbf{F} \prec \mathbf{D}$, only four of the six events in
$\Sigma$ are possible at the beginning of each history at $q_0=vfdpxa$:
$\{\mathbf{V},\mathbf{P},\mathbf{X},\mathbf{A}\}$. Since the principle
of indifference assigns each possible transition event as equally
probable in this model of unskilled CVD, we assign an initial
probability of 0.25 to each possible event. $$\begin{aligned}
    p(\mathbf{V}|q_0) = p(\mathbf{P}|q_0) = p(\mathbf{X}|q_0) = p(\mathbf{A}|q_0) &= 0.25\\
    p(\mathbf{F}|q_0) = p(\mathbf{D}|q_0) &= 0
\end{aligned}$$

From there, we see that the other rules dictate possible transitions
from each subsequent state. For example,
[\[eq:history_vp_rule\]](#eq:history_vp_rule){reference-type="eqref"
reference="eq:history_vp_rule"} says that any $h$ starting with
$(\mathbf{P})$ must start with $(\mathbf{P},\mathbf{V})$. And
[\[eq:history_px_rule\]](#eq:history_px_rule){reference-type="eqref"
reference="eq:history_px_rule"} requires any $h$ starting with
$(\mathbf{X})$ must proceed through $(\mathbf{X},\mathbf{P})$ and again
[\[eq:history_vp_rule\]](#eq:history_vp_rule){reference-type="eqref"
reference="eq:history_vp_rule"} gets us to
$(\mathbf{X},\mathbf{P},\mathbf{V})$. Therefore, we expect histories
starting with $(\mathbf{P},\mathbf{V})$ or
$(\mathbf{X},\mathbf{P},\mathbf{V})$ to occur with frequency 0.25 as
well. We can use these transition probabilities to estimate a neutral
baseline expectation of which states would be common if we weren't doing
anything special to coordinate vulnerability disclosures. Specifically,
for each state we set the transition probability to any other state
proportional to the inverse of the outdegree of the state, as shown in
the $p(transition)$ column of Table
[3.4](#tab:allowed_state_transitions){reference-type="ref"
reference="tab:allowed_state_transitions"}. Real world data is unlikely
to ever reflect such a sad state of affairs (because
[CVD]{acronym-label="CVD" acronym-form="singular+short"} *is* happening
after all).

::: {#tab:allowed_state_transitions}
   Start State  Next State(s)                             $p({transition})$   PageRank
  ------------- ---------------------------------------- ------------------- ----------
    $vfdpxa$    $vfdpxA$, $vfdpXa$, $vfdPxa$, $Vfdpxa$          0.250          0.123
    $vfdpxA$    $vfdpXA$, $vfdPxA$, $VfdpxA$                    0.333          0.031
    $vfdpXa$    $vfdPXa$                                        1.000          0.031
    $vfdpXA$    $vfdPXA$                                        1.000          0.013
    $vfdPxa$    $VfdPxa$                                        1.000          0.031
    $vfdPxA$    $VfdPxA$                                        1.000          0.013
    $vfdPXa$    $VfdPXa$                                        1.000          0.031
    $vfdPXA$    $VfdPXA$                                        1.000          0.016
    $Vfdpxa$    $VfdpxA$, $VfdpXa$, $VfdPxa$, $VFdpxa$          0.250          0.031
    $VfdpxA$    $VfdpXA$, $VfdPxA$, $VFdpxA$                    0.333          0.020
    $VfdpXa$    $VfdPXa$                                        1.000          0.011
    $VfdpXA$    $VfdPXA$                                        1.000          0.010
    $VfdPxa$    $VfdPxA$, $VfdPXa$, $VFdPxa$                    0.333          0.037
    $VfdPxA$    $VfdPXA$, $VFdPxA$                              0.500          0.032
    $VfdPXa$    $VfdPXA$, $VFdPXa$                              0.500          0.051
    $VfdPXA$    $VFdPXA$                                        1.000          0.063
    $VFdpxa$    $VFdpxA$, $VFdpXa$, $VFdPxa$, $VFDpxa$          0.250          0.011
    $VFdpxA$    $VFdpXA$, $VFdPxA$, $VFDpxA$                    0.333          0.013
    $VFdpXa$    $VFdPXa$                                        1.000          0.007
    $VFdpXA$    $VFdPXA$                                        1.000          0.008
    $VFdPxa$    $VFdPxA$, $VFdPXa$, $VFDPxa$                    0.333          0.018
    $VFdPxA$    $VFdPXA$, $VFDPxA$                              0.500          0.027
    $VFdPXa$    $VFdPXA$, $VFDPXa$                              0.500          0.037
    $VFdPXA$    $VFDPXA$                                        1.000          0.092
    $VFDpxa$    $VFDpxA$, $VFDpXa$, $VFDPxa$                    0.333          0.007
    $VFDpxA$    $VFDpXA$, $VFDPxA$                              0.500          0.010
    $VFDpXa$    $VFDPXa$                                        1.000          0.007
    $VFDpXA$    $VFDPXA$                                        1.000          0.009
    $VFDPxa$    $VFDPxA$, $VFDPXa$                              0.500          0.012
    $VFDPxA$    $VFDPXA$                                        1.000          0.026
    $VFDPXa$    $VFDPXA$                                        1.000          0.031
    $VFDPXA$    $\emptyset$                                     0.000          0.139

  : Sparse state transition matrix and state PageRank assuming
  equiprobable transitions in a random walk over $\mathcal{S}$ as shown
  Figure [2.4](#fig:vfdpxa_map){reference-type="ref"
  reference="fig:vfdpxa_map"}.)
:::

##### Using PageRank to Estimate Baseline State Probabilities

We use the PageRank algorithm to provide state probability estimates.
The PageRank algorithm provides a probability estimate for each state
based on a Markov random walk of the directed graph of states
[@page1999pagerank]. PageRank assumes each available transition is
equally probable, consistent with our model. To avoid becoming stuck in
dead ends, PageRank adds a *teleport* feature by which walks can, with a
small probability, randomly jump to another node in the graph.

Before proceeding, we need to make a small modification of our state
digraph. Without modification, the PageRank algorithm will tend to be
biased toward later states because the only way to reach the earlier
states is for the algorithm to teleport there. Teleportation chooses
states uniformly, so for example there is only a $1/32$ chance of our
actual start state ($q_0={vfdpxa}$) ever being chosen. Therefore, to
ensure that the early states in our process are fairly represented we
add a single link from ${VFDPXA}$ to ${vfdpxa}$, representing a model
reset whenever the end state is reached. This modification allows
PageRank traversals to wrap around naturally and reach the early states
in the random walk process without needing to rely on teleportation.
With our modification in place, we are ready to compute the PageRank of
each node in the graph. Results are shown in Table
[3.4](#tab:allowed_state_transitions){reference-type="ref"
reference="tab:allowed_state_transitions"}

# Reasoning over Possible Histories {#sec:reasoning}

Our goal in this section is to formulate a way to rank our
undifferentiated desiderata $\mathbb{D}$ from
§[3.2](#sec:desirability){reference-type="ref"
reference="sec:desirability"} in order to develop the concept of CVD
skill and its measurement in §[5](#sec:skill_luck){reference-type="ref"
reference="sec:skill_luck"}. This will provide a baseline expectation
about events (**RQ2)**.

## History Frequency Analysis {#sec:history_frequency_analysis}

As described in §[3.3](#sec:random_walk){reference-type="ref"
reference="sec:random_walk"}, we apply the principle of indifference to
the available transition events $\sigma_{i+1}$ at each state $q$ for
each of the possible histories to compute the expected frequency of each
history, which we denote as $f_h$. The frequency of a history $f_h$ is
the cumulative product of the probability $p$ of each event $\sigma_i$
in the history $h$. We are only concerned with histories that meet our
sequence constraints, namely $h \in \mathcal{H}$.

$$\label{eq:history_freq}
    f_h = \prod_{i=0}^{5} p(\sigma_{i+1}|h_i) %\textrm{ where } \sigma_i \in h \textrm{ and } h \in H$$

Table [3.1](#tab:possible_histories){reference-type="ref"
reference="tab:possible_histories"} displays the value of $f_h$ for each
history. Having an expected frequency ($f_h$) for each history $h$ will
allow us to examine how often we might expect our desiderata
$d \in \mathbb{D}$ to occur across $\mathcal{H}$.

Choosing uniformly over event transitions is more useful than treating
the six-element histories as uniformly distributed. For example,
$\mathbf{P} \prec \mathbf{A}$ in 59% of valid histories, but when
histories are weighted by the assumption of uniform state transitions
$\mathbf{P} \prec \mathbf{A}$ is expected to occur in 67% of the time.
These differences arise due to the dependencies between some states.
Since [CVD]{acronym-label="CVD" acronym-form="singular+short"} practice
is comprised of a sequence of events, each informed by the last, our
uniform distribution over events is more likely a useful baseline than a
uniform distribution over histories.

## Event Order Frequency Analysis {#sec:ordering_frequency_analysis}

Each of the event pair orderings in Table
[3.3](#tab:ordered_pairs){reference-type="ref"
reference="tab:ordered_pairs"} can be treated as a Boolean condition
that either holds or does not hold in any given history. In
§[4.1](#sec:history_frequency_analysis){reference-type="ref"
reference="sec:history_frequency_analysis"} we described how to compute
the expected frequency of each history ($f_h$) given the presumption of
indifference to possible events at each step. We can use $f_h$ as a
weighting factor to compute the expected frequency of event orderings
($\sigma_i \prec \sigma_j$) across all possible histories $H$. Equations
[\[eq:h_ord\]](#eq:h_ord){reference-type="ref" reference="eq:h_ord"} and
[\[eq:d_freq\]](#eq:d_freq){reference-type="ref" reference="eq:d_freq"}
define the frequency of an ordering $f_{\sigma_i \prec \sigma_j}$ as the
sum over all histories in which the ordering occurs
($H^{\sigma_i \prec \sigma_j}$) of the frequency of each such history
($f_h$) as shown in Table
[3.1](#tab:possible_histories){reference-type="ref"
reference="tab:possible_histories"}.

$$\label{eq:h_ord}
    H^{\sigma_i \prec \sigma_j} \stackrel{\mathsf{def}}{=}\{h \in H \textrm{ where } \sigma_i \prec \sigma_j \textrm{ is true for } h \textrm{ and } i \neq j\}$$

$$\label{eq:d_freq}
    f_{\sigma_i \prec \sigma_j} \stackrel{\mathsf{def}}{=}\sum_{h \in H^{\sigma_i \prec \sigma_j}} {f_h}$$

::: {#tab:event_freq}
                   $\mathbf{V}$   $\mathbf{F}$   $\mathbf{D}$   $\mathbf{P}$   $\mathbf{X}$   $\mathbf{A}$
  -------------- -------------- -------------- -------------- -------------- -------------- --------------
  $\mathbf{V}$                0              1              1          0.333          0.667          0.750
  $\mathbf{F}$                0              0              1          0.111          0.333          0.375
  $\mathbf{D}$                0              0              0          0.037          0.167          0.187
  $\mathbf{P}$            0.667          0.889          0.963              0          0.500          0.667
  $\mathbf{X}$            0.333          0.667          0.833          0.500              0          0.500
  $\mathbf{A}$            0.250          0.625          0.812          0.333          0.500              0

  : Expected Frequency of ${row} \prec {col}$ when events are chosen
  uniformly from possible transitions in each state
:::

Table [4.1](#tab:event_freq){reference-type="ref"
reference="tab:event_freq"} displays the results of this calculation.
Required event orderings have an expected frequency of 1, while
impossible orderings have an expected frequency of 0. As defined in
§[3.2](#sec:desirability){reference-type="ref"
reference="sec:desirability"}, each desiderata $d \in \mathbb{D}$ is
specified as an event ordering of the form $\sigma_i \prec \sigma_j$. We
use $f_d$ to denote the expected frequency of a given desiderata
$d \in \mathbb{D}$. The values for the relevant $f_d$ appear in the
upper right of Table [4.1](#tab:event_freq){reference-type="ref"
reference="tab:event_freq"}. Some event orderings have higher expected
frequencies than others. For example, vendor awareness precedes attacks
in 3 out of 4 histories in a uniform distribution of event transitions
($f_{\mathbf{V} \prec \mathbf{A}} = 0.75$), whereas fix deployed prior
to public awareness holds in less than 1 out of 25
($f_{\mathbf{D} \prec \mathbf{P}} = 0.037$) histories generated by a
uniform distribution over event transitions.

## A Partial Order on Desiderata {#desirability}

Any observations of phenomena in which we measure the performance of
human actors can attribute some portion of the outcome to skill and some
portion to chance [@larkey1997skill; @dreef2004measuring]. It is
reasonable to wonder whether good outcomes in [CVD]{acronym-label="CVD"
acronym-form="singular+short"} are the result of luck or skill. How can
we tell the difference?

We begin with a simple model in which outcomes are a combination of luck
and skill.

$$o_{observed} = o_{luck} + o_{skill}$$

In other words, outcomes due to skill are what remains when you subtract
the outcomes due to luck from the outcomes you observe. In this model,
we treat *luck* as a random component: the contribution of chance. In a
world where neither attackers nor defenders held any advantage and
events were chosen uniformly from $\Sigma$ whenever they were possible,
we would expect to see the preferred orderings occur with probability
equivalent to their frequency $f_d$ as shown in Table
[4.1](#tab:event_freq){reference-type="ref" reference="tab:event_freq"}.

Skill, on the other hand, accounts for the outcomes once luck has been
accounted for. So the more likely an outcome is due to luck, the less
skill we can infer when it is observed. As an example, from
Table [4.1](#tab:event_freq){reference-type="ref"
reference="tab:event_freq"} we see that fix deployed before the
vulnerability is public is the rarest of our desiderata with
$f_{\mathbf{D} \prec \mathbf{P}} = 0.037$, and thus exhibits the most
skill when observed. On the other hand, vendor awareness before attacks
is expected to be a common occurrence with
$f_{\mathbf{V} \prec \mathbf{A}} = 0.75$.

We can therefore use the set of $f_d$ to construct a partial order over
$\mathbb{D}$ in which we prefer desiderata $d$ which are more rare (and
therefore imply more skill when observed) over those that are more
common. We create the partial order on $\mathbb{D}$ as follows: for any
pair $d_1,d_2 \in \mathbb{D}$, we say that $d_2$ exhibits less skill
than $d_1$ if $d_2$ occurs more frequently in $\mathcal{H}$ than $d_1$.

$$\label{eq:ordering_d}
(\mathbb{D},\leq_{\mathbb{D}}) \stackrel{\mathsf{def}}{=}d_2 \leq_{\mathbb{D}} d_1 \iff {f_{d_2}} \stackrel{\mathbb{R}}{\geq} {f_{d_1}}$$

Note that the inequalities on the left and right sides of
[\[eq:ordering_d\]](#eq:ordering_d){reference-type="eqref"
reference="eq:ordering_d"} are flipped because skill is inversely
proportional to luck. Also, while $\leq_{\mathbb{D}}$ on the left side
of [\[eq:ordering_d\]](#eq:ordering_d){reference-type="eqref"
reference="eq:ordering_d"} defines a preorder over the poset
$\mathcal{H}$, the $\stackrel{\mathbb{R}}{\geq}$ is the usual ordering
over the set of real numbers. The result is a partial order
$(\mathbb{D},\leq_{\mathbb{D}})$ because a few $d$ have the same $f_d$
($f_{\mathbf{F} \prec \mathbf{X}} = f_{\mathbf{V} \prec \mathbf{P}} = 0.333$
for example). The full Hasse Diagram for the partial order
$(\mathbb{D},\leq_{\mathbb{D}})$ is shown in
Figure [\[fig:d_poset\]](#fig:d_poset){reference-type="ref"
reference="fig:d_poset"}.

## Ordering Possible Histories by Skill {#sec:h_poset_skill}

::: wrapfigure
r0.3
:::

Next we develop a new partial order on $\mathcal{H}$ given the partial
order $(\mathbb{D},\leq_{\mathbb{D}})$ just described. We observe that
$\mathbb{D}^{h}$ acts as a Boolean vector of desiderata met by a given
$h$. Since $0 \leq f_d \leq 1$, simply taking its inverse could in the
general case lead to some large values for rare events. For convenience,
we use $-log(f_d)$ as our proxy for skill. For example, if a desideratum
were found to occur in every case (indicating no skill required),
$f_d=1$ and therefore $-log(1) = 0$. On the other hand, for increasingly
rare desiderata, our skill metric rises:
$\lim_{f_d \to 0} -log(f_d) = +\infty$.

Taking the dot product of $\mathbb{D}^h$ with the set of $-log(f_d)$
values for each $d \in \mathbb{D}$ represented as a vector, we arrive at
a single value representing the skill exhibited for each history $h$.
Careful readers may note that this value is equivalent to the
[TF-IDF]{acronym-label="TF-IDF" acronym-form="singular+short"} score for
a search for the "skill terms" represented by $\mathbb{D}$ across the
corpus of possible histories $\mathcal{H}$.

We have now computed a skill value for every $h \in \mathcal{H}$, which
allows us to sort $\mathcal{H}$ and assign a rank to each history $h$
contained therein. The rank is shown in
Table [3.1](#tab:possible_histories){reference-type="ref"
reference="tab:possible_histories"}. Rank values start at 1 for least
skill up to a maximum of 62 for most skill. Owing to the partial order
$(\mathbb{D},\leq_{\mathbb{D}})$, some $h$ have the same computed skill
values, and these are given the same rank.

The ranks for $h \in \mathcal{H}$ lead directly to a new poset
$(\mathcal{H},\leq_{\mathbb{D}})$. It is an extension of and fully
compatible with $(\mathcal{H},\leq_{H})$ as developed in
§[3.2](#sec:desirability){reference-type="ref"
reference="sec:desirability"}.

The resulting Hasse Diagram would be too large to reproduce here.
Instead, we include the resulting rank for each $h$ as a column in
Table [3.1](#tab:possible_histories){reference-type="ref"
reference="tab:possible_histories"}. In the table, rank is ordered from
least desirable and skillful histories to most. Histories having
identical rank are incomparable to each other within the poset. The
refined poset $(\mathcal{H},\leq_{\mathbb{D}})$ is much closer to a
total order on $\mathcal{H}$, as indicated by the relatively few
histories having duplicate ranks.

The remaining incomparable histories are the direct result of the
incomparable $d$ in $(\mathbb{D},\leq_{\mathbb{D}})$, corresponding to
the branches in Figure
[\[fig:d_poset\]](#fig:d_poset){reference-type="ref"
reference="fig:d_poset"}. Achieving a total order on $\mathbb{D}$ would
require determining a preference for one of each of the following:

-   that fix ready precede exploit publication
    ($\mathbf{F} \prec \mathbf{X}$) or that vendor awareness precede
    public awareness ($\mathbf{V} \prec \mathbf{P}$)

-   that public awareness precede exploit publication
    ($\mathbf{P} \prec \mathbf{X}$) or that exploit publication precede
    attacks ($\mathbf{X} \prec \mathbf{A}$)

-   that public awareness precede attacks
    ($\mathbf{P} \prec \mathbf{A}$) or vendor awareness precede exploit
    publication ($\mathbf{V} \prec \mathbf{X}$)

Recognizing that readers may have diverse opinions on all three items,
we leave further consideration of the answers to these as future work.

This is just one example of how poset refinements might be used to order
$\mathcal{H}$. Different posets on $\mathbb{D}$ would lead to different
posets on $\mathcal{H}$. For example, one might construct a different
poset if certain $d$ were considered to have much higher financial value
when achieved than others.

# Discriminating Skill and Luck in Observations {#sec:skill_luck}

This section defines a method for measuring skillful behavior in
[CVD]{acronym-label="CVD" acronym-form="singular+short"}, which we will
need to answer **RQ3** about measuring and evaluating
[CVD]{acronym-label="CVD" acronym-form="singular+short"} "in the wild."
The measurement method makes use of all the modeling tools and baselines
established thus far: a comprehensive set of possible histories
$\mathcal{H}$, a partial order over them in terms of the presence of
desired event precedence $(\mathcal{H},\leq_{\mathbb{D}})$, and the *a
priori* expected frequency of each desiderata $d \in \mathbb{D}$.

If we expected to be able to observe all events in all
[CVD]{acronym-label="CVD" acronym-form="singular+short"} cases, we could
be assured of having complete histories and could be done here. But the
real world is messy. Not all events $\mathbf{e} \in \mathcal{E}$ are
always observable. We need to develop a way to make sense of what we
*can* observe, regardless of whether we are ever able to capture
complete histories. Continuing towards our goal of measuring efficacy,
we return to considering the balance between skill and luck in
determining our observed outcomes.

## A Measure of Skill in CVD {#sec:skillmodel}

There are many reasons why we might expect our observations to differ
from the expected frequencies we established in
§[4](#sec:reasoning){reference-type="ref" reference="sec:reasoning"}.
Adversaries might be rare, or conversely very well equipped. Vendors
might be very good at releasing fixes faster than adversaries can
discover vulnerabilities and develop exploits for them. System owners
might be diligent at applying patches. (We did say *might*, didn't we?)
Regardless, for now we will lump all of those possible explanations into
a single attribute called "skill."

In a world of pure skill, one would expect that a player could achieve
all 12 desiderata $d \in \mathbb{D}$ consistently. That is, a maximally
skillful player could consistently achieve the specific ordering
$h=(\mathbf{V},\mathbf{F},\mathbf{D},\mathbf{P},\mathbf{X},\mathbf{A})$
with probability $p_{skill} = 1$.

Thus, we construct the following model: for each of our preferred
orderings $d \in \mathbb{D}$, we model their occurrence due to luck
using the binomial distribution with parameter $p_{luck} = f_d$ taken
from Table [4.1](#tab:event_freq){reference-type="ref"
reference="tab:event_freq"}.

Recall that the mean of a binomial distribution is simply the
probability of success $p$, and that the mean of a weighted mixture of
two binomial distributions is simply the weighted mixture of the
individual means. Therefore our model adds a parameter $\alpha_d$ to
represent the weighting between our success rates arising from skill
$p_{skill}$ and luck $p_{luck}$. Because there are 12 desiderata
$d \in \mathbb{D}$, each $d$ will have its own observations and
corresponding value for $\alpha_d$ for each history $h_a$.

$$\label{eq:obs_skill_luck}
    f_d^{obs} = \alpha_d \cdot p_{skill} + (1 - \alpha_d) \cdot p_{luck}$$

Where $f_d^{obs}$ is the observed frequency of successes for desiderata
$d$. Because $p_{skill} = 1$, one of those binomial distributions is
degenerate. Substituting $p_{skill} = 1$, $p_{luck} = f_d$ and solving
Eq. [\[eq:obs_skill_luck\]](#eq:obs_skill_luck){reference-type="ref"
reference="eq:obs_skill_luck"} for $\alpha$, we get

$$\label{eq:alpha_freq}
    \alpha_d \stackrel{\mathsf{def}}{=}\frac{f_d^{obs} - f_d} {1 - f_d}$$

The value of $\alpha_d$ therefore gives us a measure of the observed
skill normalized against the background success rate provided by luck
$f_d$. We denote the set of $\alpha_d$ values for a given history as
$\alpha_\mathbb{D}$. When we refer to the $\alpha_d$ coefficient for a
specific $d$ we will use the specific ordering as the subscript, for
example: $\alpha_{\mathbf{F} \prec \mathbf{P}}$.

$$\alpha_\mathbb{D} \stackrel{\mathsf{def}}{=}\{ \alpha_d : d \in \mathbb{D} \}$$

The concept embodied by $f_d$ is founded on the idea that if attackers
and defenders are in a state of equilibrium, the frequency of observed
outcomes (i.e., how often each desiderata $d$ and history $h$ actually
occurs) will appear consistent with those predicted by chance. So
another way of interpreting $\alpha_d$ is as a measure of the degree to
which a set of observed histories is out of equilibrium.

The following are a few comments on how $\alpha_d$ behaves. Note that
$\alpha_d < 0$ when $0 \leq f_d^{obs} < f_d$ and
$0 \leq \alpha_d \leq 1$ when $f_d \leq f_d^{obs} \leq 1$. The
implication is that a negative value for $\alpha_d$ indicates that our
observed outcomes are actually *worse* than those predicted by pure
luck. In other words, we can only infer positive skill when the
observations are higher ($f_d^{obs} > f_d$). That makes intuitive sense:
if you are likely to win purely by chance, then you have to attribute
most of your wins to luck rather than skill. From Table
[4.1](#tab:event_freq){reference-type="ref" reference="tab:event_freq"},
the largest value for any $d \in \mathbb{D}$ is
$f_{\mathbf{V} \prec \mathbf{A}}=0.75$, implying that even if a vendor
knows about 7 out of 10 vulnerabilities before attacks occur
($f_{\mathbf{V} \prec \mathbf{A}}^{obs} = 0.7$), they are still not
doing better than random.

On the other hand, when $f_d$ is small it is easier to infer skill
should we observe anything better than $f_d$. However, it takes larger
increments of observations $f_d^{obs}$ to infer growth in skill when
$f_d$ is small than when it is large. The smallest $f_d$ we see in Table
[4.1](#tab:event_freq){reference-type="ref" reference="tab:event_freq"}
is $f_{\mathbf{D} \prec \mathbf{P}} = 0.037$.

Inherent to the binomial distribution is the expectation that the
variance of results is lower for both extremes (as $p$ approaches either
0 or 1) and highest at $p=0.5$. Therefore we should generally be less
certain of our observations when they fall in the middle of the
distribution. We address uncertainty further in
§[5.1.2](#sec:uncertainty){reference-type="ref"
reference="sec:uncertainty"}.

### Computing $\alpha_d$ from Observations {#sec:computing_observations}

Although Eq. [\[eq:alpha_freq\]](#eq:alpha_freq){reference-type="eqref"
reference="eq:alpha_freq"} develops a skill metric from observed
frequencies, our observations will in fact be based on counts.
Observations consist of some number of successes $S_d^{obs}$ out of some
number of trials $T$, i.e., $$\label{eq:observed_wins}
    f_d^{obs} = \frac{S_d^{obs}}{T}$$ We likewise revisit our
interpretation of $f_d$. $$\label{eq:lucky_wins}
    f_d = \frac{S_d^{luck}}{T}$$ where $S_d^{luck}$ is the number of
successes at $d$ we would expect due to luck in $T$ trials.

Substituting
[\[eq:observed_wins\]](#eq:observed_wins){reference-type="eqref"
reference="eq:observed_wins"} and
[\[eq:lucky_wins\]](#eq:lucky_wins){reference-type="eqref"
reference="eq:lucky_wins"} into
[\[eq:alpha_freq\]](#eq:alpha_freq){reference-type="eqref"
reference="eq:alpha_freq"}, and recalling that $p_{skill} = 1$ because a
maximally skillful player succeeds in $T$ out of $T$ trials, we get
$$\label{eq:alpha_obs1}
    \alpha_{d} = \frac{\cfrac{S_d^{obs}}{T}-\cfrac{S_d^{luck}}{T}}
    {\cfrac{T}{T}-\cfrac{S_d^l}{T}}$$

Rearranging [\[eq:lucky_wins\]](#eq:lucky_wins){reference-type="eqref"
reference="eq:lucky_wins"} to $S_d^{luck} = {f_d}T$, substituting into
[\[eq:alpha_obs1\]](#eq:alpha_obs1){reference-type="eqref"
reference="eq:alpha_obs1"}, and simplifying, we arrive at:
$$\alpha_{d} = \frac{{S_d^{obs}}-{f_d}T}{(1-{f_d})T}$$ Hence for any of
our desiderata $\mathbb{D}$ we can compute $\alpha_d$ given $S_d^{obs}$
observed successes out of $T$ trials in light of $f_d$ taken from Table
[4.1](#tab:event_freq){reference-type="ref" reference="tab:event_freq"}.

Before we address the data analysis we take a moment to discuss
uncertainty.

### Calculating Measurement Error {#sec:uncertainty}

We have already described the basis of our $f_d^{obs}$ model in the
binomial distribution. While we could just estimate the error in our
observations using the binomial's variance $np(1-p)$, because of
boundary conditions at 0 and 1 we should not assume symmetric error. An
extensive discussion of uncertainty in the binomial distribution is
given in [@brown2001interval].

However, for our purpose the Beta distribution lends itself to this
problem nicely. The Beta distribution is specified by two parameters
$(a,b)$. It is common to interpret $a$ as the number of successes and
$b$ as the number of failures in a set of observations of Bernoulli
trials to estimate the mean of the binomial distribution from which the
observations are drawn. For any given mean, the width of the Beta
distribution narrows as the total number of trials increases.

We use this interpretation to estimate a 95% credible interval for
$f_d^{obs}$ using a Beta distribution with parameters $a = S_d^{obs}$ as
successes and $b = T - S_d^{obs}$ representing the number of failures
using the `scipy.stats.beta.interval` function in Python. This gives us
an upper and lower estimate for $f_d^{obs}$, which we multiply by $T$ to
get upper and lower estimates of $S_d^{obs}$ as in
[\[eq:observed_wins\]](#eq:observed_wins){reference-type="eqref"
reference="eq:observed_wins"}.

## Observing CVD in the Wild {#sec:observation}

As a proof of concept, we apply the model to two data sets: Microsoft's
security updates from 2017 through early 2020 in
§[5.2.1](#sec:ms2017-20){reference-type="ref"
reference="sec:ms2017-20"}, and commodity public exploits from 2015-2019
in §[5.2.2](#sec:commodity_15_19){reference-type="ref"
reference="sec:commodity_15_19"}.

### Microsoft 2017-2020 {#sec:ms2017-20}

We are now ready to proceed with our data analysis. First, we examine
Microsoft's monthly security updates for the period between March 2017
and May 2020, as curated by the Zero Day Initiative blog[^4]. Figure
[\[fig:ms_patched\]](#fig:ms_patched){reference-type="ref"
reference="fig:ms_patched"} shows monthly totals for all vulnerabilities
while
[\[fig:ms_observations\]](#fig:ms_observations){reference-type="ref"
reference="fig:ms_observations"} has monthly observations of
$\mathbf{P} \prec \mathbf{F}$ and $\mathbf{A} \prec \mathbf{F}$. This
data set allowed us to compute the monthly counts for two of our
desiderata, $\mathbf{F} \prec \mathbf{P}$ and
$\mathbf{F} \prec \mathbf{A}$.

<figure>

<figcaption>Publicly Disclosed Microsoft Vulnerabilities
2017-2020</figcaption>
</figure>

*Observations of $\mathbf{F} \prec \mathbf{P}$:* In total, Microsoft
issued patches for 2,694 vulnerabilities; 2,610 (0.97) of them met the
fix-ready-before-public-awareness ($\mathbf{F} \prec \mathbf{P}$)
objective. The mean monthly
$\alpha_{\mathbf{F} \prec \mathbf{P}} = 0.967$, with a range of \[0.878,
1.0\]. We can also use the cumulative data to estimate an overall skill
level for the observation period, which gives us a bit more precision on
$\alpha_{\mathbf{F} \prec \mathbf{P}} = 0.969$ with the 0.95 interval of
\[0.962, 0.975\]. Figure
[\[fig:ms_fapa\]](#fig:ms_fapa){reference-type="ref"
reference="fig:ms_fapa"} shows the trend for both the monthly
observations and the cumulative estimate of
$\alpha_{\mathbf{F} \prec \mathbf{P}}$.

<figure>

<figcaption>Selected Skill Measurement for Publicly Disclosed Microsoft
Vulnerabilities 2017-2020</figcaption>
</figure>

*Observations of $\mathbf{F} \prec \mathbf{A}$:* Meanwhile, 2,655 (0.99)
vulnerabilities met the fix-ready-before-attacks-observed
($\mathbf{F} \prec \mathbf{A}$) criteria. Thus we compute a mean monthly
$\alpha_{\mathbf{F} \prec \mathbf{A}} = 0.976$ with range \[0.893,
1.0\]. The cumulative estimate yields
$\alpha_{\mathbf{F} \prec \mathbf{A}} = 0.986$ with an interval of
\[0.980, 0.989\]. The trend for both is shown in Figure
[\[fig:ms_faat\]](#fig:ms_faat){reference-type="ref"
reference="fig:ms_faat"}.

*Inferring Histories from Observations:* []{#sec:inferring_history
label="sec:inferring_history"} Another possible application of our model
is to estimate unobserved $\alpha_d$ based on the cumulative
observations of both $f_{\mathbf{F} \prec \mathbf{P}}^{obs}$ and
$f_{\mathbf{F} \prec \mathbf{A}}^{obs}$ above. Here we estimate the
frequency $f_d$ of the other $d \in \mathbb{D}$ for this period. Our
procedure is as follows:

1.  For 10000 rounds, draw an $f_d^{est}$ for both
    $\mathbf{F} \prec \mathbf{P}$ and $\mathbf{F} \prec \mathbf{A}$ from
    the Beta distribution with parameters $a=S_d^{obs}$ and
    $b=T-S_d^{obs}$ where $S_d^{obs}$ is 2,610 or 2,655, respectively,
    and $T$ is 2,694.

2.  Assign each $h \in \mathcal{H}$ a weight according to standard joint
    probability based whether it meets both, either, or neither
    $A = \mathbf{F} \prec \mathbf{P}$ and
    $B = \mathbf{F} \prec \mathbf{A}$, respectively.

    $$w_h = 
    \begin{cases}
    p_{AB} = f_A * f_B \textrm{ if } A \textrm{ and } B\\
    p_{Ab} = f_A * f_b \textrm{ if } A \textrm{ and } \lnot B\\
    p_{aB} = f_a * f_B \textrm{ if } \lnot A \textrm{ and } B\\
    p_{ab} = f_a * f_b \textrm{ if } \lnot A \textrm{ and } \lnot B
    \end{cases}$$ where $f_a = 1 - f_A$ and $f_b = 1-f_B$

3.  Draw a weighted sample (with replacement) of size $N = 2,694$ from
    $\mathcal{H}$ according to these weights.

4.  Compute the sample frequency $f_{d}^{sample} = S_d^{sample} / N$ for
    each $d \in \mathbb{D}$, and record the median rank of all histories
    $h$ in the sample.

5.  Compute the estimated frequency as the mean of the sample
    frequencies, namely $f_{d}^{est} = \langle f_{d}^{sample} \rangle$,
    for each $d \in \mathbb{D}$.

6.  Compute $\alpha_d$ from $f_{d}^{est}$ for each $d \in \mathbb{D}$ .

As one might expect given the causal requirement that vendor awareness
precedes fix availability, the estimated values of $\alpha_d$ are quite
high ($0.96-0.99$) for our desiderata involving either $\mathbf{V}$ or
$\mathbf{F}$. We also estimate that $\alpha_d$ is positive---indicating
that we are observing skill over and above mere luck---for all $d$
except $\mathbf{P} \prec \mathbf{A}$ and $\mathbf{X} \prec \mathbf{A}$
which are slightly negative. The results are shown in Figure
[5.1](#fig:ms_estimates){reference-type="ref"
reference="fig:ms_estimates"}. The most common sample median history
rank across all runs is 53, with all sample median history ranks falling
between 51-55. The median rank of possible histories weighted according
to the assumption of equiprobable transitions is 11. We take this as
evidence that the observations are indicative of skill.

![Simulated skill $\alpha_d$ for Microsoft 2017-2020 based on
observations of $\mathbf{F} \prec \mathbf{P}$ and
$\mathbf{F} \prec \mathbf{A}$ over the
period.](figures/ms_estimates.png){#fig:ms_estimates width="100mm"}

### Commodity Exploits 2015-2019 {#sec:commodity_15_19}

Next, we examine the overall trend in $\mathbf{P} \prec \mathbf{X}$ for
commodity exploits between 2015 and 2019. The data set is based on the
National Vulnerability Database [@NVD], in conjunction with the CERT
Vulnerability Data Archive [@certvda]. Between these two databases, a
number of candidate dates are available to represent the date a
vulnerability was made public. We use the minimum of these as the date
for $P$.

To estimate the exploit availability ($\mathbf{X}$) date, we extracted
the date a CVE ID appeared in the git logs for Metasploit [@metasploit]
or Exploitdb [@exploitdb]. When multiple dates were available for a CVE
ID, we kept the earliest. Note that commodity exploit tools such as
Metasploit and Exploitdb represent a non-random sample of the exploits
available to adversaries. These observations should be taken as a lower
bounds estimate of exploit availability, and therefore an upper bounds
estimate of observed desiderata $d$ and skill $\alpha_d$.

During the time period from 2013-2019, the data set contains $N=73,474$
vulnerabilities. Of these, 1,186 were observed to have public exploits
($\mathbf{X}$) prior to the earliest observed vulnerability disclosure
date ($\mathbf{P}$), giving an overall success rate for
$\mathbf{P} \prec \mathbf{X}$ of 0.984. The mean monthly
$\alpha_{\mathbf{P} \prec \mathbf{X}}$ is 0.966 with a range of \[0.873,
1.0\]. The volatility of this measurement appears to be higher than that
of the Microsoft data. The cumulative
$\alpha_{\mathbf{P} \prec \mathbf{X}}$ comes in at 0.968 with an
interval spanning \[0.966, 0.970\]. A chart of the trend is shown in
Fig. [5.2](#fig:ov_paea_2013_2019){reference-type="ref"
reference="fig:ov_paea_2013_2019"}.

![$\alpha_{\mathbf{P} \prec \mathbf{X}}$ for all NVD vulnerabilities
2013-2019 ($\mathbf{X}$ observations based on Metasploit and
ExploitDb)](figures/overall_skill_obs_paea.png){#fig:ov_paea_2013_2019
width="100mm"}

To estimate unobserved $\alpha_d$ from the commodity exploit
observations, we repeat the procedure outlined in
§[\[sec:inferring_history\]](#sec:inferring_history){reference-type="ref"
reference="sec:inferring_history"}. This time, we use $N=73,474$ and
estimate $f^{est}_{d}$ for $\mathbf{P} \prec \mathbf{X}$ with Beta
parameters $a=72,288$ and $b=1186$. As above, we find evidence of skill
in positive estimates of $\alpha_d$ for all desiderata except
$\mathbf{P} \prec \mathbf{A}$ and $\mathbf{X} \prec \mathbf{A}$, which
are negative. The most common sample median history rank in this
estimate is 33 with a range of \[32,33\], which while lower than the
median rank of 53 in the Microsoft estimate from
§[5.2.1](#sec:ms2017-20){reference-type="ref"
reference="sec:ms2017-20"}, still beats the median rank of 11 assuming
uniform event probabilities. The results are shown in Figure
[5.3](#fig:nvd_estimates){reference-type="ref"
reference="fig:nvd_estimates"}.

![Simulated skill $\alpha_d$ for all NVD vulnerabilities 2013-2019 based
on observations of $\mathbf{P} \prec \mathbf{X}$ over the
period.](figures/nvd_estimates.png){#fig:nvd_estimates width="100mm"}

# Discussion {#sec:discussion}

The observational analysis in
§[5.2](#sec:observation){reference-type="ref"
reference="sec:observation"} supports an affirmative response to
**RQ3**: vulnerability disclosure as currently practiced demonstrates
skill. In both data sets examined, our estimated $\alpha_d$ is positive
for most $d \in \mathbb{D}$. However, there is uncertainty in our
estimates due to the application of the principle of indifference to
unobserved data. This principle assumes a uniform distribution across
event transitions in the absence of [CVD]{acronym-label="CVD"
acronym-form="singular+short"}, which is an assumption we cannot readily
test. The spread of the estimates in Figures
[5.1](#fig:ms_estimates){reference-type="ref"
reference="fig:ms_estimates"} and
[5.3](#fig:nvd_estimates){reference-type="ref"
reference="fig:nvd_estimates"} represents the variance in our samples,
not this assumption-based uncertainty. Our interpretation of $\alpha_d$
values near zero is therefore that they reflect an absence of evidence
rather than evidence that skill is absent. While we cannot rule
definitively on luck or low skill, values of $\alpha_d > 0.9$ should
reliably indicate skillful defenders.

If, as seems plausible from the evidence, it turns out that further
observations of $h$ are significantly skewed toward the higher end of
the poset $(\mathcal{H},\leq_{\mathbb{D}})$, then it may be useful to
empirically calibrate our metrics rather than using the *a priori*
frequencies in Table [4.1](#tab:event_freq){reference-type="ref"
reference="tab:event_freq"} as our baseline. This analysis baseline
would provide context on "more skillful than the average for some set of
teams" rather than more skillful than blind luck.
§[6.1](#sec:benchmarks){reference-type="ref" reference="sec:benchmarks"}
discusses this topic, which should be viewed as an examination of what
"reasonable" in **RQ2** should mean in the context of "reasonable
baseline expectation."

§[6.2](#sec:mpcvd){reference-type="ref" reference="sec:mpcvd"} suggests
how the model might be applied to establish benchmarks for
[CVD]{acronym-label="CVD" acronym-form="singular+short"} processes
involving any number of participants, which closes the analysis of
**RQ1** in relation to [MPCVD]{acronym-label="MPCVD"
acronym-form="singular+short"}. §[6.3](#sec:roles){reference-type="ref"
reference="sec:roles"} surveys the stakeholders in
[CVD]{acronym-label="CVD" acronym-form="singular+short"} and how they
might use our model; the stakeholders are vendors, system owners, the
security research community, coordinators, and governments. In
particular, we focus on how these stakeholders might respond to the
affirmative answer to **RQ3** and a method to measure skill in a way
more tailored to each stakeholder group.
§[6.4](#sec:policy_formalism){reference-type="ref"
reference="sec:policy_formalism"} discusses the potential for
formalizing disclosure policy specifications using the model.
§[6.5](#sec:defining_common_terms){reference-type="ref"
reference="sec:defining_common_terms"} offers formal definitions of some
common terms in vulnerability disclosure. We then proceed to address
vulnerability response situation awareness in
§[6.6](#sec:situation_awareness){reference-type="ref"
reference="sec:situation_awareness"}, with a brief note about the
[VEP]{acronym-label="VEP" acronym-form="singular+short"} in relation to
this model in §[6.7](#sec:vep){reference-type="ref"
reference="sec:vep"}. Finally, a set of state-based rules for
[CVD]{acronym-label="CVD" acronym-form="singular+short"} actions is
given in §[6.8](#sec:cvd_action_rules){reference-type="ref"
reference="sec:cvd_action_rules"}.

## [CVD]{acronym-label="CVD" acronym-form="singular+short"} Benchmarks {#sec:benchmarks}

As described above, in an ideal [CVD]{acronym-label="CVD"
acronym-form="singular+short"} situation, each observed history would
achieve all 12 desiderata $\mathbb{D}$. Realistically, this is unlikely
to happen. We can at least state that we would prefer that most cases
reach fix ready before attacks ($\mathbf{F} \prec \mathbf{A}$). Per
Table [4.1](#tab:event_freq){reference-type="ref"
reference="tab:event_freq"}, even in a world without skill we would
expect $\mathbf{F} \prec \mathbf{A}$ to hold in 73% of cases. This means
that $\alpha_{\mathbf{F} \prec \mathbf{A}} < 0$ for anything less than a
0.73 success rate. In fact, we propose to generalize this for any
$d \in \mathbb{D}$, such that $\alpha_d$ should be greater than some
benchmark constant $c_d$:

$$\alpha_d \geq c_d \geq 0$$

where $c_d$ is a based on observations of $\alpha_d$ collected across
some collection of [CVD]{acronym-label="CVD"
acronym-form="singular+short"} cases.

We propose as a starting point a naïve benchmark of $c_d = 0$. This is a
low bar, as it only requires that [CVD]{acronym-label="CVD"
acronym-form="singular+short"} actually do better than possible events
which are independent and identically distributed (i.i.d.) within each
case. For example, given a history in which
$(\mathbf{V}, \mathbf{F}, \mathbf{P})$ have already happened (i.e.,
state $q \in VFdPxa$), $\mathbf{D}$, $\mathbf{X}$, or $\mathbf{A}$ are
equally likely to occur next.

The i.i.d. assumption may not be warranted. We anticipate that event
ordering probabilities might be conditional on history: for example,
exploit publication may be more likely when the vulnerability is public
($p(\mathbf{X}|q \in \mathcal{Q}_P) > p(\mathbf{X}|q \in \mathcal{Q}_p)$)
or attacks may be more likely when an exploit is public
($p(\mathbf{A}|q \in \mathcal{Q}_{X}) > p(\mathbf{A}|q \in \mathcal{Q}_{x})$).
If the i.i.d. assumption fails to hold for transition events
$\sigma \in \Sigma$, observed frequencies of $h \in \mathcal{H}$ could
differ significantly from the rates predicted by the uniform probability
assumption behind Table [4.1](#tab:event_freq){reference-type="ref"
reference="tab:event_freq"}.

Some example suggestive observations are:

-   There is reason to suspect that only a fraction of vulnerabilities
    ever reach the *exploit public* event $\mathbf{X}$, and fewer still
    reach the *attack* event $\mathbf{A}$. Recent work by the Cyentia
    Institute found that "5% of all CVEs are both observed within
    organizations AND known to be exploited" [@cyentia2019getting],
    which suggests that $f_{\mathbf{D} \prec \mathbf{A}} \approx 0.95$.

-   Likewise, $\mathbf{D} \prec \mathbf{X}$ holds in 28 of 70 (0.4) $h$.
    However Cyentia found that "15.6% of all open vulnerabilities
    observed across organizational assets in our sample have known
    exploits" [@cyentia2019getting], which suggests that
    $f_{\mathbf{D} \prec \mathbf{X}} \approx 0.844$.

We might therefore expect to find many vulnerabilities remaining
indefinitely in $VFDPxa$.

On their own these observations can equally well support the idea that
we are broadly observing skill in vulnerability response, rather than
that the world is biased from some other cause. However, we could choose
a slightly different goal than differentiating skill and "blind luck" as
represented by the i.i.d. assumption. One could aim to measure "more
skillful than the average for some set of teams" rather than more
skillful than blind luck.

If this were the "reasonable" baseline expectation (**RQ2**), the
primary limitation is available observations. This model helps overcome
this limitation because it provides a clear path toward collecting
relevant observations. For example, by collecting dates for the six
$\sigma \in \Sigma$ for a large sample of vulnerabilities, we can get
better estimates of the relative frequency of each history $h$ in the
real world. It seems as though better data would serve more to improve
benchmarks rather than change expectations of the role of chance.

As an applied example, if we take the first item in the above list as a
broad observation of $f_{\mathbf{D} \prec \mathbf{A}} = 0.95$, we can
plug into [\[eq:alpha_freq\]](#eq:alpha_freq){reference-type="eqref"
reference="eq:alpha_freq"} to get a potential benchmark of
$\alpha_{\mathbf{D} \prec \mathbf{A}} = 0.94$, which is considerably
higher than the naïve generic benchmark $\alpha_d = 0$. It also implies
that we should expect actual observations of histories
$h \in \mathcal{H}$ to skew toward the 19 $h$ in which
$\mathbf{D} \prec \mathbf{A}$ nearly 20x as often as the 51 $h$ in which
$\mathbf{A} \prec \mathbf{D}$. Similarly, if we interpret the second
item as a broad observation of
$f_{\mathbf{D} \prec \mathbf{X}} = 0.844$, we can then compute a
benchmark $\alpha_{\mathbf{D} \prec \mathbf{X}} = 0.81$, which is again
a significant improvement over the naïve $\alpha_d = 0$ benchmark.

## [MPCVD]{acronym-label="MPCVD" acronym-form="singular+long"} {#sec:mpcvd}

[MPCVD]{acronym-label="MPCVD" acronym-form="singular+full"} is the
process of coordinating the creation, release, publication, and
potentially the deployment of fixes for vulnerabilities across a number
of vendors and their respective products. The need for
[MPCVD]{acronym-label="MPCVD" acronym-form="singular+short"} arises due
to the inherent nature of the software supply chain
[@householder2017cert]. A vulnerability that affects a low-level
component (such as a library or operating system API) can require fixes
from both the originating vendor and any vendor whose products
incorporate the affected component. Alternatively, vulnerabilities are
sometimes found in protocol specifications or other design-time issues
where multiple vendors may have each implemented their own components
based on a vulnerable design.
§[6.2.1](#sec:mpcvd_states){reference-type="ref"
reference="sec:mpcvd_states"} applies the state-based view of our model
to [MPCVD]{acronym-label="MPCVD" acronym-form="singular+short"}, while
§[6.2.2](#sec:mpcvd criteria){reference-type="ref"
reference="sec:mpcvd criteria"} addresses the topic from the possible
history perspective.

### State Tracking in [MPCVD]{acronym-label="MPCVD" acronym-form="singular+short"} {#sec:mpcvd_states}

Applying our state-based model to [MPCVD]{acronym-label="MPCVD"
acronym-form="singular+short"} requires a forking approach to the state
tracking. At the time of discovery, the vulnerability is in state
$vfdpxa$. Known only to its finder, the vulnerability can be described
by that singular state.

As it becomes clear that the vulnerability affects multiple vendors'
products, both finder/reporters and coordinators might begin to track
the state of each individual vendor as a separate instance of the model.
For example, if 3 vendors are known to be affected, but only 1 has been
notified, the case might be considered to be in a superposition[^5] of
states $\{Vfdpxa,vfdpxa,vfdpxa\}$.

Each vendor, in turn, might then ascertain whether they are able to
produce fixes for all their available products at once, or if those
fixes will be staggered over time. In either case, the vendor might
track the case as a superposition of states for each affected product
dependent on its fix readiness status. For example, a vendor might have
four products affected, with two in the fix-ready state and two fixes
still in progress. Should they opt for transparency into their internal
process, they might communicate their status as the superposition of
$\{VFdpxa,VFdpxa,Vfdpxa,Vfdpxa\}$. Alternatively, they might choose to
only share the lowest state across their products, which in this example
would be $\{Vfdpxa\}$.

This implies a need to expand our notation. In the
[MPCVD]{acronym-label="MPCVD" acronym-form="singular+short"} case, we
need to think of each state $q \in \mathcal{Q}$ as a set of states
$q_M$: $$q_M \stackrel{\mathsf{def}}{=}\{ q_1,q_2,\dots,q_n \}$$

where $q_i$ represents the state $q$ for the $i$th affected vendor
and/or product. For example, $\{ {Vfdpxa}_1, {vfdpxa}_2 \}$ would
represent the state in which vendor 1 has been notified but vendor 2 has
not.

State transitions across vendors need not be simultaneous. Very often,
vendor notification occurs as new products and vendors are identified as
affected in the course of analyzing a vulnerability report. So the
individual events $\mathbf{V}_i$ in $\mathbf{V}_M$ (representing the
status of all the vendor notifications) might be spread out over a
period of time.

Some transitions are more readily synchronized than others. For example,
if an [MPCVD]{acronym-label="MPCVD" acronym-form="singular+short"} case
is already underway, and information about the vulnerability appears in
a public media report, we can say that $\mathbf{P}_M$ occurred
simultaneously for all coordinating vendors.

Regardless, in the maximal case, each vendor-product pair is effectively
behaving independently of all the others. Thus the maximum
dimensionality of the [MPCVD]{acronym-label="MPCVD"
acronym-form="singular+short"} model for a case is
$$D_{max} = 5 * N_{vprod}$$

where $N_{vprod}$ represents the number of vendor-product pairs.

This is of course undesirable, as it would result in a wide distribution
of realized histories that more closely resemble the randomness
assumptions outlined above than a skillful, coordinated effort. Further
discussion of measuring [MPCVD]{acronym-label="MPCVD"
acronym-form="singular+short"} skill can be found in
[6.2.2](#sec:mpcvd criteria){reference-type="ref"
reference="sec:mpcvd criteria"}. For now, though, we posit that the goal
of a good [MPCVD]{acronym-label="MPCVD" acronym-form="singular+short"}
process is to reduce the dimensionality of a given
[MPCVD]{acronym-label="MPCVD" acronym-form="singular+short"} case as
much as is possible (i.e., to the 5 dimensions of a single vendor
[CVD]{acronym-label="CVD" acronym-form="singular+short"} case we have
presented above). Experience shows that a full dimension reduction is
unlikely in most cases, but that does not detract from the value of
having the goal.

Vendors may be able to reduce their internal tracking
dimensionality---which may be driven by things like component reuse
across products or product lines---through in-house coordination of fix
development processes. Within an individual vendor organization,
[PSIRTs]{acronym-label="PSIRT" acronym-form="plural+short"} are a common
organizational structure to address this internal coordination process.
The [FIRST]{acronym-label="FIRST" acronym-form="singular+short"} PSIRT
Services Framework provides guidance regarding vendors' internal
processes for coordinating vulnerability response [@first2020psirt].
Additional guidance can be found in ISO-IEC 30111 [@ISO30111].

Regardless, the cross-vendor dimension is largely the result of
component reuse across vendors, for example through the inclusion of
third party libraries or [OEM]{acronym-label="OEM"
acronym-form="singular+short"} [SDKs]{acronym-label="SDK"
acronym-form="plural+short"}. Visibility of cross-vendor component reuse
remains an unsolved problem, although efforts such as
[NTIA]{acronym-label="NTIA" acronym-form="singular+short"}'s
[SBOM]{acronym-label="SBOM" acronym-form="singular+short"} [@ntia_sbom]
efforts are promising in this regard. Thus, dimensionality reduction can
be achieved through both improved transparency of the software supply
chain and the process of coordination toward synchronized state
transitions, especially for $\mathbf{P}$, if not for $\mathbf{F}$ and
$\mathbf{D}$ as well.

As a result of the dimensionality problem, coordinators and other
parties to an [MPCVD]{acronym-label="MPCVD"
acronym-form="singular+short"} case need to decide how to apply
disclosure policy rules in cases where different products or vendors
occupy different case states with potentially contradictory recommended
actions. For example, when four out of five vendors involved in a case
have reached $VFdpxa$ and are ready to publish, but the fifth is still
in $Vfdpxa$. Essentially this can be expected to take the form of a
weighting function that acts on a vector of case states, and outputs a
set of recommended actions derived from those states.

One possible function would be to apply a simple voting heuristic such
as waiting for a simple majority of vendors to reach a state before
taking action as that state recommends. In our 4/5 $VFdpxa$ example, the
coordinating parties would simply behave as if the case were in that
state for all. Another could be to weight vendors and products by some
other factor, such as size of the installed user base, or even based on
a risk analysis of societal costs associated with potential actions.
Here we acknowledge that our example is under-specified: does the fifth
vendor (the one in $Vfdpxa$) represent a sizable fraction of the total
user base? Or does it concentrate the highest risk use cases for the
software? Challenges in efficiently assessing consistent answers to
these questions are easy to imagine. The status quo for
[MPCVD]{acronym-label="MPCVD" acronym-form="singular+short"} appears
consistent with defaulting to simple majority in the absence of
additional information, with consideration given to the distribution of
both users and risk on a case-by-case basis. At present, there is no
clear consensus on such policies, although we hope that future work can
use the model presented here to formalize the necessary analysis.

##### Integrating [FIRST]{acronym-label="FIRST" acronym-form="singular+short"} [MPCVD]{acronym-label="MPCVD" acronym-form="singular+short"} Guidance

[FIRST]{acronym-label="FIRST" acronym-form="singular+short"} has
published [MPCVD]{acronym-label="MPCVD" acronym-form="singular+short"}
guidance [@first2020mpcvd]. Their guidance describes four use cases,
along some with variations. Each use case variant includes a list of
potential causes along with recommendations for prevention and responses
when the scenario is encountered. A mapping of which use cases and
variants apply to which subsets of states is given in Table
[6.1](#tab:first_use_cases){reference-type="ref"
reference="tab:first_use_cases"}.

::: {#tab:first_use_cases}
           States           [FIRST]{acronym-label="FIRST" acronym-form="singular+short"} Use Case  Description
  ------------------------ ----------------------------------------------------------------------- ----------------------------------------------------------------------------------------------
            n/a                                               0                                    No vulnerability exists
          ${VFDp}$                                            1                                    Vulnerability with no affected users
           ${Vp}$                                        1 Variant 1                               Product is deployed before vulnerability is discovered or fixed
           ${f}$                                              2                                    Vulnerability with coordinated disclosure
          ${fdP}$                                        2 Variant 1                               Finder makes the vulnerability details public prior to remediation
          ${VFdP}$                                       2 Variant 2                               Users do not deploy remediation immediately
     (multiparty sync)                                   2 Variant 3                               Missing communication between upstream and downstream vendors
          ${VfdP}$                                       2 Variant 4                               Vendor makes the vulnerability details public prior to remediation
          ${Vfd}$                                        2 Variant 5                               Vendor does not remediate a reported vulnerability
     (multiparty sync)                                   2 Variant 6                               Missing communication between peer vendors impedes coordination
          ${fdP}$                                        2 Variant 7                               Coordinator makes vulnerability details public prior to remediation
     ${Vfdp}$, ${vfdp}$                                  2 Variant 8                               Finder reports a vulnerability to one vendor that may affect others using the same component
          ${fdP}$                                             3                                    Public disclosure of limited vulnerability information prior to remediation
   ${vP}$, ${vX}$, ${vA}$                                     4                                    Public disclosure or exploitation of vulnerability prior to vendor awareness
     ${vfPX}$, ${vfPA}$                                  4 Variant 1                               Finder publishes vulnerability details and vulnerability is exploited
          ${vpA}$                                        4 Variant 2                               Previously undisclosed vulnerability used in attacks

  : Applicability of [FIRST]{acronym-label="FIRST"
  acronym-form="singular+short"} [MPCVD]{acronym-label="MPCVD"
  acronym-form="singular+short"} scenarios to subsets of states in our
  model
:::

### [MPCVD]{acronym-label="MPCVD" acronym-form="singular+short"} Benchmarks {#sec:mpcvd criteria}

A common problem in [MPCVD]{acronym-label="MPCVD"
acronym-form="singular+short"} is that of fairness: coordinators are
often motivated to optimize the [CVD]{acronym-label="CVD"
acronym-form="singular+short"} process to maximize the deployment of
fixes to as many end users as possible while minimizing the exposure of
users of other affected products to unnecessary risks.

The model presented in this paper provides a way for coordinators to
assess the effectiveness of their [MPCVD]{acronym-label="MPCVD"
acronym-form="singular+short"} cases. In an
[MPCVD]{acronym-label="MPCVD" acronym-form="singular+short"} case, each
vendor/product pair effectively has its own 6-event history $h_a$. We
can therefore recast [MPCVD]{acronym-label="MPCVD"
acronym-form="singular+short"} as a set of histories $\mathcal{M}$ drawn
from the possible histories $\mathcal{H}$:
$$\mathcal{M} = \{ h_1,h_2,...,h_m \textrm{ where each } h_a \in H \}$$
Where $m = |\mathcal{M}| \geq 1$. The edge case when $|\mathcal{M}| = 1$
is simply the regular (non-multiparty) case.

We can then set desired criteria for the set $\mathcal{M}$, as in the
benchmarks described in §[6.1](#sec:benchmarks){reference-type="ref"
reference="sec:benchmarks"}. In the [MPCVD]{acronym-label="MPCVD"
acronym-form="singular+short"} case, we propose to generalize the
benchmark concept such that the median $\Tilde{\alpha_d}$ should be
greater than some benchmark constant $c_d$:

$$\Tilde{\alpha_d} \geq c_d \geq 0$$

In real-world cases where some outcomes across different vendor/product
pairs will necessarily be lower than others, we can also add the
criteria that we want the variance of each $\alpha_d$ to be low. An
[MPCVD]{acronym-label="MPCVD" acronym-form="singular+short"} case having
high median $\alpha_d$ with low variance across vendors and products
involved will mean that most vendors achieved acceptable outcomes.

To summarize:

-   The median $\alpha_d$ for all histories $h \in \mathcal{M}$ should
    be positive and preferably above some benchmark constant $c_d$,
    which may be different for each $d \in \mathbb{D}$.

    $$Median(\{ \alpha_d(h) : h \in \mathcal{M} \}) \geq c_d > 0$$

-   The variance of each $\alpha_d$ for all histories
    $h \in \mathcal{M}$ should be low. The constant $\varepsilon$ is
    presumed to be small.

    $$\sigma^2(\{ \alpha_d(h) : h \in \mathcal{M} \}) \leq \varepsilon$$

## [CVD]{acronym-label="CVD" acronym-form="singular+short"} Roles and Their Influence {#sec:roles}

[CVD]{acronym-label="CVD" acronym-form="singular+short"} stakeholders
include vendors, system owners, the security research community,
coordinators, and governments [@householder2017cert]. Of interest here
are the main roles: *finder/reporter*, *vendor*, *deployer*, and
*coordinator*. Each of the roles corresponds to a set of transitions
they can cause. For example, a *coordinator* can notify the *vendor*
($\mathbf{V}$) but not create the fix ($\mathbf{F}$), whereas a *vendor*
can create the fix but not notify itself (although a *vendor* with an
in-house vulnerability discovery capability might also play the role of
a *finder/reporter* as well). A mapping of [CVD]{acronym-label="CVD"
acronym-form="singular+short"} Roles to the transitions they can control
can be found in Table [6.2](#tab:cvd_roles){reference-type="ref"
reference="tab:cvd_roles"}. We also included a role of *adversary* just
to cover the $\mathbf{A}$ transition.

::: {#tab:cvd_roles}
        Role         $\mathbf{V}$   $\mathbf{F}$   $\mathbf{D}$   $\mathbf{P}$   $\mathbf{X}$   $\mathbf{A}$
  ----------------- -------------- -------------- -------------- -------------- -------------- --------------
   Finder/Reporter                    $\cdot$        $\cdot$                                      $\cdot$
       Vendor          $\cdot$                       $\cdot$                                      $\cdot$
      Deployer         $\cdot$        $\cdot$                       $\cdot$        $\cdot$        $\cdot$
     Coordinator                      $\cdot$        $\cdot$                                      $\cdot$
      Adversary        $\cdot$        $\cdot$        $\cdot$        $\cdot$        $\cdot$     

  : [CVD]{acronym-label="CVD" acronym-form="singular+short"} Roles and
  the transitions they can control. Roles can be combined (vendor +
  deployer, finder + coordinator, etc.). Roles are based on
  [@householder2017cert].
:::

Different stakeholders might want different things, although most
benevolent parties will likely seek some subset of $\mathbb{D}$. Because
$\mathcal{H}$ is the same for all stakeholders, the expected frequencies
shown in Table [4.1](#tab:event_freq){reference-type="ref"
reference="tab:event_freq"} will be consistent across any such
variations in desiderata.

::: {#tab:stakeholder_order}
  ------------------------------- ------------------ ------------------ ------------------
                                        Vendor            SysOwner         Coordinator
  $d \in \mathbb{D}$               ($\mathbb{D}_v$)   ($\mathbb{D}_s$)   ($\mathbb{D}_c$)
  $\mathbf{V} \prec \mathbf{P}$          yes              maybe^4^             yes
  $\mathbf{V} \prec \mathbf{X}$          yes              maybe^4^             yes
  $\mathbf{V} \prec \mathbf{A}$          yes              maybe^4^             yes
  $\mathbf{F} \prec \mathbf{P}$          yes              maybe^5^             yes
  $\mathbf{F} \prec \mathbf{X}$          yes                yes                yes
  $\mathbf{F} \prec \mathbf{A}$          yes                yes                yes
  $\mathbf{D} \prec \mathbf{P}$        maybe^1^           maybe^1^             yes
  $\mathbf{D} \prec \mathbf{X}$        maybe^2^           maybe^5^             yes
  $\mathbf{D} \prec \mathbf{A}$        maybe^2^             yes                yes
  $\mathbf{P} \prec \mathbf{X}$          yes                yes                yes
  $\mathbf{P} \prec \mathbf{A}$          yes                yes                yes
  $\mathbf{X} \prec \mathbf{A}$        maybe^3^           maybe^3^           maybe^3^
  ------------------------------- ------------------ ------------------ ------------------

  : Ordering Preferences for Selected Stakeholders.
:::

::: tablenotes
^1^ When vendors control deployment, both vendors and system owners
likely prefer $\mathbf{D} \prec \mathbf{P}$. When system owners control
deployment, $\mathbf{D} \prec \mathbf{P}$ is impossible.

^2^ Vendors should care about orderings involving $\mathbf{D}$ when they
control deployment, but might be less concerned if deployment
responsibility is left to system owners.

^3^ Exploit publication can be controversial. To some, it enables
defenders to test deployed systems for vulnerabilities or detect
attempted exploitation. To others, it provides unnecessary adversary
advantage.

^4^ System owners may only be concerned with orderings involving
$\mathbf{V}$ insofar as it is a prerequisite for $\mathbf{F}$.

^5^ System owners might be indifferent to $\mathbf{F} \prec \mathbf{P}$
and $\mathbf{D} \prec \mathbf{X}$ depending on their risk tolerance.
:::

A discussion of some stakeholder preferences is given below, while a
summary can be found in Table
[6.3](#tab:stakeholder_order){reference-type="ref"
reference="tab:stakeholder_order"}. We notate these variations of the
set of desiderata $\mathbb{D}$ with subscripts: $\mathbb{D}_v$ for
vendors, $\mathbb{D}_s$ for system owners, $\mathbb{D}_c$ for
coordinators, and $\mathbb{D}_g$ for governments. In
Table [3.3](#tab:ordered_pairs){reference-type="ref"
reference="tab:ordered_pairs"} we defined a preference ordering between
every possible pairing of events, therefore $\mathbb{D}$ is the largest
possible set of desiderata. We thus expect the desiderata of benevolent
stakeholders to be a subset of $\mathbb{D}$ in most cases. That said, we
note a few exceptions in the text that follows.

### Vendors

As shown in Table [6.3](#tab:stakeholder_order){reference-type="ref"
reference="tab:stakeholder_order"}, we expect vendors' desiderata
$\mathbb{D}_v$ to be a subset of $\mathbb{D}$. It seems reasonable to
expect vendors to prefer that a fix is ready before either exploit
publication or attacks ($\mathbf{F} \prec \mathbf{X}$ and
$\mathbf{F} \prec \mathbf{A}$, respectively). Fix availability implies
vendor awareness ($\mathbf{V} \prec \mathbf{F}$), so we would expect
vendors' desiderata to include those orderings as well
($\mathbf{V} \prec \mathbf{X}$ and $\mathbf{V} \prec \mathbf{A}$,
respectively).

Vendors typically want to have a fix ready before the public finds out
about a vulnerability ($\mathbf{F} \prec \mathbf{P}$). We surmise that a
vendor's preference for this item could be driven by at least two
factors: the vendor's tolerance for potentially increased support costs
(e.g., fielding customer support calls while the fix is being prepared),
and the perception that public awareness without an available fix leads
to a higher risk of attacks. As above, vendor preference for
$\mathbf{F} \prec \mathbf{P}$ implies a preference for
$\mathbf{V} \prec \mathbf{P}$ as well.

When a vendor has control over fix deployment ($\mathbf{D}$), it will
likely prefer that deployment precede public awareness, exploit
publication, and attacks ($\mathbf{D} \prec \mathbf{P}$,
$\mathbf{D} \prec \mathbf{X}$, and $\mathbf{D} \prec \mathbf{A}$,
respectively).[^6] However, when fix deployment depends on system owners
to take action, the feasibility of $\mathbf{D} \prec \mathbf{P}$ is
limited.[^7] Regardless of the vendor's ability to deploy fixes or
influence their deployment, it would not be unreasonable for them to
prefer that public awareness precedes both public exploits and attacks
($\mathbf{P} \prec \mathbf{X}$ and $\mathbf{P} \prec \mathbf{A}$,
respectively).

Ensuring the ease of patch deployment by system owners remains a likely
concern for vendors. Conscientious vendors might still prefer
$\mathbf{D} \prec \mathbf{X}$ and $\mathbf{D} \prec \mathbf{A}$ even if
they have no direct control over those factors. However, vendors may be
indifferent to $\mathbf{X} \prec \mathbf{A}$.

Although our model only addresses event ordering, not timing, a few
comments about timing of events are relevant since they reflect the
underlying state transition process from which $\mathcal{H}$ arises.
Vendors have significant influence over the speed of $\mathbf{V}$ to
$\mathbf{F}$ based on their vulnerability handling, remediation, and
development processes [@ISO30111]. They can also influence how early
$\mathbf{V}$ happens based on promoting a cooperative atmosphere with
the security researcher community [@ISO29147]. Vendor architecture and
business decisions affect the speed of $\mathbf{F}$ to $\mathbf{D}$.
Cloud-based services and automated patch delivery can shorten the lag
between $\mathbf{F}$ and $\mathbf{D}$. Vendors that leave deployment
contingent on system owner action can be expected to have longer lags,
making it harder to achieve the $\mathbf{D} \prec \mathbf{P}$,
$\mathbf{D} \prec \mathbf{X}$, and $\mathbf{D} \prec \mathbf{A}$
objectives, respectively.

### System Owners

System owners ultimately determine the lag from $\mathbf{F}$ to
$\mathbf{D}$ based on their processes for system inventory, scanning,
prioritization, patch testing, and deployment---in other words, their
[VM]{acronym-label="VM" acronym-form="singular+full"} practices. In
cases where the vendor and system owner are distinct entities, system
owners should optimize to minimize the lag between $\mathbf{F}$ and
$\mathbf{D}$ in order to improve the chances of meeting the
$\mathbf{D} \prec \mathbf{X}$ and $\mathbf{D} \prec \mathbf{A}$
objectives, respectively. Enabling automatic updates for security
patches is one way to improve $\mathbf{F}$ to $\mathbf{D}$ performance,
although not all system owners find the resulting risk of operational
impact to be acceptable to their change management process.

System owners might select a different desiderata subset than vendors
$\mathbb{D}_s \subseteq \mathbb{D}$, $\mathbb{D}_s \neq \mathbb{D}_v$.
In general, system owners are primarily concerned with the $\mathbf{F}$
and $\mathbf{D}$ events relative to $\mathbf{X}$ and $\mathbf{A}$.
Therefore, we expect system owners to be concerned about
$\mathbf{F} \prec \mathbf{X}$, $\mathbf{F} \prec \mathbf{A}$,
$\mathbf{D} \prec \mathbf{X}$, and $\mathbf{D} \prec \mathbf{A}$. As
discussed above, $\mathbf{D} \prec \mathbf{P}$ is only possible when the
vendor controls $\mathbf{D}$. Depending on the system owner's risk
tolerance, $\mathbf{F} \prec \mathbf{P}$ and
$\mathbf{D} \prec \mathbf{X}$ may or may not be preferred. Some system
owners may find $\mathbf{X} \prec \mathbf{A}$ useful for testing their
infrastructure, others might prefer that no public exploits be
available.

### Security Researchers

The "friendly" offensive security community (i.e., those who research
vulnerabilities, report them to vendors, and sometimes release
proof-of-concept exploits for system security evaluation purposes) can
do their part to ensure that vendors are aware of vulnerabilities as
early as possible prior to public disclosure
[\[eq:notify_vendor\]](#eq:notify_vendor){reference-type="eqref"
reference="eq:notify_vendor"}. $$\label{eq:notify_vendor}
vfdpxa \xrightarrow{\mathbf{V}} Vfdpxa \implies \mathbf{V} \prec \mathbf{P} \textrm{, } \mathbf{V} \prec \mathbf{X} \textrm{ and } \mathbf{V} \prec \mathbf{A}$$

Security researchers can also delay the publication of exploits until
after fixes exist [\[eq:fx\]](#eq:fx){reference-type="eqref"
reference="eq:fx"}, are public
[\[eq:fxpx\]](#eq:fxpx){reference-type="eqref" reference="eq:fxpx"}, and
possibly even until most system owners have deployed the fix
[\[eq:fxpxdx\]](#eq:fxpxdx){reference-type="eqref"
reference="eq:fxpxdx"}. $$\begin{aligned}
\label{eq:fx}
  \mathbf{X}|q \in VFdpx &\implies \mathbf{F} \prec \mathbf{X} \\
  \label{eq:fxpx}
  \mathbf{X}|q \in VFdPx &\implies \mathbf{F} \prec \mathbf{X} \textrm{ and } \mathbf{P} \prec \mathbf{X}\\
  \label{eq:fxpxdx}
  \mathbf{X} |q \in VFDPx &\implies \mathbf{F} \prec \mathbf{X} \textrm{, } \mathbf{P} \prec \mathbf{X} \textrm{ and } \mathbf{D} \prec \mathbf{X} 
\end{aligned}$$ This does not preclude adversaries from doing their own
exploit development on the way to $\mathbf{A}$, but it avoids providing
them with unnecessary assistance.

### Coordinators

Coordinators have been characterized as seeking to balance the social
good across both vendors and system owners [@arora2008optimal]. This
implies that they are likely interested in the union of the vendors' and
system owners' preferences. In other words, coordinators want the full
set of desiderata ($\mathbb{D}_c = \mathbb{D}$).

We pause for a brief aside about the design of the model with respect to
the coordination role. We considered adding a *Coordinator Awareness*
($\mathbf{C}$) event, but this would expand $|\mathcal{H}|$ from 70 to
452 because it could occur at any point in any $h$. There is not much
for a coordinator to do once the fix is deployed, however, so we could
potentially reduce $|\mathcal{H}|$ to 329 by only including positions in
$\mathcal{H}$ that precede the $\mathbf{D}$ event. This is still too
large and unwieldy for meaningful analysis within our scope; instead, we
simply provide the following comment.

The goal of coordination is this: regardless of which stage a
coordinator becomes involved in a case, the objective is to choose
actions that make preferred histories more likely and non-preferred
histories less likely.

The rules outlined in §[6.8](#sec:cvd_action_rules){reference-type="ref"
reference="sec:cvd_action_rules"} suggest available actions to improve
outcomes. Namely, this means focusing coordination efforts as needed on
vendor awareness, fix availability, fix deployment, and the
appropriately timed public awareness of vulnerabilities and their
exploits ($\mathbf{V}$,$\mathbf{F}$,$\mathbf{D}$, $\mathbf{P}$, and
$\mathbf{X}$).

### Governments

In their defensive roles, governments act as a combination of system
owners, vendors, andincreasinglycoordinators. Therefore we might
anticipate $\mathbb{D}_g = \mathbb{D}_c = \mathbb{D}$.

However, governments sometimes also have an adversarial role to play for
national security, law enforcement, or other reasons. The model
presented in this paper could be adapted to that role by drawing some
desiderata from the lower left triangle of Table
[3.3](#tab:ordered_pairs){reference-type="ref"
reference="tab:ordered_pairs"}. While defining such adversarial
desiderata ($\mathbb{D}_a$) is out of scope for this paper, we leave the
topic with our expectation that $\mathbb{D}_a \not\subseteq \mathbb{D}$.

## Disclosure Policy Formalization {#sec:policy_formalism}

In this section, we apply our model to the formalization of
vulnerability disclosure policies. This discussion is not intended to be
a complete formalization of all possible policy choices; rather, we seek
to relate how some aspects of disclosure policies might be formalized
using our model. In particular, we will look at applications of the
model to embargoes and service level expectations.

### Embargo Initiation Policies

An agreement between coordinating stakeholders to keep information about
the vulnerability private until some exit condition has been met is
called an *embargo*.[^8] Examples of exit conditions for
[CVD]{acronym-label="CVD" acronym-form="singular+short"} embargoes
include the expiration of a timer or a the occurrence of a triggering
event such as fix availability. The model gives us a way of formally
specifying the conditions under which initiating or maintaining an
embargo may or may not be appropriate.

Let us first examine which states are eligible for embargoes to be
initiated. The whole point of an embargo is to restrict public knowledge
of the vulnerability for some period of time, corresponding to a desire
to avoid entering $\mathcal{Q}_{P}$ until the embargo ends. Therefore,
it follows that our set of embargo initiation states must reside in
$\mathcal{Q}_{p}$. Furthermore, as we have discussed, $pX$ is inherently
unstable because publication of an exploit necessarily leads to public
awareness of the vulnerability. Because $pX$ leads immediately to $PX$,
we can infer that our embargo entry points must be in $px$.

Many disclosure policies---including [CERT/CC]{acronym-label="CERT/CC"
acronym-form="singular+short"}'s---eschew embargoes when attacks are
underway ($\mathcal{Q}_{A}$). This implies we should be looking in
$pxa$. We further observe that there is little reason to initiate an
information embargo about a vulnerability after the fix has been
deployed[^9] ($D$) and thus continue with $dpxa$.

In cases where a single vendor and product are affected, then fix
readiness is truly binary (it either is or is not ready), and there may
be no need to enter into an embargo when the fix is ready (i.e., in
$Fdpxa$). However, while may be tempted to expand the requirement and
narrow the states of interest to $fdpxa$, we must allow for the
multiparty situation in which some vendors have a fix ready ($Fp$) while
others do not ($fp$). We discuss [MPCVD]{acronym-label="MPCVD"
acronym-form="singular+short"} further in section
§[6.2](#sec:mpcvd){reference-type="ref" reference="sec:mpcvd"}. Here we
note that in [MPCVD]{acronym-label="MPCVD"
acronym-form="singular+short"} cases, prudence requires us to allow for
a (hopefully brief) embargo period to enable more vendors to achieve
$fp \xrightarrow{\mathbf{F}} Fp$ prior to public disclosure
($\mathbf{F} \prec \mathbf{P}$). Therefore we stick with $dpxa$ for the
moment.

Finally, because embargoes are typically an agreement between the vendor
and other coordinating parties, it might appear that we should expect
embargoes to begin in ${Vdpxa}$. However, doing so would neglect the
possibility of embargoes entered into by finders, reporters, and
coordinators prior to vendor awareness---i.e., in ${vfdpxa}$. In fact,
the very concept of [CVD]{acronym-label="CVD"
acronym-form="singular+short"} is built on the premise that every newly
discovered vulnerability should have a default embargo at least until
the vendor has been informed about the vulnerability (i.e.,
${vfdpxa} \xrightarrow{\mathbf{V}} {Vfdpxa}$ is
[CVD]{acronym-label="CVD" acronym-form="singular+short"}'s preferred
initial state transition). And so, having considered all possible
states, we conclude that embargoes can only begin from ${dpxa}$, with
the caveat that practitioners should carefully consider why they would
enter an embargo from ${Fdpxa}$.

This leaves us with only few states from which we can enter an embargo,
which we denote as $\mathcal{Q}_{E}^{0}$:

$$\label{eq:embargo_start}
    \mathcal{Q}_{E}^{0} \stackrel{\mathsf{def}}{=}{dpxa} = \{{vfdpxa}, {Vfdpxa}, {VFdpxa}\}$$

### Embargo Continuation Policies

Having shown the limited number of states from which an embargo can
begin, we turn next to the states in which an embargo remains viable. By
*viable* we mean that maintaining the embargo is reasonable and not
contraindicated by the facts at hand. It is of course possible for
parties to attempt to maintain embargoes in spite of facts indicating
they should do otherwise. We are not here to support such contrived
arguments.

By definition an embargo must be viable in all the states it can start
from, so we'll begin with $\mathcal{Q}_{E}^{0}$ (${dpxa}$) and consider
which restrictions we can relax, as there may be states in which an
existing embargo remains viable even if one should not initiate a new
one.

To begin, states in $\mathcal{Q}_{p}$ remain a necessary condition
because keeping the public from becoming aware of the vulnerability too
early is the key state the embargo is intended to maintain. Furthermore,
because our starting criteria is already indifferent to vendor awareness
and fix availability, we will not revisit those here.

It appears we can relax $\mathcal{Q}_{d}$ because it is certainly
possible in some situations to maintain an embargo after a fix is
deployed, as is common in CVD cases regarding specific instances of
vulnerabilities. For example, web site vulnerabilities are often only
published after the system is no longer vulnerable. So our set of viable
states is currently ${pxa}$.

Next, we address two potential sticking points, $\mathbf{X}$ and
$\mathbf{A}$. First, how long can an existing embargo persist in ${pX}$?
The embargo can persist only for as long as it takes for public
awareness of its existence to take hold
${pX} \xrightarrow{\mathbf{P}} {PX}$. This might be reasonable for a few
hours or at best a few days, but not much longer.[^10] In other words,
an active embargo for a vulnerability case in a state $q \in {pX}$ has
either already failed or is at imminent risk of failure to prevent
public awareness. For this reason, it seems better to presume embargo
non-viability in ${pX}$.

Second, what should we do if an embargo is in place and we find out that
attacks are happening---i.e., we assess that we are in a state
$q \in {pA}$? Cases in ${pA}$ give the attacker an advantage over
defenders insofar as attackers are able to exploit vulnerabilities while
deployers remain ignorant of steps they might take to defend their
systems. For this reason, many organizations' disclosure policies
explicitly call out observed attacks as a reason to break an embargo.
Therefore, while it may be technically possible to maintain an embargo
in ${pxA}$, we remain skeptical of the reason for doing so, if not to
maintain the ability for attacks to remain stealthy.

In the interest of avoiding justification for bad faith disclosure
behaviors, we hold that embargoes remain viable only in ${pxa}$, with
the caveat that only limited circumstances as described above justify
maintaining embargoes once $\mathbf{F}$ or $\mathbf{D}$ have occurred
(${VFdpxa}$ and ${VFDpxa}$, respectively).

$$\label{eq:embargo_viable}
    \mathcal{Q}_{E} \stackrel{\mathsf{def}}{=}{pxa} = \{{vfdpxa}, {Vfdpxa}, {VFdpxa}, {VFDpxa}\}$$

In summary, embargoes can be initiated if the case is in
$\mathcal{Q}_{E}^{0}$ as in Eq.
[\[eq:embargo_start\]](#eq:embargo_start){reference-type="eqref"
reference="eq:embargo_start"}, and remain viable through any state in
$\mathcal{Q}_{E}$ as in Eq.
[\[eq:embargo_viable\]](#eq:embargo_viable){reference-type="eqref"
reference="eq:embargo_viable"}. This in turn gives us specific things to
look for in order to determine when to end an embargo:

-   The embargo timer has expired.

-   Any observation of $\mathbf{P}$, $\mathbf{X}$, or $\mathbf{A}$ has
    been made ($q \not\in {pxa}$).

-   $\mathbf{F}$ or $\mathbf{D}$ have occurred
    ($q \in \{{VFdpxa}, {VFDpxa}\})$, and no reasons specific to the
    case to maintain the embargo remain.

-   Any other embargo exit rules---such as those specified in the
    relevant disclosure policies---have been triggered.

### [CVD]{acronym-label="CVD" acronym-form="singular+short"} Service Level Expectations

Closely related to [CVD]{acronym-label="CVD"
acronym-form="singular+short"} embargoes are [CVD]{acronym-label="CVD"
acronym-form="singular+short"} [SLEs]{acronym-label="SLE"
acronym-form="plural+short"}. Disclosure policies specify commitments by
coordinating parties to ensure the occurrence of certain state
transitions within a specific period of time. While the model presented
here does not directly address timing choices, we can point out some
ways to relate the model to those choices. Specifically, we intend to
demonstrate how disclosure policy [SLEs]{acronym-label="SLE"
acronym-form="plural+short"} can be stated as rules triggered within
subsets of states or by particular transitions between subsets of states
in $\mathcal{Q}$.

For example, a finder, reporter, or coordinator might commit to
publishing information about a vulnerability 30 days after vendor
notification. This translates to starting a timer at
${v} \xrightarrow{\mathbf{V}} {V}$ and ensuring
${Vp} \xrightarrow{\mathbf{P}} {VP}$ when the timer expires. Notice that
the prospect of ${Vfp} \xrightarrow{\mathbf{P}} {VfP}$ is often used to
motivate vendors to ensure a reasonable [SLE]{acronym-label="SLE"
acronym-form="singular+short"} to produce fixes
(${Vf} \xrightarrow{\mathbf{F}} {VF}$) [@arora2008optimal].

Similarly, a vendor might commit to providing public fixes within 5
business days of report receipt. In that case, the
[SLE]{acronym-label="SLE" acronym-form="singular+short"} timer would
start at ${vfp} \xrightarrow{\mathbf{V}} {Vfp}$ and and end at one of
two transitions: First, the "normal" situation in which the vendor
creates a fix and makes it public along with the vulnerability
($\mathbf{F} \prec \mathbf{P}$, i.e.,
${VFp} \xrightarrow{\mathbf{P}} {VFP}$). Second, a "zero day"
situation[^11] in which events outside the vendor's control cause the
${Vfp} \xrightarrow{\mathbf{P}} {VfP}$ transition to occur prior to the
fix being ready (${VfP} \xrightarrow{\mathbf{F}} {VFP}$), i.e,
$\mathbf{P} \prec \mathbf{F}$. Likewise, the
${Vfp} \xrightarrow{\mathbf{P}} {VfP} \xrightarrow{\mathbf{F}} {VFP}$
path might also occur when a vendor has set their embargo timer too
aggressively for their development process to keep up.

It is therefore in the vendor's interest to tune their
[SLE]{acronym-label="SLE" acronym-form="singular+short"} to reduce the
likelihood for unexpected public awareness ($\mathbf{P}$) while
providing sufficient time for $\mathbf{F}$ to occur, optimizing to
achieve $\mathbf{F} \prec \mathbf{P}$ in a substantial fraction of
cases. As future work, measurement of both the incidence and timing of
embargo failures through observation of $\mathbf{P}$, $\mathbf{X}$, and
$\mathbf{A}$ originating from $\mathcal{Q}_{E}$ could give insight into
appropriate vendor [SLEs]{acronym-label="SLE"
acronym-form="plural+short"} for fix readiness ($\mathbf{F}$).

Service providers and [VM]{acronym-label="VM"
acronym-form="singular+short"} practitioners might similarly describe
their [SLEs]{acronym-label="SLE" acronym-form="plural+short"} in terms
of timing between states. Such policies will likely take the form of
commitments to limit the time spent in ${FdP}$. When the vendor has
already produced a patch, the clock starts at
${Fdp} \xrightarrow{\mathbf{P}} {FdP}$, whereas if the vulnerability
becomes public prior to patch the clock starts at
${fdP} \xrightarrow{\mathbf{F}} {FdP}$. In both cases, the timer ends at
${FdP} \xrightarrow{\mathbf{D}} {FDP}$.

Future formal definitions of policy statements might take the general
form of specifications including

-   Starting state ($q \in \mathcal{Q}$) or subset of states
    ($S \subset \mathcal{Q}$)

-   Expected transitions ($\sigma \in \Sigma$) and
    [SLEs]{acronym-label="SLE" acronym-form="plural+short"} around their
    timing, including possible constraints such as "not before" and "no
    later than" specifications

-   An indication of constraint rigidity (negotiable, fixed, *MUST*,
    *SHOULD*, *MAY* [@bradner1997rfc2119], etc.)

-   Potential exceptions in the form of other transitions
    ($\sigma \in \Sigma$) that might alter expected behavior, and a
    description of the anticipated response.

One reason to formalize policy definitions is the potential to
automatically resolve embargo negotiations when those policies are
compatible. It may be possible to resolve some apparent policy conflicts
by delaying notifications to some vendors to ensure that all embargo end
timers expire simultaneously. We informally refer to this as the
*Thanksgiving Dinner problem*, due to its similarity to the familiar
annual holiday meal in which a number of dishes with varying preparation
times are expected to be delivered to the table simultaneously, each at
its appropriate temperature and doneness. For example, when one party
has a "minimum 90 days to publish" policy and another has a "maximum 5
days to publish" policy, the resolution could be to notify the first
vendor 85 days before notifying the second. Such a model of graduated
disclosure could work well for cases where notifications are automated
and vendor dependencies are small or where coordinating parties'
policies can be resolved as compatible. Technology such as Theorem
Provers and Solvers seem likely to be suited to this sort of problem.

However, when formal policies are incompatible, the failure to resolve
them automatically becomes an opportunity for human intervention as the
exception handler of last resort. Of potential concern here are
[MPCVD]{acronym-label="MPCVD" acronym-form="singular+short"} cases in
which a vendor with a long policy timer is dependent on one with a short
policy timer to provide fixes. The serial nature of the dependency
creates the potential for a compatibility conflict. For example, this
can happen when an OS kernel provider's disclosure policy specifies a
shorter embargo timer than the policies of device manufacturers whose
products depend on that OS kernel. Automation can draw attention to
these sorts of conflicts, but their resolution is likely to require
human intervention for some time to come.

## Improving Definitions of Common Terms {#sec:defining_common_terms}

Some terms surrounding [CVD]{acronym-label="CVD"
acronym-form="singular+short"} and [VM]{acronym-label="VM"
acronym-form="singular+short"} have been ambiguously defined in common
usage. One benefit of the definition of events, states, and possible CVD
histories presented in this whitepaper is an opportunity to clarify
definitions of related terms. In this section we will use our model to
formally define their meaning.

### Zero Day {#sec:zerodays}

The information security community uses a variety of common phrases that
contain the words *zero day*. This creates confusion. For example, a
reviewer stated that they prefer to define "zero day vulnerability" as
$\mathbf{X} \prec \mathbf{V}$ and not $(\mathbf{P} \prec \mathbf{F}$ or
$\mathbf{A} \prec \mathbf{F})$. We should seek these precise definitions
because sometimes both $\mathbf{X} \prec \mathbf{V}$ and
$\mathbf{P} \prec \mathbf{F}$ are true, in which case two people might
agree that an instance is a "zero day" without realizing that they
disagree on its definition. We can resolve these formally using our
model. This section extends prior work by one of the authors in
[@householder2015zeroday].

zero day vulnerability

:   Two common definitions for this term are in widespread use; a third
    is drawn from an important policy context. The two commonly-used
    definitions can be considered a relatively *low* threat level
    because they only involve states $q \in {xa}$ where no exploits are
    public and no attacks have occurred. We ordered all three
    definitions in approximately descending risk due to the expected
    duration until $\mathbf{D}$ can be achieved.

    1.  $q \in vp$ The United States [VEP]{acronym-label="VEP"
        acronym-form="singular+long"} [@usg2017vep] defines *zero day
        vulnerability* in a manner consistent with $q \in {vp}$. Further
        discussion appears in §[6.7](#sec:vep){reference-type="ref"
        reference="sec:vep"}.

    2.  ${vp} \xrightarrow{\mathbf{P}} {vP}$ when the vulnerability
        becomes public before the vendor is aware of it. Note that our
        model assumes that states in ${vP}$ are unstable and resolve to
        ${vP} \xrightarrow{\mathbf{V}} {VP}$ in the next step.

    3.  ${fp} \xrightarrow{\mathbf{P}} {fP}$ when the vulnerability
        becomes public before a fix is available, regardless of the
        vendor's awareness. Some states in ${fP}$---specifically, those
        in ${VfP}$---are closer to ${\mathbf{F}}$ (and therefore
        ${\mathbf{D}}$) occuring than others (i.e., ${vfP}$), thus this
        definition could imply less time spent at risk than the first.

zero day exploit

:   This term has three common definitions. Each can be considered a
    *moderate* threat level because they involve transition from
    ${xa} \xrightarrow{\mathbf{X}} {Xa}$. However, we ordered them in
    approximately descending risk due to the expected duration until
    $\mathbf{D}$ can be achieved.

    1.  ${vfdx} \xrightarrow{\mathbf{X}} {vfdX}$ when an exploit is
        released before the vendor is aware of the vulnerability.

    2.  ${fdx} \xrightarrow{\mathbf{X}} {fdX}$ when an exploit is
        released before a fix is available for the vulnerability.
        Because $\mathcal{Q}_{vf} \subset \mathcal{Q}_{f}$, any scenario
        matching the previous definition also matches this one.

    3.  ${px} \xrightarrow{\mathbf{X}} {pX}$ when an exploit is released
        before the public is aware of the vulnerability. Note that our
        model assumes that states in ${pX}$ are unstable and transition
        ${pX} \xrightarrow{\mathbf{P}} {PX}$ in the next step.

zero day attack

:   We have identified three common definitions of this term. Each can
    be considered a *high* threat level because they involve the
    $\mathbf{A}$ transition. However, we ordered them in approximately
    descending risk due to the expected duration until $\mathbf{D}$ can
    be achieved.

    1.  ${vfda} \xrightarrow{\mathbf{A}} {vfdA}$ when attacks against
        the vulnerability occur before the vendor is aware of the
        vulnerability.

    2.  ${fda} \xrightarrow{\mathbf{A}} {fdA}$ when attacks against the
        vulnerability occur before a fix is available for the
        vulnerability. As with *zero day exploit*, because
        $\mathcal{Q}_{vf} \subset \mathcal{Q}_{f}$, any scenario
        matching the previous definition also matches this one.

    3.  ${pa} \xrightarrow{\mathbf{A}} {pA}$ when attacks against the
        vulnerability occur before the public is aware of the
        vulnerability. Note that this definition disregards the vendor
        entirely since it makes no reference to either $\mathbf{V}$ or
        $\mathbf{F}$.

### Forever Day

In common usage, a *forever day* vulnerability is one that is expected
to remain unpatched indefinitely [@ars2012forever]. In other words, the
vulnerability is expected to remain in $d$ forever. This situation can
occur when deployed code is abandoned for a number of reasons,
including:

1.  The vendor has designated the product as [EoL]{acronym-label="EoL"
    acronym-form="singular+short"} and thereby declines to fix any
    further security flaws, usually implying $q \in {Vfd}$. Vendors
    should evaluate their support posture for [EoL]{acronym-label="EoL"
    acronym-form="singular+short"} products when they are aware of
    vulnerabilities in ${VfdX}$ or ${VfdA}$. Potential vendor responses
    include issuing additional guidance or an out-of-support patch.

2.  The vendor no longer exists, implying a state $q \in {vfd}$. Neither
    $\mathbf{F}$ nor $\mathbf{D}$ transitions can be expected although
    $\mathbf{P}$, $\mathbf{X}$, and $\mathbf{A}$ remain possible. For
    this reason alone, coordinators or other stakeholders may choose to
    publish anyway to cause $\mathbf{P}$. In this situation, if
    deployers are to respond at all, states in ${vfdP}$ are preferable
    to states in ${vfdp}$. Defender options in this case are usually
    limited to retiring or otherwise isolating affected systems,
    especially for vulnerabilities in either ${vfdPX}$ or ${vfdPA}$.

3.  The deployer chooses to never deploy, implying an expectation to
    remain in ${d}$ until the affected systems are retired or otherwise
    removed from service. This situation may be more common in
    deployments of safety-critical systems and [OT]{acronym-label="OT"
    acronym-form="singular+short"} than it is in [IT]{acronym-label="IT"
    acronym-form="singular+short"} deployments. It is also the most
    reversible of the three *forever day* scenarios, because the
    deployer can always reverse their decision as long as a fix is
    available ($q \in {VF}$). In deployment environments where other
    mitigations are in place and judged to be adequate, and where the
    risk posed by $\mathbf{X}$ and/or $\mathbf{A}$ are perceived to be
    low, this can be a reasonable strategy within a
    [VM]{acronym-label="VM" acronym-form="singular+short"} program.

Scenarios in which the vendor has chosen not to develop a patch for an
otherwise supported product, and which also imply $q \in {Vfd}$, are
omitted from the above definition because as long as the vendor exists
the choice to not develop a fix remains reversible. That said, such
scenarios most closely follow the first bullet in the list above.

## Vulnerability Response Situation Awareness {#sec:situation_awareness}

In this section, we demonstrate how the model can be applied to improve
situation awareness for coordinating parties and other stakeholders.

##### SSVC v2.0 {#sec:ssvc}

::: {#tab:ssvc_v2_states}
       States       SSVC Decision Point            SSVC Value
  ---------------- --------------------- ------------------------------
        $xa$           Exploitation                   None
        $Xa$           Exploitation          PoC (Proof of Concept)
        $A$            Exploitation                  Active
        $p$            Report Public                   No
        $P$            Report Public                  Yes
        $V$         Supplier Contacted                Yes
        $v$         Supplier Contacted    No (but see text for caveat)
        $p$         Public Value Added             Precedence
   $VFdp$ or $dP$   Public Value Added             Ampliative
       $VFP$        Public Value Added              Limited

  : Mapping Subsets of States $\mathcal{Q}$ to SSVC v2.0
:::

Vulnerability prioritization schemes such as SSVC
[@spring2019ssvc; @spring2020ssvc; @spring2021ssvc] generally give
increased priority to states in higher threat levels, corresponding to
$q \in \mathcal{Q}_X \cup \mathcal{Q}_A$. SSVC also includes decision
points surrounding other states in our model. A summary of the relevant
SSVC decision points and their intersection with our model is given in
Table [6.4](#tab:ssvc_v2_states){reference-type="ref"
reference="tab:ssvc_v2_states"}.

Not all SSVC decision point values map as clearly onto states in this
model however. For example, *Supplier Contacted=No* likely means
$q \in \mathcal{Q}_{v}$ but it is possible that the vendor has found out
another way, so one cannot rule out $q \in \mathcal{Q}_{V}$ on this
basis alone. However, notifying the vendor yourself forces you into
$q \in \mathcal{Q}_{V}$. Therefore it is always in the coordinator's
interest to encourage, facilitate, or otherwise cause the vendor to be
notified.

Other SSVC decision points may be informative about which transitions to
expect in a case. Two examples apply here: First, *Supplier Engagement*
acts to gauge the likelihood of the $\mathbf{F}$ transitions.
Coordination becomes more necessary the lower that likelihood is.
Second, *Utility* (the usefulness of the exploit to the adversary) acts
to gauge the likelihood of the $\mathbf{A}$ transition.

##### Mapping to CVSS v3.1 {#sec:cvss}

[CVSS]{acronym-label="CVSS" acronym-form="singular+short"} version 3.1
includes a few Temporal Metric variables that connect to this model
[@first2019cvss31]. Unfortunately, differences in abstraction between
the models leaves a good deal of ambiguity in the translation. Table
[6.5](#tab:cvss_31){reference-type="ref" reference="tab:cvss_31"} shows
the relationship between the two models.

::: {#tab:cvss_31}
   States   [CVSS]{acronym-label="CVSS" acronym-form="singular+short"} v3.1 Temporal Metric  [CVSS]{acronym-label="CVSS" acronym-form="singular+short"} v3.1 Temporal Metric Value(s)
  -------- --------------------------------------------------------------------------------- ------------------------------------------------------------------------------------------
   ${XA}$                                  Exploit Maturity                                  High (H), or Functional (F)
   ${X}$                                   Exploit Maturity                                  High (H), Functional (F), or Proof-of-Concept (P)
   ${x}$                                   Exploit Maturity                                  Unproven (U) or Not Defined (X)
   ${Vf}$                                  Remediation Level                                 Not Defined (X), Unavailable (U), Workaround (W), or Temporary Fix (T)
   ${VF}$                                  Remediation Level                                 Temporary Fix (T) or Official Fix (O)

  : Mapping Subsets of States $\mathcal{Q}$ to
  [CVSS]{acronym-label="CVSS" acronym-form="singular+short"} v3.1
:::

##### Addressing Uncertainty in Situation Awareness

It is possible to use this model to infer what other decisions can be
made based on incomplete information about a case. For example, imagine
that a vendor just found out about a vulnerability in a product and has
taken no action yet. We know they are in ${Vf}$, but that leaves 8
possible states for the case to be in: $$\begin{aligned}
    {Vf} = \{ & {Vfdpxa}, {VfdPxa}, {VfdpXa}, \\ 
              & {VfdpxA}, {VfdPXa}, {VfdpXA}, \\
              & {VfdPxA}, {VfdPXA} \}
\end{aligned}$$

Can we do better than simply assigning equal likelihood
$p(q|Vf) = 0.125$ to each of these states? Yes: we can use the PageRank
computations from Table
[3.4](#tab:allowed_state_transitions){reference-type="ref"
reference="tab:allowed_state_transitions"} to inform our estimates.

To assess our presence in ${Vf}$, we can select just the subset of
states we are interested in. But our PageRank values are computed across
all 32 states and we are only interested in the relative probabilities
within a subset of 8 states. Thus, we normalize the PageRank for the
subset to find the results shown in Table
[6.6](#tab:pagerank_vf){reference-type="ref"
reference="tab:pagerank_vf"}. As a result, we find that the most likely
state in ${Vf}$ is ${VfdPXA}$ with probability $0.24$, nearly twice what
we would have expected ($1/8 = 0.125$) if we just assumed each state was
equally probable.

::: {#tab:pagerank_vf}
    State     PageRank   Normalized
  ---------- ---------- ------------
   $VfdPXA$    0.063       0.245
   $VfdPXa$    0.051       0.200
   $VfdPxa$    0.037       0.146
   $VfdPxA$    0.032       0.126
   $Vfdpxa$    0.031       0.120
   $VfdpxA$    0.020       0.078
   $VfdpXa$    0.011       0.044
   $VfdpXA$    0.010       0.040

  : PageRank and normalized state probabilities for states in ${Vf}$
:::

## [VEP]{acronym-label="VEP" acronym-form="singular+full"} {#sec:vep}

The [VEP]{acronym-label="VEP" acronym-form="singular+full"} is the
United States government's process to decide whether to inform vendors
about vulnerabilities they have discovered. The
[VEP]{acronym-label="VEP" acronym-form="singular+short"} Charter
[@usg2017vep] describes the process:

> The Vulnerabilities Equities Process (VEP) balances whether to
> disseminate vulnerability information to the vendor/supplier in the
> expectation that it will be patched, or to temporarily restrict the
> knowledge of the vulnerability to the USG, and potentially other
> partners, so that it can be used for national security and law
> enforcement purposes, such as intelligence collection, military
> operations, and/or counterintelligence.

For each vulnerability that enters the process, the
[VEP]{acronym-label="VEP" acronym-form="singular+short"} results in a
decision to *disseminate* or *restrict* the information.

In terms of our model:

disseminate

:   is a decision to notify the vendor, thereby triggering the
    transition
    $\mathcal{Q}_{v} \xrightarrow{\mathbf{V}} \mathcal{Q}_{V}$.

restrict

:   is a decision not to notify the vendor and remain in
    $\mathcal{Q}_{v}$.

[VEP]{acronym-label="VEP" acronym-form="singular+short"} policy does not
explicitly touch on any other aspect of the [CVD]{acronym-label="CVD"
acronym-form="singular+short"} process. By solely addressing
$\mathbf{V}$, [VEP]{acronym-label="VEP" acronym-form="singular+short"}
is mute regarding intentionally triggering the $\mathbf{P}$ or
$\mathbf{X}$ transitions. It also makes no commitments about
$\mathbf{F}$ or $\mathbf{D}$, although obviously these are entirely
dependent on $\mathbf{V}$ having occurred. However, preserving the
opportunity to exploit the vulnerability implies a chance that such use
would be observed by others, thereby resulting in the $\mathbf{A}$
transition.

The charter sets the following scope requirement as to which
vulnerabilities are eligible for [VEP]{acronym-label="VEP"
acronym-form="singular+short"}:

> To enter the process, a *vulnerability* must be both *newly
> discovered* and not *publicly known*

given the following definitions (from Annex A of [@usg2017vep])

Newly Discovered

:   After February 16, 2010, the effective date of the initial
    Vulnerabilities Equities Process, when the USG discovers a zero-day
    vulnerability or new zero-day vulnerability information, it will be
    considered newly discovered. This definition does NOT preclude entry
    of vulnerability information discovered prior to February 16, 2010.

Publicly known

:   A vulnerability is considered publicly known if the vendor is aware
    of its existence and/or vulnerability information can be found in
    the public domain (e.g., published documentation, Internet, trade
    journals).

Vulnerability

:   A weakness in an information system or its components (e.g., system
    security procedures, hardware design, internal controls) that could
    be exploited or impact confidentiality, integrity, or availability
    of information.

Zero-Day Vulnerability

:   A type of vulnerability that is unknown to the vendor, exploitable,
    and not publicly known.

Mapping back to our model, the [VEP]{acronym-label="VEP"
acronym-form="singular+short"} definition of *newly discovered* hinges
on the definition of *zero day vulnerability*. The policy is not clear
what distinction is intended by the use of the term *exploitable* in the
*zero day vulnerability* definition, as the definition of
*vulnerability* includes the phrase "could be exploited,\" seeming to
imply that a non-exploitable vulnerability might fail to qualify as a
*vulnerability* altogether. Regardless, "unknown to the vendor" clearly
matches with $\mathcal{Q}_{v}$, and "not publicly known" likewise
matches with $\mathcal{Q}_{p}$. Thus we interpret their definition of
*newly discovered* to be consistent with $q \in {vp}$.

[VEP]{acronym-label="VEP" acronym-form="singular+short"}'s definition of
*publicly known* similarly specifies either "vendor is aware"
($\mathcal{Q}_{V}$) or "information can be found in the public domain"
($\mathcal{Q}_{P}$). As above, the logical negation of these two
criteria puts us back in $q \in {vp}$ since
${vp} = \lnot \mathcal{Q}_{V} \cap \lnot \mathcal{Q}_{P}$. We further
note that because a public exploit ($\mathcal{Q}_X$) would also meet the
definition of "vulnerability information in the public domain," we can
narrow the scope from ${vp}$ to ${vpx}$. Lastly, we note that due to the
vendor fix path causality rule in Eq.
[\[eq:history_vfd_rule\]](#eq:history_vfd_rule){reference-type="eqref"
reference="eq:history_vfd_rule"}, ${vpx}$ is equivalent to ${vfdpx}$,
and therefore we can formally specify that [VEP]{acronym-label="VEP"
acronym-form="singular+short"} is only applicable to vulnerabilities in

$$\mathcal{S}_{VEP} = {vfdpx} = \{vfdpxa, vfdpxA\}$$

Vulnerabilities in any other state by definition should not enter into
the [VEP]{acronym-label="VEP" acronym-form="singular+long"}, as the
first transition from ${vfdpx}$ (i.e., $\mathbf{V}$, $\mathbf{P}$, or
$\mathbf{X}$) exits the inclusion criteria. However it is worth
mentioning that the utility of a vulnerability for offensive use
continues throughout $\mathcal{Q}_d$, which is a considerably larger
subset of states than ${vfdpx}$ ($|\mathcal{Q}_d| = 24$,
$|\mathcal{Q}_{vfdpx}| = 2$).

## Recommended Action Rules for [CVD]{acronym-label="CVD" acronym-form="singular+short"} {#sec:cvd_action_rules}

Another application of this model is to recommend actions for
coordinating parties in [CVD]{acronym-label="CVD"
acronym-form="singular+short"} based on the subset of states that
currently apply to a case. What a coordinating party does depends on
their role and where they engage, as shown in the list below. As
described in §[6.2](#sec:mpcvd){reference-type="ref"
reference="sec:mpcvd"}, [MPCVD]{acronym-label="MPCVD"
acronym-form="singular+short"} attempts to synchronize state transitions
across vendors.

A significant portion of [CVD]{acronym-label="CVD"
acronym-form="singular+long"} can be formally described as a set of
action rules based on this model. For our purposes, a
[CVD]{acronym-label="CVD" acronym-form="singular+short"} action rule
consists of:

State subset

:   The subset of states $Q \in \mathcal{Q}$ from which the action may
    be taken

Role(s)

:   The role(s) capable of performing the action

Action

:   A summary of the action to be taken

Reason

:   The rationale for taking the action

Transition

:   The state transition event $\sigma \in \Sigma$ induced by the action
    (if any)

This rule structure follows a common user story pattern:

> When a case is in a state $q \in Q \subseteq \mathcal{Q}$, a *Role*
> can do *Action* for *Reason*, resulting in the transition event
> $\sigma \in \Sigma$

The list in Table [6.7](#tab:cvd_rules){reference-type="ref"
reference="tab:cvd_rules"} can be built into a rules engine that
translates each state in the model to a set of suggested
[CVD]{acronym-label="CVD" acronym-form="singular+short"} actions.

::: {#tab:cvd_rules}
        State Subset       Role(s)            Action                                                       Reason                                            $\sigma$
  ------------------------ ------------------ ------------------------------------------------------------ ---------------------------------------------- --------------
   Continued on next page                                                                                                                                 
            $P$            any                Terminate any existing embargo                               Exit criteria met                                    \-
            $X$            any                Terminate any existing embargo                               Exit criteria met                                    \-
            $A$            any                Terminate any existing embargo                               Exit criteria met                                    \-
            $x$            any                Monitor for exploit publication                              SA                                                   \-
            $X$            any                Monitor for exploit refinement                               SA                                                   \-
            $a$            any                Monitor for attacks                                          SA                                                   \-
            $A$            any                Monitor for additional attacks                               SA                                                   \-
           $vfdP$          vendor             Pay attention to public reports                              SA                                              $\mathbf{V}$
            $pX$           any                Draw attention to published exploit(s)                       SA                                              $\mathbf{P}$
            $PX$           any                Draw attention to published exploit(s)                       SA                                              $\mathbf{P}$
           $pxa$           any                Maintain vigilance for embargo exit criteria                 SA                                                   \-
           $VfdP$          any                Escalate vigilance for exploit publication or attacks        SA, Coordination                                     \-
            $X$            any                Publish detection(s) for exploits                            Detection                                       $\mathbf{P}$
            $A$            any                Publish detection(s) for attacks                             Detection                                       $\mathbf{P}$
            $Vp$           any                Publish vul and any mitigations (if no active embargo)       Defense                                         $\mathbf{P}$
           $fdP$           any                Publish mitigations                                          Defense                                              \-
            $pX$           any                Publish vul and any mitigations                              Defense                                         $\mathbf{P}$
            $PX$           any                Publish vul and any mitigations                              Defense                                         $\mathbf{P}$
            $pA$           any                Publish vul and any mitigations                              Defense                                         $\mathbf{P}$
           $VfdP$          any                Publish mitigations                                          Defense                                              \-
           $vfdp$          any                Publish vul and any mitigations (if no vendor exists)        Defense                                         $\mathbf{P}$
           $VfdP$          any                Ensure any available mitigations are publicized              Defense                                              \-
           $Vfd$           vendor             Create fix                                                   Defense                                         $\mathbf{F}$
           $VFdp$          vendor, deployer   Deploy fix (if possible)                                     Defense                                         $\mathbf{D}$
           $VFdP$          deployer           Deploy fix                                                   Defense                                         $\mathbf{D}$
          $fdPxA$          any                Publish exploit code                                         Defense, Detection                              $\mathbf{X}$
          $VFdPxa$         any                Publish exploit code                                         Defense, Detection, Accelerate deployment       $\mathbf{X}$
           $vfd$           non-vendor         Notify vendor                                                Coordination                                    $\mathbf{V}$
            $dP$           any                Escalate response priority among responding parties          Coordination                                         \-
            $dX$           any                Escalate response priority among responding parties          Coordination                                         \-
            $dA$           any                Escalate response priority among responding parties          Coordination                                         \-
           $Vfd$           non-vendor         Encourage vendor to create fix                               Coordination                                         \-
           $pxa$           any                Maintain any existing disclosure embargo                     Coordination                                         \-
           $dpxa$          any                Negotiate or establish disclosure embargo                    Coordination                                         \-
           $VfdP$          non-vendor         Escalate fix priority with vendor                            Coordination                                         \-
           $Vfdp$          non-vendor         Publish vul                                                  Coordination, Motivate vendor to fix            $\mathbf{P}$
           $Vfdp$          any                Publish vul                                                  Coordination, Motivate deployers to mitigate    $\mathbf{P}$
           $VFdp$          non-vendor         Encourage vendor to deploy fix (if possible)                 Coordination                                         \-
          $VFdpxa$         any                Scrutinize appropriateness of initiating a new embargo       Coordination                                         \-
           $VFdp$          any                Publish vul and fix details                                  Accelerate deployment                           $\mathbf{P}$
           $VFdP$          any                Promote fix deployment                                       Accelerate deployment                                \-
           $VFDp$          any                Publish vulnerability                                        Document for future reference                   $\mathbf{P}$
           $VFDp$          any                Publish vulnerability                                        Acknowledge contributions                       $\mathbf{P}$
           $fdxa$          any                Discourage exploit publication until at least $\mathbf{F}$   Limit attacker advantage                             \-
          $vfdpx$          US Gov't           Initiate VEP (if applicable)                                 Policy                                               \-
          $VFDPXA$         any                Close case                                                   No action required                                   \-
          $VFDPxa$         any                Close case (unless monitoring for X or A)                    No action required                                   \-
          $VFDPXa$         any                Close case (unless monitoring for A)                         No action required                                   \-
          $VFDPxA$         any                Close case (unless monitoring for X)                         No action required                                   \-

  : [CVD]{acronym-label="CVD" acronym-form="singular+short"} Action
  Rules based on States
:::

# Related Work {#sec:related_work}

Numerous models of the vulnerability life cycle and
[CVD]{acronym-label="CVD" acronym-form="singular+short"} have been
proposed. Arbaugh, Fithen, and McHugh provide a descriptive model of the
life cycle of vulnerabilities from inception to attacks and remediation
[@arbaugh2000windows], which we refined with those of Frei et al.
[@frei2010modeling], and Bilge and et al. [@bilge2012before] to form the
basis of this model as described in
§[2.1](#sec:events){reference-type="ref" reference="sec:events"}. We
also found Lewis' literature review of vulnerability lifecycle models to
be useful [@lewis2017global].

Prescriptive models of the [CVD]{acronym-label="CVD"
acronym-form="singular+short"} process have also been proposed. Christey
and Wysopal's 2002 IETF draft laid out a process for responsible
disclosure geared towards prescribing roles, responsibilities for
researchers, vendors, customers, and the security community
[@christey2002responsible]. The NIAC Vulnerability Disclosure Framework
also prescribed a process for coordinating the disclosure and
remediation of vulnerabilities [@niac2004vul]. The CERT Guide to
Coordinated Vulnerability Disclosure provides a practical overview of
the [CVD]{acronym-label="CVD" acronym-form="singular+short"} process
[@householder2017cert]. ISO/IEC 29147 describes standard
externally-facing processes for vulnerability disclosure from the
perspective of a vendor receiving vulnerability reports , while ISO/IEC
30111 describes internal vulnerability handling processes within a
vendor [@ISO29147; @ISO30111]. The [FIRST]{acronym-label="FIRST"
acronym-form="singular+full"} *[PSIRT]{acronym-label="PSIRT"
acronym-form="singular+short"} Services Framework* provides a practical
description of the capabilities common to vulnerability response within
vendor organizations [@first2020psirt]. The
[FIRST]{acronym-label="FIRST" acronym-form="singular+short"} *Guidelines
and Practices for Multi-Party Vulnerability Coordination and Disclosure*
provides a number of scenarios for [MPCVD]{acronym-label="MPCVD"
acronym-form="singular+short"} [@first2020mpcvd]. Many of these
scenarios can be mapped directly to the histories $h \in H$ described in
§[6.2](#sec:mpcvd){reference-type="ref" reference="sec:mpcvd"}.

Benchmarking [CVD]{acronym-label="CVD" acronym-form="singular+short"}
capability is the topic of the [VCMM]{acronym-label="VCMM"
acronym-form="singular+short"} from Luta Security [@luta2020]. The
[VCMM]{acronym-label="VCMM" acronym-form="singular+short"} addresses
five capability areas: organizational, engineering, communications,
analytics, and incentives. Of these, our model is perhaps most relevant
to the analytics capability, and the metrics described in
§[5](#sec:skill_luck){reference-type="ref" reference="sec:skill_luck"}
could be used to inform an organization's assessment of progress in this
dimension. Concise description of case states using the model presented
here could also be used to improve the communications dimension of the
[VCMM]{acronym-label="VCMM" acronym-form="singular+short"}.

System dynamics and agent based models have been applied to the
interactions between the vulnerability discovery, disclosure, and
remediation processes. Ellis et al. analyzed the composition of the
labor market for bug bounty programs, finding that a small core of
high-volume reporters earn most of the bounties while a much larger
group are infrequent low-volume reporters [@ellis2018fixing]. Lewis
modeled the interaction of social and economic factors in the global
vulnerability discovery and disclosure system [@lewis2017global]. The
key systemic themes identified include:

> Perception of Punishment; Vendor Interactions; Disclosure Stance;
> Ethical Considerations; Economic factors for Discovery and Disclosure
> and Emergence of New Vulnerability Markets

Moore and Householder modeled cooperative aspects of the
[MPCVD]{acronym-label="MPCVD" acronym-form="singular+short"} process,
noting, \"it appears that adjusting the embargo period to increase the
likelihood that patches can be developed by most vendors just in time is
a good strategy for reducing cost\"[@moore2019multi].

Economic analysis of [CVD]{acronym-label="CVD"
acronym-form="singular+short"} has also been done. Arora et al. explored
the [CVD]{acronym-label="CVD" acronym-form="singular+short"} process
from an economic and social welfare
perspective [@arora2005economics; @arora2006does; @arora2006research; @arora2008optimal; @arora2010competition; @arora2010empirical].
More recently, so did Silfversten [@silfversten2018economics]. Cavusoglu
and Cavusoglu model the mechanisms involved in motivating vendors to
produce and release patches [@cavusoglu2007efficiency]. Ellis et al.
examined the dynamics of labor market for bug bounties both within and
across [CVD]{acronym-label="CVD" acronym-form="singular+short"} programs
[@ellis2018fixing]. Pupillo et al. explored the policy implications of
[CVD]{acronym-label="CVD" acronym-form="singular+short"} in Europe
[@pupillo2018software]. A model for prioritizing vulnerability response
that considers $\mathbf{X}$ and $\mathbf{A}$, among other impact
factors, can be found in Spring et al. [@spring2020ssvc].

Other work has examined the timing of events in the lifecycle, sometimes
with implications for forecasting. Ozment and Schechter examined the
rate of vulnerability reports as software ages [@ozment2006milk]. Bilge
and Dumitraş studied 18 vulnerabilities in which
${pa} \xrightarrow{\mathbf{A}} {pA} \xrightarrow{\mathbf{P}} {PA}$,
finding a lag of over 300 days [@bilge2012before]. Jacobs et al.
proposed an Exploit Prediction Scoring System [@jacobs2020epss], which
could provide insight into the relative frequencies of $$\begin{aligned}
{vfda} \xrightarrow{\mathbf{V}} {Va} \xrightarrow{\mathbf{A}} {VA}
&\textrm{ vs. } 
{vfda} \xrightarrow{\mathbf{A}} {vA} \xrightarrow{\mathbf{V}} {VA} \\
{fda} \xrightarrow{\mathbf{F}} {Fa} \xrightarrow{\mathbf{A}} {FA} 
&\textrm{ vs. } 
{fda} \xrightarrow{\mathbf{A}} {fA} \xrightarrow{\mathbf{F}} {FA}
\end{aligned}$$ and possibly other transitions.

Future work might apply similar measurements of state subset populations
over time to put better bounds on state transition probabilities than
our simplified assumption of uniformity. Some possible starting points
for such analysis follow.

Householder et al. found that only about 5% of vulnerabilities have
public exploits available via commodity tools. However, for those that
do, the median lag between transitions in
${px} \xrightarrow{\mathbf{P}} {Px} \xrightarrow{\mathbf{X}} {PX}$ was 2
days [@householder2020historical].

Frei et al. describe the timing of many of the events here, including
$\mathbf{F}$, $\mathbf{D}$, $\mathbf{X}$, $\mathbf{P}$, and the elapsed
time between them for the period 2000-2007 across a wide swath of
industry [@frei2010modeling]. Their analysis finds that
${px} \xrightarrow{\mathbf{X}} {pX} \xrightarrow{\mathbf{P}} {PX}$ in
15% of the vulnerabilities they analyzed, leaving 85% on the
${px} \xrightarrow{\mathbf{P}} {Px} \xrightarrow{\mathbf{X}} {PX}$ path.
Similarly, they report that a patch is available on or before the date
of public awareness in 43% of vulnerabilities. In other words, they find
that ${fp} \xrightarrow{\mathbf{F}} {Fp} \xrightarrow{\mathbf{P}} {FP}$
43% of the time, implying that
${fp} \xrightarrow{\mathbf{P}} {fP} \xrightarrow{\mathbf{F}} {FP}$ 57%
of the time.

# Limitations and Future Work {#sec:limitationsAnd}

This section highlights some limitations of the current work and lays
out a path for improving on those limitations in future work. Broadly,
the opportunities for expanding the model include

-   addressing the complexities of tracking [CVD]{acronym-label="CVD"
    acronym-form="singular+short"} and [MPCVD]{acronym-label="MPCVD"
    acronym-form="singular+short"} cases throughout their lifecycle

-   addressing the importance of both state transition probabilities and
    the time interval between them

-   options for modeling attacker behavior

-   modeling multiple agents

-   gathering more data about [CVD]{acronym-label="CVD"
    acronym-form="singular+short"} in the world

-   managing the impact of partial information

-   working to account for fairness and the complexity of
    [MPCVD]{acronym-label="MPCVD" acronym-form="singular+short"}

## State Explosion

Although our discussion of [MPCVD]{acronym-label="MPCVD"
acronym-form="singular+short"} in
§[6.2](#sec:mpcvd){reference-type="ref" reference="sec:mpcvd"} and
§[6.2.2](#sec:mpcvd criteria){reference-type="ref"
reference="sec:mpcvd criteria"} highlights one area in which the number
of states to track can increase dramatically, an even larger problem
could arise in the context of [VM]{acronym-label="VM"
acronym-form="singular+full"} efforts even within normal
[CVD]{acronym-label="CVD" acronym-form="singular+short"} cases. Our
model casts each event $\sigma \in \Sigma$ as a singular point event,
even though some---such as fix deployed $\mathbf{D}$---would be more
accurately described as diffusion or multi-agent processes.

That is, by the time a vulnerability case reaches the point of
remediating individual instances of vulnerable deployments, every such
instance has its own state to track in regards to whether $\mathbf{D}$
has occurred yet. To apply this model to real world observations, it may
be pragmatic to adapt the event definition to include some defined
threshold criteria.

However, this problem is equivalent to an existing problem in
[VM]{acronym-label="VM" acronym-form="singular+short"} practice: how
best to address the question of whether the fix for a vulnerability has
been deployed across the enterprise. Many organizations find a fixed
quantile [SLE]{acronym-label="SLE" acronym-form="singular+short"} to be
a reasonable approach. For example, a stakeholder might set the
[SLE]{acronym-label="SLE" acronym-form="singular+short"} that 80% of
known vulnerable systems will be patched within a certain timeframe.
Other organizations might track fix deployments by risk groups, for
example by differentiating between end user systems, servers, and
network infrastructure. They then could observe the deployed fix ratio
for their constituency and mark the event $\mathbf{D}$ as having
occurred when certain thresholds are reached. Nothing in our model
precludes those sorts of roll-up functions from being applied.

## The Model Does Not Address Transition Probabilities

Although we posit a skill-less baseline in which each transition is
equally likely whenever possible within the model, it is a reasonable
criticism to point out that some transitions may be expected to change
conditional on a history already in progress.

For example, many people believe that the publication of exploits
increases the likelihood of attacks. Our model moves toward making this
a testable hypothesis: Does
$p(\mathbf{A}|q \in \mathcal{Q}_X) > p(\mathbf{A}|q \in  \mathcal{Q}_x)$
over some set of cases? Other such hypotheses can be framed in terms of
the model.

Does making vulnerabilities public prior to fix readiness increase
attacks? $$p(\mathbf{A}|q \in fP) > p(\mathbf{A}|q \in FP)?$$ Does
notifying vendors prior to making vulnerability information public
increase the likelihood that fixes will be deployed before attacks are
observed?
$$p(\mathbf{D} \prec \mathbf{A}|\mathbf{V} \prec \mathbf{P}) > p(\mathbf{D} \prec \mathbf{A}|\mathbf{P} \prec \mathbf{V})?$$
The novelty here is not that these questions could not be asked or
answered previously. Rather, it is that the formalism of our model
allows them to be stated concisely and measured in terms of 6 events
$\sigma \in \Sigma$, which points directly to the usefulness of
collecting data about those events as part of ongoing
[CVD]{acronym-label="CVD" acronym-form="singular+short"} (including
[MPCVD]{acronym-label="MPCVD" acronym-form="singular+short"}) practices.

## The Model Does Not Achieve a Total Order Over Histories

As described in §[4.4](#sec:h_poset_skill){reference-type="ref"
reference="sec:h_poset_skill"}, some ambiguity remains regarding
preferences for elements of $\mathbb{D}$. These preferences would need
to be addressed before the model can achieve a total order over
histories $\mathcal{H}$. Specifically, we need to decide whether it is
preferable

-   that Fix Ready precede Exploit Publication
    ($\mathbf{F} \prec \mathbf{X}$) or that Vendor Awareness precede
    Public Awareness ($\mathbf{V} \prec \mathbf{P}$)

-   that Public Awareness precede Exploit Publication
    ($\mathbf{P} \prec \mathbf{X}$) or that Exploit Publication Precede
    Attacks ($\mathbf{X} \prec \mathbf{A}$)

-   that Public Awareness precede Attacks
    ($\mathbf{P} \prec \mathbf{A}$) or Vendor Awareness precede Exploit
    Publication ($\mathbf{V} \prec \mathbf{X}$)

We look forward to the ensuing "would you rather\...?" discussions.

## The Model Has No Sense of Timing

There is no concept of time in this model, but delays between events can
make a big difference in history results. Two cases in which
$\mathbf{F} \prec \mathbf{A}$ would be quite different if the time gap
between these two events was 1 week versus 3 months, as this gap
directly bears on the need for speed in deploying fixes. Organizations
may wish to extend this model by setting timing expectations in addition
to simple precedence preferences. For example, organizations may wish to
specify [SLEs]{acronym-label="SLE" acronym-form="plural+short"} for
$\mathbf{V} \prec \mathbf{F}$, $\mathbf{F} \prec \mathbf{D}$,
$\mathbf{F} \prec \mathbf{A}$, and so forth.

Furthermore, in the long run the elapsed time for
$\mathbf{F} \prec \mathbf{A}$ essentially dictates the response time
requirements for [VM]{acronym-label="VM" acronym-form="singular+full"}
processes for system owners. Neither system owners nor vendors get to
choose when attacks happen, so we should expect stochasticity to play a
significant role in this timing. However, if an organization cannot
consistently achieve a shorter lag between $\mathbf{F}$ and $\mathbf{D}$
than between $\mathbf{F}$ and $\mathbf{A}$ (i.e., achieving
$\mathbf{D} \prec \mathbf{A}$) for a sizable fraction of the
vulnerability cases they encounter, it's difficult to imagine that
organization being satisfied with the effectiveness of their
[VM]{acronym-label="VM" acronym-form="singular+short"} program.

## Attacks As Random Events

In the model presented here, attacks are modeled as random events.
However, attacks are not random. At an individual or organization level,
attackers are intelligent adversaries and can be expected to follow
their own objectives and processes to achieve their ends.

Modeling the details of various attackers is beyond the scope of this
model. Thus we believe that a stochastic approach to adversarial actions
is reasonable from the perspective of a vendor or system owner.
Furthermore, if attacks were easily predicted, we would be having a very
different conversation.

## Modeling Multiple Agents

We agree with the reviewer who suggested that an agent-based model could
allow deeper examination of the interactions between stakeholders in
[MPCVD]{acronym-label="MPCVD" acronym-form="singular+short"}. Many of
the mechanisms and proximate causes underlying the events this model
describes are hidden from the model, and would be difficult to observe
or measure even if they were included.

Nevertheless, to reason about different stakeholders' strategies and
approaches to MPCVD, we need a way to measure and compare outcomes. The
model we present here gives us such a framework, but it does so by
making a tradeoff in favor of generality over causal specificity. We
anticipate that future agent-based models of
[MPCVD]{acronym-label="MPCVD" acronym-form="singular+short"} will be
better positioned to address process mechanisms, whereas this model will
be useful to assess outcomes independently of the mechanisms by which
they arise.

## Gather Data About CVD

§[6.1](#sec:benchmarks){reference-type="ref" reference="sec:benchmarks"}
discusses how different benchmarks and "reasonable baseline
expectations" might change the results of a skill assessment. It also
proposes how to use observations of the actions a certain team or team
performs to create a baseline which compares other
[CVD]{acronym-label="CVD" acronym-form="singular+short"} practitioners
to the skill of that team or teams. Such data could also inform causal
reasoning about certain event orderings and help identify effective
interventions. For example, might causing $\mathbf{X} \prec \mathbf{F}$
be an effective method to improve the chances of
$\mathbf{D} \prec \mathbf{A}$ in cases where the vendor is slow to
produce a fix? Whether it is better to compare the skill of a team to
blind luck via the i.i.d. assumption or to other teams via measurement
remains an open question.

To address questions such as this, future research efforts must collect
and collate a large amount of data about the timing sequences of events
in the model for a variety of stakeholder groups and a variety of
vulnerabilities. Deeper analysis using joint probabilities could then
continue if the modeling choice is to base skill upon a measure from
past observations.

While there is a modeling choice about using the uniformity assumption
versus observations from past [CVD]{acronym-label="CVD"
acronym-form="singular+short"} (see
§[6.1](#sec:benchmarks){reference-type="ref"
reference="sec:benchmarks"}), the model does not depend on whether the
uniformity assumption actually holds. We have provided a means to
calculate from observations a deviation from the desired "reasonable
baseline," whether this is based on the i.i.d. assumption or not.
Although, via our research questions, we have provided a method for
evaluating skill in [CVD]{acronym-label="CVD"
acronym-form="singular+short"}, evaluating the overarching question of
*fairness* in [MPCVD]{acronym-label="MPCVD"
acronym-form="singular+short"} requires a much broader sense of
[CVD]{acronym-label="CVD" acronym-form="singular+short"} practices.

## Observation May Be Limited

Not all events $\sigma \in \Sigma$, and therefore not all desiderata
$d \in \mathbb{D}$, will be observable by all interested parties. But in
many cases at least some are, which can still help to infer reasonable
limits on the others, as shown in
§[\[sec:inferring_history\]](#sec:inferring_history){reference-type="ref"
reference="sec:inferring_history"}.

Vendors are in a good position to observe most of the events in each
case. This is even more so if they have good sources of threat
information to bolster their awareness of the $\mathbf{X}$ and
$\mathbf{A}$ events. A vigilant public can also be expected to
eventually observe most of the events, although $\mathbf{V}$ might not
be observable unless vendors, researchers, and/or coordinators are
forthcoming with their notification timelines (as many increasingly
are). $\mathbf{D}$ is probably the hardest event to observe for all
parties, for the reasons described in the timing discussion above.

## [CVD]{acronym-label="CVD" acronym-form="singular+short"} Action Rules Are Not Algorithms

The rules given in §[6.8](#sec:cvd_action_rules){reference-type="ref"
reference="sec:cvd_action_rules"} are not algorithms. We do not propose
them as a set of required actions for every [CVD]{acronym-label="CVD"
acronym-form="singular+short"} case. However, following Atul Gawande's
lead, we offer them as a mechanism to generate [CVD]{acronym-label="CVD"
acronym-form="singular+short"} checklists:

> Good checklists, on the other hand are precise. They are efficient, to
> the point, and easy to use even in the most difficult situations. They
> do not try to spell out everything--a checklist cannot fly a plane.
> Instead, they provide reminders of only the most critical and
> important steps--the ones that even the highly skilled professional
> using them could miss. Good checklists are, above all, practical
> [@gawande2011checklist].

## [MPCVD]{acronym-label="MPCVD" acronym-form="singular+short"} Criteria Do Not Account for Equitable Resilience

The proposed criteria for [MPCVD]{acronym-label="MPCVD"
acronym-form="singular+short"} in
§[6.2.2](#sec:mpcvd criteria){reference-type="ref"
reference="sec:mpcvd criteria"} fail to account for either user
populations or their relative importance. For example, suppose an
[MPCVD]{acronym-label="MPCVD" acronym-form="singular+short"} case had a
total of 15 vendors, with 5 vendors representing 95% of the total
userbase achieving highly preferred outcomes and 10 vendors with poor
outcomes representing the remaining 5% of the userbase. The desired
criteria (high median $\alpha$ score with low variance) would likely be
unmet even though most users were protected.

Similarly, a smaller set of vendor/product pairs might represent a
disproportionate concentration of the total risk posed by a
vulnerability.[^12] Again, aggregation across all vendor/product pairs
could be misleading. In fact, risk concentration within a particular
user population may lead to a need for strategies that appear
inequitable at the vendor level while achieving greater outcome equity
at a larger scale.

The core issue is that we lack a utility function to map from observed
case histories to harm reduction.[^13] Potential features of such a
function include aggregation across vendors and/or users. Alternatively,
it may be possible to devise a method for weighting the achieved
histories in an [MPCVD]{acronym-label="MPCVD"
acronym-form="singular+short"} case by some proxy for total user risk.
Other approaches remain possible---for example, employing a heuristic to
avoid catastrophic outcomes for all, then applying a weighted sum over
the impact to the remaining users. Future work might also consider
whether criteria other than high median and low variance could be
applied.

Regardless, achieving accurate estimates of such parameters is likely to
remain challenging. Equity in [MPCVD]{acronym-label="MPCVD"
acronym-form="singular+short"} may be a topic of future interest to
groups such as the [FIRST]{acronym-label="FIRST"
acronym-form="singular+short"} Ethics [SIG]{acronym-label="SIG"
acronym-form="singular+short"}[^14].

## [MPCVD]{acronym-label="MPCVD" acronym-form="singular+short"} Is Still Hard

[CVD]{acronym-label="CVD" acronym-form="singular+short"} is a wicked
problem, and [MPCVD]{acronym-label="MPCVD"
acronym-form="singular+short"} even more so [@householder2017cert]. The
model provided by this white paper offers structure to describe the
problem space where there was little of it to speak of previously.

However, such a model does not significantly alter the complexity of the
task of coordinating the response of multiple organizations, many of
which identify as each others' competitors, in order to bring about a
delicate social good in the face of many incentives for things to go
otherwise. The social, business, and geopolitical concerns and interests
that influence cybersecurity policy across the globe remain at the heart
of the vulnerability disclosure problem for most stakeholders. Our hope
is that the model found here will help to clarify decisions,
communication, and policies that all have their part to play in
[MPCVD]{acronym-label="MPCVD" acronym-form="singular+short"} process
improvement.

# Conclusion {#sec:conclusion}

In this report, we developed a state-based model of the
[CVD]{acronym-label="CVD" acronym-form="singular+short"} process that
enables us to enumerate all possible [CVD]{acronym-label="CVD"
acronym-form="singular+short"} histories $\mathcal{H}$ and defined a set
of desired criteria $\mathbb{D}$ that are preferable in each history.
This allowed us to create a partially ordered set over all histories and
to compute a baseline expected frequency for each desired criteria. We
also proposed a new performance indicator for comparing actual
[CVD]{acronym-label="CVD" acronym-form="singular+short"} experiences
against a benchmark, and proposed an initial benchmark based on the
expected frequency of each desired criteria. We demonstrated this
performance indicator in a few examples, indicating that at least some
[CVD]{acronym-label="CVD" acronym-form="singular+short"} practices
appear to be doing considerably better than random. Finally, we posited
a way to apply these metrics to measure the efficacy of
[MPCVD]{acronym-label="MPCVD" acronym-form="singular+short"} processes.

The resulting state-transition model has numerous applications to
formalizing the specification of [CVD]{acronym-label="CVD"
acronym-form="singular+short"} policies and processes. We discussed how
the model can be used to specify embargo and disclosure policies, and to
bring consistency to coordination practices. We further showed how the
model can be used to reduce uncertainty regarding actions to take even
in the presence of incomplete [CVD]{acronym-label="CVD"
acronym-form="singular+short"} information. We also suggested how the
model can be used to normalize frequently-used terms that have lacked
consistent definitions among practitioners of [CVD]{acronym-label="CVD"
acronym-form="singular+short"} and [VM]{acronym-label="VM"
acronym-form="singular+short"}. Finally, we demonstrated the potential
application of this model to US [VEP]{acronym-label="VEP"
acronym-form="singular+short"} scope definitions.

In combination, the model described in this report offers a way to
observe, communicate, and measure the quality improvement of
[CVD]{acronym-label="CVD" acronym-form="singular+short"} and
[MPCVD]{acronym-label="MPCVD" acronym-form="singular+short"} practices
across the board.

::: feedbackrqst
The [CERT/CC]{acronym-label="CERT/CC" acronym-form="singular+short"} is
interested to receive feedback on this report. Although every action was
taken to ensure the completeness and accuracy of the information
contained within this report, the possibility for improvement still
exists. Please feel free to contact the author providing
recommendations, corrections, opinions, or requests for clarification.

Feedback may be submitted at <https://www.sei.cmu.edu/contact-us/>

To contact the author please address all mail to:\
Software Engineering Institute\
4500 Fifth Avenue\
Pittsburgh, PA 15213-2612\
USA\
Email: <info@sei.cmu.edu>\
:::

# Per-State Details {#appendix:actions}

This appendix gives a brief description of each state
$q \in \mathcal{Q}$ as developed in
§[2](#sec:model){reference-type="ref" reference="sec:model"}. See
§[2.3](#sec:states){reference-type="ref" reference="sec:states"} for an
explanation of the states in the model. States are presented in the
order given in
[\[eq:all_states\]](#eq:all_states){reference-type="eqref"
reference="eq:all_states"}, which follows a hierarchy implied by
traversal of the $PXA$ submodel found in
[\[eq:pxa_dfa\]](#eq:pxa_dfa){reference-type="eqref"
reference="eq:pxa_dfa"} for each step of the $VFD$ submodel given in
[\[eq:vfd_dfa\]](#eq:vfd_dfa){reference-type="eqref"
reference="eq:vfd_dfa"}. See
§[2.4](#sec:transitions){reference-type="ref"
reference="sec:transitions"} for an explanation of the state transitions
permitted by the model.

In this appendix, state transitions are cross-referenced by page number
to enable easier navigation through the state descriptions. See
§[3.2](#sec:desirability){reference-type="ref"
reference="sec:desirability"} for more on transition ordering
desiderata. Where applicable, the specific definitions of *zero day*
matched by a given state are shown based on
§[6.5.1](#sec:zerodays){reference-type="ref" reference="sec:zerodays"}.
Additional notes on each state are consistent with
§[6.6](#sec:situation_awareness){reference-type="ref"
reference="sec:situation_awareness"}. Also included for each state is a
table containing suggested actions as derived from
§[6.8](#sec:cvd_action_rules){reference-type="ref"
reference="sec:cvd_action_rules"}. The embargo initiation, continuation,
and exit advice in those rules are consistent with the discussion found
in §[6.4](#sec:policy_formalism){reference-type="ref"
reference="sec:policy_formalism"}. Each state is given its own page to
allow for consistent formatting.

## vfdpxa {#sec:vfdpxa}

Vendor is unaware of vulnerability. Fix is not ready. Fix has not been
deployed. Public is unaware of vulnerability. No exploits have been made
public. No attacks have been observed.

*Previous State(s):* N/A

*Next State(s):* $vfdpxA$ (p.), $vfdpXa$ (p.), $vfdPxa$ (p.), $Vfdpxa$
(p.)

*Desiderata met:* N/A

*Desiderata blocked:* N/A

*Zero Day Definitions Matched:* Zero Day Vulnerability Type 1

*Other notes:* Attack success likely. CVSS 3.1 Exploit Maturity:
Unproven (U) or Not Defined (X). Embargo continuation is viable. Embargo
initiation may be appropriate. SSVC v2 Exploitation: None. SSVC v2
Public Value Added: Precedence. SSVC v2 Report Public: No. SSVC v2
Supplier Contacted: No. VEP remains tenable. See Table
[10.1](#tab:vfdpxa_actions){reference-type="ref"
reference="tab:vfdpxa_actions"} for actions.

::: {#tab:vfdpxa_actions}
  Role         Action                                                  Reason                       Transition
  ------------ ------------------------------------------------------- -------------------------- --------------
  any          Publish vul and any mitigations (if no vendor exists)   Defense                     $\mathbf{P}$
  non-vendor   Notify vendor                                           Coordination                $\mathbf{V}$
  any          Monitor for exploit publication                         SA                               \-
  any          Monitor for attacks                                     SA                               \-
  any          Maintain vigilance for embargo exit criteria            SA                               \-
  any          Maintain any existing disclosure embargo                Coordination                     \-
  any          Negotiate or establish disclosure embargo               Coordination                     \-
  any          Discourage exploit publication until at least F         Limit attacker advantage         \-
  US Gov't     Initiate VEP (if applicable)                            Policy                           \-

  : CVD Action Options for State $vfdpxa$
:::

## vfdpxA {#sec:vfdpxA}

Vendor is unaware of vulnerability. Fix is not ready. Fix has not been
deployed. Public is unaware of vulnerability. No exploits have been made
public. Attacks have been observed.

*Previous State(s):* $vfdpxa$ (p.)

*Next State(s):* $vfdpXA$ (p.), $vfdPxA$ (p.), $VfdpxA$ (p.)

*Desiderata met:* N/A

*Desiderata blocked:* $\mathbf{D} \prec \mathbf{A}$,
$\mathbf{F} \prec \mathbf{A}$, $\mathbf{P} \prec \mathbf{A}$,
$\mathbf{V} \prec \mathbf{A}$, $\mathbf{X} \prec \mathbf{A}$

*Zero Day Definitions Matched:* Zero Day Vulnerability Type 1, Zero Day
Attack Type 1, Zero Day Attack Type 2, Zero Day Attack Type 3

*Other notes:* Attack success likely. Embargo is at risk. SSVC v2
Exploitation: Active. SSVC v2 Public Value Added: Precedence. SSVC v2
Report Public: No. SSVC v2 Supplier Contacted: No. VEP remains tenable.
See Table [10.2](#tab:vfdpxA_actions){reference-type="ref"
reference="tab:vfdpxA_actions"} for actions.

::: {#tab:vfdpxA_actions}
  Role         Action                                                  Reason               Transition
  ------------ ------------------------------------------------------- ------------------ --------------
  any          Publish detection(s) for attacks                        Detection           $\mathbf{P}$
  any          Publish vul and any mitigations                         Defense             $\mathbf{P}$
  any          Publish vul and any mitigations (if no vendor exists)   Defense             $\mathbf{P}$
  non-vendor   Notify vendor                                           Coordination        $\mathbf{V}$
  any          Terminate any existing embargo                          Attacks observed         \-
  any          Monitor for exploit publication                         SA                       \-
  any          Monitor for additional attacks                          SA                       \-
  any          Escalate response priority among responding parties     Coordination             \-
  US Gov't     Initiate VEP (if applicable)                            Policy                   \-

  : CVD Action Options for State $vfdpxA$
:::

## vfdpXa {#sec:vfdpXa}

Vendor is unaware of vulnerability. Fix is not ready. Fix has not been
deployed. Public is unaware of vulnerability. Exploit(s) have been made
public. No attacks have been observed.

*Previous State(s):* $vfdpxa$ (p.)

*Next State(s):* $vfdPXa$ (p.)

*Desiderata met:* $\mathbf{X} \prec \mathbf{A}$

*Desiderata blocked:* $\mathbf{D} \prec \mathbf{X}$,
$\mathbf{F} \prec \mathbf{X}$, $\mathbf{P} \prec \mathbf{X}$,
$\mathbf{V} \prec \mathbf{X}$

*Zero Day Definitions Matched:* Zero Day Vulnerability Type 1, Zero Day
Exploit Type 1, Zero Day Exploit Type 2, Zero Day Exploit Type 3

*Other notes:* Attack success likely. CVSS 3.1 Exploit Maturity: high
(H), functional (F), or proof of concept (P). Embargo is at risk. Expect
both Vendor and Public awareness imminently. SSVC v2 Exploitation: PoC.
SSVC v2 Public Value Added: Precedence. SSVC v2 Report Public: No. SSVC
v2 Supplier Contacted: No. VEP does not apply. See Table
[10.3](#tab:vfdpXa_actions){reference-type="ref"
reference="tab:vfdpXa_actions"} for actions.

::: {#tab:vfdpXa_actions}
  Role         Action                                                  Reason                Transition
  ------------ ------------------------------------------------------- ------------------- --------------
  any          Draw attention to published exploit(s)                  SA                   $\mathbf{P}$
  any          Publish detection(s) for exploits                       Detection            $\mathbf{P}$
  any          Publish vul and any mitigations                         Defense              $\mathbf{P}$
  any          Publish vul and any mitigations (if no vendor exists)   Defense              $\mathbf{P}$
  non-vendor   Notify vendor                                           Coordination         $\mathbf{V}$
  any          Terminate any existing embargo                          Exploit is public         \-
  any          Monitor for exploit refinement                          SA                        \-
  any          Monitor for attacks                                     SA                        \-
  any          Escalate response priority among responding parties     Coordination              \-

  : CVD Action Options for State $vfdpXa$
:::

## vfdpXA {#sec:vfdpXA}

Vendor is unaware of vulnerability. Fix is not ready. Fix has not been
deployed. Public is unaware of vulnerability. Exploit(s) have been made
public. Attacks have been observed.

*Previous State(s):* $vfdpxA$ (p.)

*Next State(s):* $vfdPXA$ (p.)

*Desiderata met:* N/A

*Desiderata blocked:* $\mathbf{D} \prec \mathbf{A}$,
$\mathbf{D} \prec \mathbf{X}$, $\mathbf{F} \prec \mathbf{A}$,
$\mathbf{F} \prec \mathbf{X}$, $\mathbf{P} \prec \mathbf{A}$,
$\mathbf{P} \prec \mathbf{X}$, $\mathbf{V} \prec \mathbf{A}$,
$\mathbf{V} \prec \mathbf{X}$

*Zero Day Definitions Matched:* Zero Day Vulnerability Type 1, Zero Day
Exploit Type 1, Zero Day Exploit Type 2, Zero Day Exploit Type 3, Zero
Day Attack Type 1, Zero Day Attack Type 2, Zero Day Attack Type 3

*Other notes:* Attack success likely. CVSS 3.1 Exploit Maturity: high
(H) or functional (F). Embargo is at risk. Expect both Vendor and Public
awareness imminently. SSVC v2 Exploitation: Active. SSVC v2 Public Value
Added: Precedence. SSVC v2 Report Public: No. SSVC v2 Supplier
Contacted: No. VEP does not apply. See Table
[10.4](#tab:vfdpXA_actions){reference-type="ref"
reference="tab:vfdpXA_actions"} for actions.

::: {#tab:vfdpXA_actions}
  Role         Action                                                  Reason                Transition
  ------------ ------------------------------------------------------- ------------------- --------------
  any          Draw attention to published exploit(s)                  SA                   $\mathbf{P}$
  any          Publish detection(s) for exploits                       Detection            $\mathbf{P}$
  any          Publish detection(s) for attacks                        Detection            $\mathbf{P}$
  any          Publish vul and any mitigations                         Defense              $\mathbf{P}$
  any          Publish vul and any mitigations (if no vendor exists)   Defense              $\mathbf{P}$
  non-vendor   Notify vendor                                           Coordination         $\mathbf{V}$
  any          Terminate any existing embargo                          Exploit is public         \-
  any          Terminate any existing embargo                          Attacks observed          \-
  any          Monitor for exploit refinement                          SA                        \-
  any          Monitor for additional attacks                          SA                        \-
  any          Escalate response priority among responding parties     Coordination              \-

  : CVD Action Options for State $vfdpXA$
:::

## vfdPxa {#sec:vfdPxa}

Vendor is unaware of vulnerability. Fix is not ready. Fix has not been
deployed. Public is aware of vulnerability. No exploits have been made
public. No attacks have been observed.

*Previous State(s):* $vfdpxa$ (p.)

*Next State(s):* $VfdPxa$ (p.)

*Desiderata met:* $\mathbf{P} \prec \mathbf{A}$,
$\mathbf{P} \prec \mathbf{X}$

*Desiderata blocked:* $\mathbf{D} \prec \mathbf{P}$,
$\mathbf{F} \prec \mathbf{P}$, $\mathbf{V} \prec \mathbf{P}$

*Zero Day Definitions Matched:* Zero Day Vulnerability Type 2, Zero Day
Vulnerability Type 3

*Other notes:* Attack success likely. CVSS 3.1 Exploit Maturity:
Unproven (U) or Not Defined (X). Embargo is no longer viable. Expect
Vendor awareness imminently. SSVC v2 Exploitation: None. SSVC v2 Public
Value Added: Ampliative. SSVC v2 Report Public: Yes. SSVC v2 Supplier
Contacted: No. VEP does not apply. See Table
[10.5](#tab:vfdPxa_actions){reference-type="ref"
reference="tab:vfdPxa_actions"} for actions.

::: {#tab:vfdPxa_actions}
  Role         Action                                                Reason                       Transition
  ------------ ----------------------------------------------------- -------------------------- --------------
  vendor       Pay attention to public reports                       SA                          $\mathbf{V}$
  non-vendor   Notify vendor                                         Coordination                $\mathbf{V}$
  any          Terminate any existing embargo                        Vul is public                    \-
  any          Monitor for exploit publication                       SA                               \-
  any          Monitor for attacks                                   SA                               \-
  any          Publish mitigations                                   Defense                          \-
  any          Escalate response priority among responding parties   Coordination                     \-
  any          Discourage exploit publication until at least F       Limit attacker advantage         \-

  : CVD Action Options for State $vfdPxa$
:::

## vfdPxA {#sec:vfdPxA}

Vendor is unaware of vulnerability. Fix is not ready. Fix has not been
deployed. Public is aware of vulnerability. No exploits have been made
public. Attacks have been observed.

*Previous State(s):* $vfdpxA$ (p.)

*Next State(s):* $VfdPxA$ (p.)

*Desiderata met:* $\mathbf{P} \prec \mathbf{X}$

*Desiderata blocked:* $\mathbf{D} \prec \mathbf{A}$,
$\mathbf{D} \prec \mathbf{P}$, $\mathbf{F} \prec \mathbf{A}$,
$\mathbf{F} \prec \mathbf{P}$, $\mathbf{V} \prec \mathbf{A}$,
$\mathbf{V} \prec \mathbf{P}$, $\mathbf{X} \prec \mathbf{A}$

*Zero Day Definitions Matched:* Zero Day Vulnerability Type 2, Zero Day
Vulnerability Type 3, Zero Day Attack Type 1, Zero Day Attack Type 2

*Other notes:* Attack success likely. Embargo is no longer viable.
Expect Vendor awareness imminently. SSVC v2 Exploitation: Active. SSVC
v2 Public Value Added: Ampliative. SSVC v2 Report Public: Yes. SSVC v2
Supplier Contacted: No. VEP does not apply. See Table
[10.6](#tab:vfdPxA_actions){reference-type="ref"
reference="tab:vfdPxA_actions"} for actions.

::: {#tab:vfdPxA_actions}
  Role         Action                                                Reason                 Transition
  ------------ ----------------------------------------------------- -------------------- --------------
  any          Publish detection(s) for attacks                      Detection             $\mathbf{P}$
  vendor       Pay attention to public reports                       SA                    $\mathbf{V}$
  non-vendor   Notify vendor                                         Coordination          $\mathbf{V}$
  any          Publish exploit code                                  Defense, Detection    $\mathbf{X}$
  any          Terminate any existing embargo                        Vul is public              \-
  any          Terminate any existing embargo                        Attacks observed           \-
  any          Monitor for exploit publication                       SA                         \-
  any          Monitor for additional attacks                        SA                         \-
  any          Publish mitigations                                   Defense                    \-
  any          Escalate response priority among responding parties   Coordination               \-

  : CVD Action Options for State $vfdPxA$
:::

## vfdPXa {#sec:vfdPXa}

Vendor is unaware of vulnerability. Fix is not ready. Fix has not been
deployed. Public is aware of vulnerability. Exploit(s) have been made
public. No attacks have been observed.

*Previous State(s):* $vfdpXa$ (p.)

*Next State(s):* $VfdPXa$ (p.)

*Desiderata met:* $\mathbf{P} \prec \mathbf{A}$,
$\mathbf{X} \prec \mathbf{A}$

*Desiderata blocked:* $\mathbf{D} \prec \mathbf{P}$,
$\mathbf{D} \prec \mathbf{X}$, $\mathbf{F} \prec \mathbf{P}$,
$\mathbf{F} \prec \mathbf{X}$, $\mathbf{V} \prec \mathbf{P}$,
$\mathbf{V} \prec \mathbf{X}$

*Zero Day Definitions Matched:* Zero Day Vulnerability Type 2, Zero Day
Vulnerability Type 3, Zero Day Exploit Type 1, Zero Day Exploit Type 2

*Other notes:* Attack success likely. CVSS 3.1 Exploit Maturity: high
(H), functional (F), or proof of concept (P). Embargo is no longer
viable. Expect Vendor awareness imminently. SSVC v2 Exploitation: PoC.
SSVC v2 Public Value Added: Ampliative. SSVC v2 Report Public: Yes. SSVC
v2 Supplier Contacted: No. VEP does not apply. See Table
[10.7](#tab:vfdPXa_actions){reference-type="ref"
reference="tab:vfdPXa_actions"} for actions.

::: {#tab:vfdPXa_actions}
  Role         Action                                                Reason                Transition
  ------------ ----------------------------------------------------- ------------------- --------------
  any          Draw attention to published exploit(s)                SA                   $\mathbf{P}$
  any          Publish detection(s) for exploits                     Detection            $\mathbf{P}$
  any          Publish vul and any mitigations                       Defense              $\mathbf{P}$
  vendor       Pay attention to public reports                       SA                   $\mathbf{V}$
  non-vendor   Notify vendor                                         Coordination         $\mathbf{V}$
  any          Terminate any existing embargo                        Vul is public             \-
  any          Terminate any existing embargo                        Exploit is public         \-
  any          Monitor for exploit refinement                        SA                        \-
  any          Monitor for attacks                                   SA                        \-
  any          Publish mitigations                                   Defense                   \-
  any          Escalate response priority among responding parties   Coordination              \-

  : CVD Action Options for State $vfdPXa$
:::

## vfdPXA {#sec:vfdPXA}

Vendor is unaware of vulnerability. Fix is not ready. Fix has not been
deployed. Public is aware of vulnerability. Exploit(s) have been made
public. Attacks have been observed.

*Previous State(s):* $vfdpXA$ (p.)

*Next State(s):* $VfdPXA$ (p.)

*Desiderata met:* N/A

*Desiderata blocked:* $\mathbf{D} \prec \mathbf{A}$,
$\mathbf{D} \prec \mathbf{P}$, $\mathbf{D} \prec \mathbf{X}$,
$\mathbf{F} \prec \mathbf{A}$, $\mathbf{F} \prec \mathbf{P}$,
$\mathbf{F} \prec \mathbf{X}$, $\mathbf{V} \prec \mathbf{A}$,
$\mathbf{V} \prec \mathbf{P}$, $\mathbf{V} \prec \mathbf{X}$

*Zero Day Definitions Matched:* Zero Day Vulnerability Type 2, Zero Day
Vulnerability Type 3, Zero Day Exploit Type 1, Zero Day Exploit Type 2,
Zero Day Attack Type 1, Zero Day Attack Type 2

*Other notes:* Attack success likely. CVSS 3.1 Exploit Maturity: high
(H) or functional (F). Embargo is no longer viable. Expect Vendor
awareness imminently. SSVC v2 Exploitation: Active. SSVC v2 Public Value
Added: Ampliative. SSVC v2 Report Public: Yes. SSVC v2 Supplier
Contacted: No. VEP does not apply. See Table
[10.8](#tab:vfdPXA_actions){reference-type="ref"
reference="tab:vfdPXA_actions"} for actions.

::: {#tab:vfdPXA_actions}
  Role         Action                                                Reason                Transition
  ------------ ----------------------------------------------------- ------------------- --------------
  any          Draw attention to published exploit(s)                SA                   $\mathbf{P}$
  any          Publish detection(s) for exploits                     Detection            $\mathbf{P}$
  any          Publish detection(s) for attacks                      Detection            $\mathbf{P}$
  any          Publish vul and any mitigations                       Defense              $\mathbf{P}$
  vendor       Pay attention to public reports                       SA                   $\mathbf{V}$
  non-vendor   Notify vendor                                         Coordination         $\mathbf{V}$
  any          Terminate any existing embargo                        Vul is public             \-
  any          Terminate any existing embargo                        Exploit is public         \-
  any          Terminate any existing embargo                        Attacks observed          \-
  any          Monitor for exploit refinement                        SA                        \-
  any          Monitor for additional attacks                        SA                        \-
  any          Publish mitigations                                   Defense                   \-
  any          Escalate response priority among responding parties   Coordination              \-

  : CVD Action Options for State $vfdPXA$
:::

## Vfdpxa {#sec:Vfdpxa}

Vendor is aware of vulnerability. Fix is not ready. Fix has not been
deployed. Public is unaware of vulnerability. No exploits have been made
public. No attacks have been observed.

*Previous State(s):* $vfdpxa$ (p.)

*Next State(s):* $VfdpxA$ (p.), $VfdpXa$ (p.), $VfdPxa$ (p.), $VFdpxa$
(p.)

*Desiderata met:* $\mathbf{V} \prec \mathbf{A}$,
$\mathbf{V} \prec \mathbf{P}$, $\mathbf{V} \prec \mathbf{X}$

*Desiderata blocked:* N/A

*Other notes:* Attack success likely. CVSS 3.1 Exploit Maturity:
Unproven (U) or Not Defined (X). CVSS 3.1 remediation level: Not Defined
(X), Unavailable (U), Workaround (W), or Temporary Fix (T). Embargo
continuation is viable. Embargo initiation may be appropriate. SSVC v2
Exploitation: None. SSVC v2 Public Value Added: Precedence. SSVC v2
Report Public: No. SSVC v2 Supplier Contacted: Yes. VEP does not apply.
See Table [10.9](#tab:Vfdpxa_actions){reference-type="ref"
reference="tab:Vfdpxa_actions"} for actions.

::: {#tab:Vfdpxa_actions}
  Role         Action                                                   Reason                                           Transition
  ------------ -------------------------------------------------------- ---------------------------------------------- --------------
  vendor       Create fix                                               Defense                                         $\mathbf{F}$
  any          Publish vul and any mitigations (if no active embargo)   Defense                                         $\mathbf{P}$
  non-vendor   Publish vul                                              Coordination, Motivate vendor to fix            $\mathbf{P}$
  any          Publish vul                                              Coordination, Motivate deployers to mitigate    $\mathbf{P}$
  any          Monitor for exploit publication                          SA                                                   \-
  any          Monitor for attacks                                      SA                                                   \-
  any          Maintain vigilance for embargo exit criteria             SA                                                   \-
  non-vendor   Encourage vendor to create fix                           Coordination                                         \-
  any          Maintain any existing disclosure embargo                 Coordination                                         \-
  any          Negotiate or establish disclosure embargo                Coordination                                         \-
  any          Discourage exploit publication until at least F          Limit attacker advantage                             \-

  : CVD Action Options for State $Vfdpxa$
:::

## VfdpxA {#sec:VfdpxA}

Vendor is aware of vulnerability. Fix is not ready. Fix has not been
deployed. Public is unaware of vulnerability. No exploits have been made
public. Attacks have been observed.

*Previous State(s):* $vfdpxA$ (p.), $Vfdpxa$ (p.)

*Next State(s):* $VfdpXA$ (p.), $VfdPxA$ (p.), $VFdpxA$ (p.)

*Desiderata met:* $\mathbf{V} \prec \mathbf{P}$,
$\mathbf{V} \prec \mathbf{X}$

*Desiderata blocked:* $\mathbf{D} \prec \mathbf{A}$,
$\mathbf{F} \prec \mathbf{A}$, $\mathbf{P} \prec \mathbf{A}$,
$\mathbf{X} \prec \mathbf{A}$

*Zero Day Definitions Matched:* Zero Day Attack Type 2, Zero Day Attack
Type 3

*Other notes:* Attack success likely. CVSS 3.1 remediation level: Not
Defined (X), Unavailable (U), Workaround (W), or Temporary Fix (T).
Embargo is at risk. SSVC v2 Exploitation: Active. SSVC v2 Public Value
Added: Precedence. SSVC v2 Report Public: No. SSVC v2 Supplier
Contacted: Yes. VEP does not apply. See Table
[10.10](#tab:VfdpxA_actions){reference-type="ref"
reference="tab:VfdpxA_actions"} for actions.

::: {#tab:VfdpxA_actions}
  Role         Action                                                   Reason                                           Transition
  ------------ -------------------------------------------------------- ---------------------------------------------- --------------
  vendor       Create fix                                               Defense                                         $\mathbf{F}$
  any          Publish detection(s) for attacks                         Detection                                       $\mathbf{P}$
  any          Publish vul and any mitigations (if no active embargo)   Defense                                         $\mathbf{P}$
  any          Publish vul and any mitigations                          Defense                                         $\mathbf{P}$
  non-vendor   Publish vul                                              Coordination, Motivate vendor to fix            $\mathbf{P}$
  any          Publish vul                                              Coordination, Motivate deployers to mitigate    $\mathbf{P}$
  any          Terminate any existing embargo                           Attacks observed                                     \-
  any          Monitor for exploit publication                          SA                                                   \-
  any          Monitor for additional attacks                           SA                                                   \-
  any          Escalate response priority among responding parties      Coordination                                         \-
  non-vendor   Encourage vendor to create fix                           Coordination                                         \-

  : CVD Action Options for State $VfdpxA$
:::

## VfdpXa {#sec:VfdpXa}

Vendor is aware of vulnerability. Fix is not ready. Fix has not been
deployed. Public is unaware of vulnerability. Exploit(s) have been made
public. No attacks have been observed.

*Previous State(s):* $Vfdpxa$ (p.)

*Next State(s):* $VfdPXa$ (p.)

*Desiderata met:* $\mathbf{V} \prec \mathbf{A}$,
$\mathbf{V} \prec \mathbf{P}$, $\mathbf{X} \prec \mathbf{A}$

*Desiderata blocked:* $\mathbf{D} \prec \mathbf{X}$,
$\mathbf{F} \prec \mathbf{X}$, $\mathbf{P} \prec \mathbf{X}$

*Zero Day Definitions Matched:* Zero Day Exploit Type 2, Zero Day
Exploit Type 3

*Other notes:* Attack success likely. CVSS 3.1 Exploit Maturity: high
(H), functional (F), or proof of concept (P). CVSS 3.1 remediation
level: Not Defined (X), Unavailable (U), Workaround (W), or Temporary
Fix (T). Embargo is at risk. Expect Public awareness imminently. SSVC v2
Exploitation: PoC. SSVC v2 Public Value Added: Precedence. SSVC v2
Report Public: No. SSVC v2 Supplier Contacted: Yes. VEP does not apply.
See Table [10.11](#tab:VfdpXa_actions){reference-type="ref"
reference="tab:VfdpXa_actions"} for actions.

::: {#tab:VfdpXa_actions}
  Role         Action                                                   Reason                                           Transition
  ------------ -------------------------------------------------------- ---------------------------------------------- --------------
  vendor       Create fix                                               Defense                                         $\mathbf{F}$
  any          Draw attention to published exploit(s)                   SA                                              $\mathbf{P}$
  any          Publish detection(s) for exploits                        Detection                                       $\mathbf{P}$
  any          Publish vul and any mitigations (if no active embargo)   Defense                                         $\mathbf{P}$
  any          Publish vul and any mitigations                          Defense                                         $\mathbf{P}$
  non-vendor   Publish vul                                              Coordination, Motivate vendor to fix            $\mathbf{P}$
  any          Publish vul                                              Coordination, Motivate deployers to mitigate    $\mathbf{P}$
  any          Terminate any existing embargo                           Exploit is public                                    \-
  any          Monitor for exploit refinement                           SA                                                   \-
  any          Monitor for attacks                                      SA                                                   \-
  any          Escalate response priority among responding parties      Coordination                                         \-
  non-vendor   Encourage vendor to create fix                           Coordination                                         \-

  : CVD Action Options for State $VfdpXa$
:::

## VfdpXA {#sec:VfdpXA}

Vendor is aware of vulnerability. Fix is not ready. Fix has not been
deployed. Public is unaware of vulnerability. Exploit(s) have been made
public. Attacks have been observed.

*Previous State(s):* $VfdpxA$ (p.)

*Next State(s):* $VfdPXA$ (p.)

*Desiderata met:* $\mathbf{V} \prec \mathbf{P}$

*Desiderata blocked:* $\mathbf{D} \prec \mathbf{A}$,
$\mathbf{D} \prec \mathbf{X}$, $\mathbf{F} \prec \mathbf{A}$,
$\mathbf{F} \prec \mathbf{X}$, $\mathbf{P} \prec \mathbf{A}$,
$\mathbf{P} \prec \mathbf{X}$

*Zero Day Definitions Matched:* Zero Day Exploit Type 2, Zero Day
Exploit Type 3, Zero Day Attack Type 2, Zero Day Attack Type 3

*Other notes:* Attack success likely. CVSS 3.1 Exploit Maturity: high
(H) or functional (F). CVSS 3.1 remediation level: Not Defined (X),
Unavailable (U), Workaround (W), or Temporary Fix (T). Embargo is at
risk. Expect Public awareness imminently. SSVC v2 Exploitation: Active.
SSVC v2 Public Value Added: Precedence. SSVC v2 Report Public: No. SSVC
v2 Supplier Contacted: Yes. VEP does not apply. See Table
[10.12](#tab:VfdpXA_actions){reference-type="ref"
reference="tab:VfdpXA_actions"} for actions.

::: {#tab:VfdpXA_actions}
  Role         Action                                                   Reason                                           Transition
  ------------ -------------------------------------------------------- ---------------------------------------------- --------------
  vendor       Create fix                                               Defense                                         $\mathbf{F}$
  any          Draw attention to published exploit(s)                   SA                                              $\mathbf{P}$
  any          Publish detection(s) for exploits                        Detection                                       $\mathbf{P}$
  any          Publish detection(s) for attacks                         Detection                                       $\mathbf{P}$
  any          Publish vul and any mitigations (if no active embargo)   Defense                                         $\mathbf{P}$
  any          Publish vul and any mitigations                          Defense                                         $\mathbf{P}$
  non-vendor   Publish vul                                              Coordination, Motivate vendor to fix            $\mathbf{P}$
  any          Publish vul                                              Coordination, Motivate deployers to mitigate    $\mathbf{P}$
  any          Terminate any existing embargo                           Exploit is public                                    \-
  any          Terminate any existing embargo                           Attacks observed                                     \-
  any          Monitor for exploit refinement                           SA                                                   \-
  any          Monitor for additional attacks                           SA                                                   \-
  any          Escalate response priority among responding parties      Coordination                                         \-
  non-vendor   Encourage vendor to create fix                           Coordination                                         \-

  : CVD Action Options for State $VfdpXA$
:::

## VfdPxa {#sec:VfdPxa}

Vendor is aware of vulnerability. Fix is not ready. Fix has not been
deployed. Public is aware of vulnerability. No exploits have been made
public. No attacks have been observed.

*Previous State(s):* $vfdPxa$ (p.), $Vfdpxa$ (p.)

*Next State(s):* $VfdPxA$ (p.), $VfdPXa$ (p.), $VFdPxa$ (p.)

*Desiderata met:* $\mathbf{P} \prec \mathbf{A}$,
$\mathbf{P} \prec \mathbf{X}$, $\mathbf{V} \prec \mathbf{A}$,
$\mathbf{V} \prec \mathbf{X}$

*Desiderata blocked:* $\mathbf{D} \prec \mathbf{P}$,
$\mathbf{F} \prec \mathbf{P}$

*Zero Day Definitions Matched:* Zero Day Vulnerability Type 3

*Other notes:* Attack success likely. CVSS 3.1 Exploit Maturity:
Unproven (U) or Not Defined (X). CVSS 3.1 remediation level: Not Defined
(X), Unavailable (U), Workaround (W), or Temporary Fix (T). Embargo is
no longer viable. SSVC v2 Exploitation: None. SSVC v2 Public Value
Added: Ampliative. SSVC v2 Report Public: Yes. SSVC v2 Supplier
Contacted: Yes. VEP does not apply. See Table
[10.13](#tab:VfdPxa_actions){reference-type="ref"
reference="tab:VfdPxa_actions"} for actions.

::: {#tab:VfdPxa_actions}
  Role         Action                                                  Reason                       Transition
  ------------ ------------------------------------------------------- -------------------------- --------------
  vendor       Create fix                                              Defense                     $\mathbf{F}$
  any          Terminate any existing embargo                          Vul is public                    \-
  any          Monitor for exploit publication                         SA                               \-
  any          Monitor for attacks                                     SA                               \-
  any          Escalate vigilance for exploit publication or attacks   SA, Coordination                 \-
  any          Publish mitigations                                     Defense                          \-
  any          Ensure any available mitigations are publicized         Defense                          \-
  any          Escalate response priority among responding parties     Coordination                     \-
  non-vendor   Encourage vendor to create fix                          Coordination                     \-
  non-vendor   Escalate fix priority with vendor                       Coordination                     \-
  any          Discourage exploit publication until at least F         Limit attacker advantage         \-

  : CVD Action Options for State $VfdPxa$
:::

## VfdPxA {#sec:VfdPxA}

Vendor is aware of vulnerability. Fix is not ready. Fix has not been
deployed. Public is aware of vulnerability. No exploits have been made
public. Attacks have been observed.

*Previous State(s):* $vfdPxA$ (p.), $VfdpxA$ (p.), $VfdPxa$ (p.)

*Next State(s):* $VfdPXA$ (p.), $VFdPxA$ (p.)

*Desiderata met:* $\mathbf{P} \prec \mathbf{X}$,
$\mathbf{V} \prec \mathbf{X}$

*Desiderata blocked:* $\mathbf{D} \prec \mathbf{A}$,
$\mathbf{D} \prec \mathbf{P}$, $\mathbf{F} \prec \mathbf{A}$,
$\mathbf{F} \prec \mathbf{P}$, $\mathbf{X} \prec \mathbf{A}$

*Zero Day Definitions Matched:* Zero Day Vulnerability Type 3, Zero Day
Attack Type 2

*Other notes:* Attack success likely. CVSS 3.1 remediation level: Not
Defined (X), Unavailable (U), Workaround (W), or Temporary Fix (T).
Embargo is no longer viable. SSVC v2 Exploitation: Active. SSVC v2
Public Value Added: Ampliative. SSVC v2 Report Public: Yes. SSVC v2
Supplier Contacted: Yes. VEP does not apply. See Table
[10.14](#tab:VfdPxA_actions){reference-type="ref"
reference="tab:VfdPxA_actions"} for actions.

::: {#tab:VfdPxA_actions}
  Role         Action                                                  Reason                 Transition
  ------------ ------------------------------------------------------- -------------------- --------------
  vendor       Create fix                                              Defense               $\mathbf{F}$
  any          Publish detection(s) for attacks                        Detection             $\mathbf{P}$
  any          Publish exploit code                                    Defense, Detection    $\mathbf{X}$
  any          Terminate any existing embargo                          Vul is public              \-
  any          Terminate any existing embargo                          Attacks observed           \-
  any          Monitor for exploit publication                         SA                         \-
  any          Monitor for additional attacks                          SA                         \-
  any          Escalate vigilance for exploit publication or attacks   SA, Coordination           \-
  any          Publish mitigations                                     Defense                    \-
  any          Ensure any available mitigations are publicized         Defense                    \-
  any          Escalate response priority among responding parties     Coordination               \-
  non-vendor   Encourage vendor to create fix                          Coordination               \-
  non-vendor   Escalate fix priority with vendor                       Coordination               \-

  : CVD Action Options for State $VfdPxA$
:::

## VfdPXa {#sec:VfdPXa}

Vendor is aware of vulnerability. Fix is not ready. Fix has not been
deployed. Public is aware of vulnerability. Exploit(s) have been made
public. No attacks have been observed.

*Previous State(s):* $vfdPXa$ (p.), $VfdpXa$ (p.), $VfdPxa$ (p.)

*Next State(s):* $VfdPXA$ (p.), $VFdPXa$ (p.)

*Desiderata met:* $\mathbf{P} \prec \mathbf{A}$,
$\mathbf{V} \prec \mathbf{A}$, $\mathbf{X} \prec \mathbf{A}$

*Desiderata blocked:* $\mathbf{D} \prec \mathbf{P}$,
$\mathbf{D} \prec \mathbf{X}$, $\mathbf{F} \prec \mathbf{P}$,
$\mathbf{F} \prec \mathbf{X}$

*Zero Day Definitions Matched:* Zero Day Vulnerability Type 3, Zero Day
Exploit Type 2

*Other notes:* Attack success likely. CVSS 3.1 Exploit Maturity: high
(H), functional (F), or proof of concept (P). CVSS 3.1 remediation
level: Not Defined (X), Unavailable (U), Workaround (W), or Temporary
Fix (T). Embargo is no longer viable. SSVC v2 Exploitation: PoC. SSVC v2
Public Value Added: Ampliative. SSVC v2 Report Public: Yes. SSVC v2
Supplier Contacted: Yes. VEP does not apply. See Table
[10.15](#tab:VfdPXa_actions){reference-type="ref"
reference="tab:VfdPXa_actions"} for actions.

::: {#tab:VfdPXa_actions}
  Role         Action                                                  Reason                Transition
  ------------ ------------------------------------------------------- ------------------- --------------
  vendor       Create fix                                              Defense              $\mathbf{F}$
  any          Draw attention to published exploit(s)                  SA                   $\mathbf{P}$
  any          Publish detection(s) for exploits                       Detection            $\mathbf{P}$
  any          Publish vul and any mitigations                         Defense              $\mathbf{P}$
  any          Terminate any existing embargo                          Vul is public             \-
  any          Terminate any existing embargo                          Exploit is public         \-
  any          Monitor for exploit refinement                          SA                        \-
  any          Monitor for attacks                                     SA                        \-
  any          Escalate vigilance for exploit publication or attacks   SA, Coordination          \-
  any          Publish mitigations                                     Defense                   \-
  any          Ensure any available mitigations are publicized         Defense                   \-
  any          Escalate response priority among responding parties     Coordination              \-
  non-vendor   Encourage vendor to create fix                          Coordination              \-
  non-vendor   Escalate fix priority with vendor                       Coordination              \-

  : CVD Action Options for State $VfdPXa$
:::

## VfdPXA {#sec:VfdPXA}

Vendor is aware of vulnerability. Fix is not ready. Fix has not been
deployed. Public is aware of vulnerability. Exploit(s) have been made
public. Attacks have been observed.

*Previous State(s):* $vfdPXA$ (p.), $VfdpXA$ (p.), $VfdPxA$ (p.),
$VfdPXa$ (p.)

*Next State(s):* $VFdPXA$ (p.)

*Desiderata met:* N/A

*Desiderata blocked:* $\mathbf{D} \prec \mathbf{A}$,
$\mathbf{D} \prec \mathbf{P}$, $\mathbf{D} \prec \mathbf{X}$,
$\mathbf{F} \prec \mathbf{A}$, $\mathbf{F} \prec \mathbf{P}$,
$\mathbf{F} \prec \mathbf{X}$

*Zero Day Definitions Matched:* Zero Day Vulnerability Type 3, Zero Day
Exploit Type 2, Zero Day Attack Type 2

*Other notes:* Attack success likely. CVSS 3.1 Exploit Maturity: high
(H) or functional (F). CVSS 3.1 remediation level: Not Defined (X),
Unavailable (U), Workaround (W), or Temporary Fix (T). Embargo is no
longer viable. SSVC v2 Exploitation: Active. SSVC v2 Public Value Added:
Ampliative. SSVC v2 Report Public: Yes. SSVC v2 Supplier Contacted: Yes.
VEP does not apply. See Table
[10.16](#tab:VfdPXA_actions){reference-type="ref"
reference="tab:VfdPXA_actions"} for actions.

::: {#tab:VfdPXA_actions}
  Role         Action                                                  Reason                Transition
  ------------ ------------------------------------------------------- ------------------- --------------
  vendor       Create fix                                              Defense              $\mathbf{F}$
  any          Draw attention to published exploit(s)                  SA                   $\mathbf{P}$
  any          Publish detection(s) for exploits                       Detection            $\mathbf{P}$
  any          Publish detection(s) for attacks                        Detection            $\mathbf{P}$
  any          Publish vul and any mitigations                         Defense              $\mathbf{P}$
  any          Terminate any existing embargo                          Vul is public             \-
  any          Terminate any existing embargo                          Exploit is public         \-
  any          Terminate any existing embargo                          Attacks observed          \-
  any          Monitor for exploit refinement                          SA                        \-
  any          Monitor for additional attacks                          SA                        \-
  any          Escalate vigilance for exploit publication or attacks   SA, Coordination          \-
  any          Publish mitigations                                     Defense                   \-
  any          Ensure any available mitigations are publicized         Defense                   \-
  any          Escalate response priority among responding parties     Coordination              \-
  non-vendor   Encourage vendor to create fix                          Coordination              \-
  non-vendor   Escalate fix priority with vendor                       Coordination              \-

  : CVD Action Options for State $VfdPXA$
:::

## VFdpxa {#sec:VFdpxa}

Vendor is aware of vulnerability. Fix is ready. Fix has not been
deployed. Public is unaware of vulnerability. No exploits have been made
public. No attacks have been observed.

*Previous State(s):* $Vfdpxa$ (p.)

*Next State(s):* $VFdpxA$ (p.), $VFdpXa$ (p.), $VFdPxa$ (p.), $VFDpxa$
(p.)

*Desiderata met:* $\mathbf{F} \prec \mathbf{A}$,
$\mathbf{F} \prec \mathbf{P}$, $\mathbf{F} \prec \mathbf{X}$,
$\mathbf{V} \prec \mathbf{A}$, $\mathbf{V} \prec \mathbf{P}$,
$\mathbf{V} \prec \mathbf{X}$

*Desiderata blocked:* N/A

*Other notes:* Attack success likely. CVSS 3.1 Exploit Maturity:
Unproven (U) or Not Defined (X). CVSS 3.1 remediation level: Temporary
Fix (T) or Official Fix (O). Embargo continuation is viable. Embargo
initiation may be appropriate. Embargo initiation with careful
consideration only. SSVC v2 Exploitation: None. SSVC v2 Public Value
Added: Ampliative. SSVC v2 Public Value Added: Precedence. SSVC v2
Report Public: No. SSVC v2 Supplier Contacted: Yes. VEP does not apply.
See Table [10.17](#tab:VFdpxa_actions){reference-type="ref"
reference="tab:VFdpxa_actions"} for actions.

::: {#tab:VFdpxa_actions}
  Role               Action                                                              Reason                    Transition
  ------------------ ------------------------------------------------------------------- ----------------------- --------------
  vendor, deployer   Deploy fix (if possible)                                            Defense                  $\mathbf{D}$
  any                Publish vul and any mitigations (if no active embargo)              Defense                  $\mathbf{P}$
  any                Publish vul and fix details                                         Accelerate deployment    $\mathbf{P}$
  any                Monitor for exploit publication                                     SA                            \-
  any                Monitor for attacks                                                 SA                            \-
  any                Maintain vigilance for embargo exit criteria                        SA                            \-
  any                Maintain any existing disclosure embargo                            Coordination                  \-
  any                Negotiate or establish disclosure embargo                           Coordination                  \-
  non-vendor         Encourage vendor to deploy fix (if possible)                        Coordination                  \-
  any                Scrutinize appropriateness of initiating a new disclosure embargo   Coordination                  \-

  : CVD Action Options for State $VFdpxa$
:::

## VFdpxA {#sec:VFdpxA}

Vendor is aware of vulnerability. Fix is ready. Fix has not been
deployed. Public is unaware of vulnerability. No exploits have been made
public. Attacks have been observed.

*Previous State(s):* $VfdpxA$ (p.), $VFdpxa$ (p.)

*Next State(s):* $VFdpXA$ (p.), $VFdPxA$ (p.), $VFDpxA$ (p.)

*Desiderata met:* $\mathbf{F} \prec \mathbf{P}$,
$\mathbf{F} \prec \mathbf{X}$, $\mathbf{V} \prec \mathbf{P}$,
$\mathbf{V} \prec \mathbf{X}$

*Desiderata blocked:* $\mathbf{D} \prec \mathbf{A}$,
$\mathbf{P} \prec \mathbf{A}$, $\mathbf{X} \prec \mathbf{A}$

*Zero Day Definitions Matched:* Zero Day Attack Type 3

*Other notes:* Attack success likely. CVSS 3.1 remediation level:
Temporary Fix (T) or Official Fix (O). Embargo is at risk. SSVC v2
Exploitation: Active. SSVC v2 Public Value Added: Ampliative. SSVC v2
Public Value Added: Precedence. SSVC v2 Report Public: No. SSVC v2
Supplier Contacted: Yes. VEP does not apply. See Table
[10.18](#tab:VFdpxA_actions){reference-type="ref"
reference="tab:VFdpxA_actions"} for actions.

::: {#tab:VFdpxA_actions}
  Role               Action                                                   Reason                    Transition
  ------------------ -------------------------------------------------------- ----------------------- --------------
  vendor, deployer   Deploy fix (if possible)                                 Defense                  $\mathbf{D}$
  any                Publish detection(s) for attacks                         Detection                $\mathbf{P}$
  any                Publish vul and any mitigations (if no active embargo)   Defense                  $\mathbf{P}$
  any                Publish vul and any mitigations                          Defense                  $\mathbf{P}$
  any                Publish vul and fix details                              Accelerate deployment    $\mathbf{P}$
  any                Terminate any existing embargo                           Attacks observed              \-
  any                Monitor for exploit publication                          SA                            \-
  any                Monitor for additional attacks                           SA                            \-
  any                Escalate response priority among responding parties      Coordination                  \-
  non-vendor         Encourage vendor to deploy fix (if possible)             Coordination                  \-

  : CVD Action Options for State $VFdpxA$
:::

## VFdpXa {#sec:VFdpXa}

Vendor is aware of vulnerability. Fix is ready. Fix has not been
deployed. Public is unaware of vulnerability. Exploit(s) have been made
public. No attacks have been observed.

*Previous State(s):* $VFdpxa$ (p.)

*Next State(s):* $VFdPXa$ (p.)

*Desiderata met:* $\mathbf{F} \prec \mathbf{A}$,
$\mathbf{F} \prec \mathbf{P}$, $\mathbf{V} \prec \mathbf{A}$,
$\mathbf{V} \prec \mathbf{P}$, $\mathbf{X} \prec \mathbf{A}$

*Desiderata blocked:* $\mathbf{D} \prec \mathbf{X}$,
$\mathbf{P} \prec \mathbf{X}$

*Zero Day Definitions Matched:* Zero Day Exploit Type 3

*Other notes:* Attack success likely. CVSS 3.1 Exploit Maturity: high
(H), functional (F), or proof of concept (P). CVSS 3.1 remediation
level: Temporary Fix (T) or Official Fix (O). Embargo is at risk. Expect
Public awareness imminently. SSVC v2 Exploitation: PoC. SSVC v2 Public
Value Added: Ampliative. SSVC v2 Public Value Added: Precedence. SSVC v2
Report Public: No. SSVC v2 Supplier Contacted: Yes. VEP does not apply.
See Table [10.19](#tab:VFdpXa_actions){reference-type="ref"
reference="tab:VFdpXa_actions"} for actions.

::: {#tab:VFdpXa_actions}
  Role               Action                                                   Reason                    Transition
  ------------------ -------------------------------------------------------- ----------------------- --------------
  vendor, deployer   Deploy fix (if possible)                                 Defense                  $\mathbf{D}$
  any                Draw attention to published exploit(s)                   SA                       $\mathbf{P}$
  any                Publish detection(s) for exploits                        Detection                $\mathbf{P}$
  any                Publish vul and any mitigations (if no active embargo)   Defense                  $\mathbf{P}$
  any                Publish vul and any mitigations                          Defense                  $\mathbf{P}$
  any                Publish vul and fix details                              Accelerate deployment    $\mathbf{P}$
  any                Terminate any existing embargo                           Exploit is public             \-
  any                Monitor for exploit refinement                           SA                            \-
  any                Monitor for attacks                                      SA                            \-
  any                Escalate response priority among responding parties      Coordination                  \-
  non-vendor         Encourage vendor to deploy fix (if possible)             Coordination                  \-

  : CVD Action Options for State $VFdpXa$
:::

## VFdpXA {#sec:VFdpXA}

Vendor is aware of vulnerability. Fix is ready. Fix has not been
deployed. Public is unaware of vulnerability. Exploit(s) have been made
public. Attacks have been observed.

*Previous State(s):* $VFdpxA$ (p.)

*Next State(s):* $VFdPXA$ (p.)

*Desiderata met:* $\mathbf{F} \prec \mathbf{P}$,
$\mathbf{V} \prec \mathbf{P}$

*Desiderata blocked:* $\mathbf{D} \prec \mathbf{A}$,
$\mathbf{D} \prec \mathbf{X}$, $\mathbf{P} \prec \mathbf{A}$,
$\mathbf{P} \prec \mathbf{X}$

*Zero Day Definitions Matched:* Zero Day Exploit Type 3, Zero Day Attack
Type 3

*Other notes:* Attack success likely. CVSS 3.1 Exploit Maturity: high
(H) or functional (F). CVSS 3.1 remediation level: Temporary Fix (T) or
Official Fix (O). Embargo is at risk. Expect Public awareness
imminently. SSVC v2 Exploitation: Active. SSVC v2 Public Value Added:
Ampliative. SSVC v2 Public Value Added: Precedence. SSVC v2 Report
Public: No. SSVC v2 Supplier Contacted: Yes. VEP does not apply. See
Table [10.20](#tab:VFdpXA_actions){reference-type="ref"
reference="tab:VFdpXA_actions"} for actions.

::: {#tab:VFdpXA_actions}
  Role               Action                                                   Reason                    Transition
  ------------------ -------------------------------------------------------- ----------------------- --------------
  vendor, deployer   Deploy fix (if possible)                                 Defense                  $\mathbf{D}$
  any                Draw attention to published exploit(s)                   SA                       $\mathbf{P}$
  any                Publish detection(s) for exploits                        Detection                $\mathbf{P}$
  any                Publish detection(s) for attacks                         Detection                $\mathbf{P}$
  any                Publish vul and any mitigations (if no active embargo)   Defense                  $\mathbf{P}$
  any                Publish vul and any mitigations                          Defense                  $\mathbf{P}$
  any                Publish vul and fix details                              Accelerate deployment    $\mathbf{P}$
  any                Terminate any existing embargo                           Exploit is public             \-
  any                Terminate any existing embargo                           Attacks observed              \-
  any                Monitor for exploit refinement                           SA                            \-
  any                Monitor for additional attacks                           SA                            \-
  any                Escalate response priority among responding parties      Coordination                  \-
  non-vendor         Encourage vendor to deploy fix (if possible)             Coordination                  \-

  : CVD Action Options for State $VFdpXA$
:::

## VFdPxa {#sec:VFdPxa}

Vendor is aware of vulnerability. Fix is ready. Fix has not been
deployed. Public is aware of vulnerability. No exploits have been made
public. No attacks have been observed.

*Previous State(s):* $VfdPxa$ (p.), $VFdpxa$ (p.)

*Next State(s):* $VFdPxA$ (p.), $VFdPXa$ (p.), $VFDPxa$ (p.)

*Desiderata met:* $\mathbf{F} \prec \mathbf{A}$,
$\mathbf{F} \prec \mathbf{X}$, $\mathbf{P} \prec \mathbf{A}$,
$\mathbf{P} \prec \mathbf{X}$, $\mathbf{V} \prec \mathbf{A}$,
$\mathbf{V} \prec \mathbf{X}$

*Desiderata blocked:* $\mathbf{D} \prec \mathbf{P}$

*Other notes:* Attack success likely. CVSS 3.1 Exploit Maturity:
Unproven (U) or Not Defined (X). CVSS 3.1 remediation level: Temporary
Fix (T) or Official Fix (O). Embargo is no longer viable. SSVC v2
Exploitation: None. SSVC v2 Public Value Added: Ampliative. SSVC v2
Public Value Added: Limited. SSVC v2 Report Public: Yes. SSVC v2
Supplier Contacted: Yes. VEP does not apply. See Table
[10.21](#tab:VFdPxa_actions){reference-type="ref"
reference="tab:VFdPxa_actions"} for actions.

::: {#tab:VFdPxa_actions}
  Role       Action                                                Reason                                        Transition
  ---------- ----------------------------------------------------- ------------------------------------------- --------------
  deployer   Deploy fix                                            Defense                                      $\mathbf{D}$
  any        Publish exploit code                                  Defense, Detection, Accelerate deployment    $\mathbf{X}$
  any        Terminate any existing embargo                        Vul is public                                     \-
  any        Monitor for exploit publication                       SA                                                \-
  any        Monitor for attacks                                   SA                                                \-
  any        Escalate response priority among responding parties   Coordination                                      \-
  any        Promote fix deployment                                Accelerate deployment                             \-

  : CVD Action Options for State $VFdPxa$
:::

## VFdPxA {#sec:VFdPxA}

Vendor is aware of vulnerability. Fix is ready. Fix has not been
deployed. Public is aware of vulnerability. No exploits have been made
public. Attacks have been observed.

*Previous State(s):* $VfdPxA$ (p.), $VFdpxA$ (p.), $VFdPxa$ (p.)

*Next State(s):* $VFdPXA$ (p.), $VFDPxA$ (p.)

*Desiderata met:* $\mathbf{F} \prec \mathbf{X}$,
$\mathbf{P} \prec \mathbf{X}$, $\mathbf{V} \prec \mathbf{X}$

*Desiderata blocked:* $\mathbf{D} \prec \mathbf{A}$,
$\mathbf{D} \prec \mathbf{P}$, $\mathbf{X} \prec \mathbf{A}$

*Other notes:* Attack success likely. CVSS 3.1 remediation level:
Temporary Fix (T) or Official Fix (O). Embargo is no longer viable. SSVC
v2 Exploitation: Active. SSVC v2 Public Value Added: Ampliative. SSVC v2
Public Value Added: Limited. SSVC v2 Report Public: Yes. SSVC v2
Supplier Contacted: Yes. VEP does not apply. See Table
[10.22](#tab:VFdPxA_actions){reference-type="ref"
reference="tab:VFdPxA_actions"} for actions.

::: {#tab:VFdPxA_actions}
  Role       Action                                                Reason                    Transition
  ---------- ----------------------------------------------------- ----------------------- --------------
  deployer   Deploy fix                                            Defense                  $\mathbf{D}$
  any        Publish detection(s) for attacks                      Detection                $\mathbf{P}$
  any        Terminate any existing embargo                        Vul is public                 \-
  any        Terminate any existing embargo                        Attacks observed              \-
  any        Monitor for exploit publication                       SA                            \-
  any        Monitor for additional attacks                        SA                            \-
  any        Escalate response priority among responding parties   Coordination                  \-
  any        Promote fix deployment                                Accelerate deployment         \-

  : CVD Action Options for State $VFdPxA$
:::

## VFdPXa {#sec:VFdPXa}

Vendor is aware of vulnerability. Fix is ready. Fix has not been
deployed. Public is aware of vulnerability. Exploit(s) have been made
public. No attacks have been observed.

*Previous State(s):* $VfdPXa$ (p.), $VFdpXa$ (p.), $VFdPxa$ (p.)

*Next State(s):* $VFdPXA$ (p.), $VFDPXa$ (p.)

*Desiderata met:* $\mathbf{F} \prec \mathbf{A}$,
$\mathbf{P} \prec \mathbf{A}$, $\mathbf{V} \prec \mathbf{A}$,
$\mathbf{X} \prec \mathbf{A}$

*Desiderata blocked:* $\mathbf{D} \prec \mathbf{P}$,
$\mathbf{D} \prec \mathbf{X}$

*Other notes:* Attack success likely. CVSS 3.1 Exploit Maturity: high
(H), functional (F), or proof of concept (P). CVSS 3.1 remediation
level: Temporary Fix (T) or Official Fix (O). Embargo is no longer
viable. SSVC v2 Exploitation: PoC. SSVC v2 Public Value Added:
Ampliative. SSVC v2 Public Value Added: Limited. SSVC v2 Report Public:
Yes. SSVC v2 Supplier Contacted: Yes. VEP does not apply. See Table
[10.23](#tab:VFdPXa_actions){reference-type="ref"
reference="tab:VFdPXa_actions"} for actions.

::: {#tab:VFdPXa_actions}
  Role       Action                                                Reason                    Transition
  ---------- ----------------------------------------------------- ----------------------- --------------
  deployer   Deploy fix                                            Defense                  $\mathbf{D}$
  any        Draw attention to published exploit(s)                SA                       $\mathbf{P}$
  any        Publish detection(s) for exploits                     Detection                $\mathbf{P}$
  any        Publish vul and any mitigations                       Defense                  $\mathbf{P}$
  any        Terminate any existing embargo                        Vul is public                 \-
  any        Terminate any existing embargo                        Exploit is public             \-
  any        Monitor for exploit refinement                        SA                            \-
  any        Monitor for attacks                                   SA                            \-
  any        Escalate response priority among responding parties   Coordination                  \-
  any        Promote fix deployment                                Accelerate deployment         \-

  : CVD Action Options for State $VFdPXa$
:::

## VFdPXA {#sec:VFdPXA}

Vendor is aware of vulnerability. Fix is ready. Fix has not been
deployed. Public is aware of vulnerability. Exploit(s) have been made
public. Attacks have been observed.

*Previous State(s):* $VfdPXA$ (p.), $VFdpXA$ (p.), $VFdPxA$ (p.),
$VFdPXa$ (p.)

*Next State(s):* $VFDPXA$ (p.)

*Desiderata met:* N/A

*Desiderata blocked:* $\mathbf{D} \prec \mathbf{A}$,
$\mathbf{D} \prec \mathbf{P}$, $\mathbf{D} \prec \mathbf{X}$

*Other notes:* Attack success likely. CVSS 3.1 Exploit Maturity: high
(H) or functional (F). CVSS 3.1 remediation level: Temporary Fix (T) or
Official Fix (O). Embargo is no longer viable. SSVC v2 Exploitation:
Active. SSVC v2 Public Value Added: Ampliative. SSVC v2 Public Value
Added: Limited. SSVC v2 Report Public: Yes. SSVC v2 Supplier Contacted:
Yes. VEP does not apply. See Table
[10.24](#tab:VFdPXA_actions){reference-type="ref"
reference="tab:VFdPXA_actions"} for actions.

::: {#tab:VFdPXA_actions}
  Role       Action                                                Reason                    Transition
  ---------- ----------------------------------------------------- ----------------------- --------------
  deployer   Deploy fix                                            Defense                  $\mathbf{D}$
  any        Draw attention to published exploit(s)                SA                       $\mathbf{P}$
  any        Publish detection(s) for exploits                     Detection                $\mathbf{P}$
  any        Publish detection(s) for attacks                      Detection                $\mathbf{P}$
  any        Publish vul and any mitigations                       Defense                  $\mathbf{P}$
  any        Terminate any existing embargo                        Vul is public                 \-
  any        Terminate any existing embargo                        Exploit is public             \-
  any        Terminate any existing embargo                        Attacks observed              \-
  any        Monitor for exploit refinement                        SA                            \-
  any        Monitor for additional attacks                        SA                            \-
  any        Escalate response priority among responding parties   Coordination                  \-
  any        Promote fix deployment                                Accelerate deployment         \-

  : CVD Action Options for State $VFdPXA$
:::

## VFDpxa {#sec:VFDpxa}

Vendor is aware of vulnerability. Fix is ready. Fix has been deployed.
Public is unaware of vulnerability. No exploits have been made public.
No attacks have been observed.

*Previous State(s):* $VFdpxa$ (p.)

*Next State(s):* $VFDpxA$ (p.), $VFDpXa$ (p.), $VFDPxa$ (p.)

*Desiderata met:* $\mathbf{D} \prec \mathbf{A}$,
$\mathbf{D} \prec \mathbf{P}$, $\mathbf{D} \prec \mathbf{X}$,
$\mathbf{F} \prec \mathbf{A}$, $\mathbf{F} \prec \mathbf{P}$,
$\mathbf{F} \prec \mathbf{X}$, $\mathbf{V} \prec \mathbf{A}$,
$\mathbf{V} \prec \mathbf{P}$, $\mathbf{V} \prec \mathbf{X}$

*Desiderata blocked:* N/A

*Other notes:* Attack success unlikely. CVSS 3.1 Exploit Maturity:
Unproven (U) or Not Defined (X). CVSS 3.1 remediation level: Temporary
Fix (T) or Official Fix (O). Do not initiate a new disclosure embargo,
but an existing embargo may continue. Embargo continuation is viable.
SSVC v2 Exploitation: None. SSVC v2 Public Value Added: Precedence. SSVC
v2 Report Public: No. SSVC v2 Supplier Contacted: Yes. VEP does not
apply. See Table [10.25](#tab:VFDpxa_actions){reference-type="ref"
reference="tab:VFDpxa_actions"} for actions.

::: {#tab:VFDpxa_actions}
  Role   Action                                                   Reason                            Transition
  ------ -------------------------------------------------------- ------------------------------- --------------
  any    Publish vul and any mitigations (if no active embargo)   Defense                          $\mathbf{P}$
  any    Publish vulnerability                                    Document for future reference    $\mathbf{P}$
  any    Publish vulnerability                                    Acknowledge contributions        $\mathbf{P}$
  any    Monitor for exploit publication                          SA                                    \-
  any    Monitor for attacks                                      SA                                    \-
  any    Maintain vigilance for embargo exit criteria             SA                                    \-
  any    Maintain any existing disclosure embargo                 Coordination                          \-

  : CVD Action Options for State $VFDpxa$
:::

## VFDpxA {#sec:VFDpxA}

Vendor is aware of vulnerability. Fix is ready. Fix has been deployed.
Public is unaware of vulnerability. No exploits have been made public.
Attacks have been observed.

*Previous State(s):* $VFdpxA$ (p.), $VFDpxa$ (p.)

*Next State(s):* $VFDpXA$ (p.), $VFDPxA$ (p.)

*Desiderata met:* $\mathbf{D} \prec \mathbf{P}$,
$\mathbf{D} \prec \mathbf{X}$, $\mathbf{F} \prec \mathbf{P}$,
$\mathbf{F} \prec \mathbf{X}$, $\mathbf{V} \prec \mathbf{P}$,
$\mathbf{V} \prec \mathbf{X}$

*Desiderata blocked:* $\mathbf{P} \prec \mathbf{A}$,
$\mathbf{X} \prec \mathbf{A}$

*Zero Day Definitions Matched:* Zero Day Attack Type 3

*Other notes:* Attack success unlikely. CVSS 3.1 remediation level:
Temporary Fix (T) or Official Fix (O). Embargo is at risk. SSVC v2
Exploitation: Active. SSVC v2 Public Value Added: Precedence. SSVC v2
Report Public: No. SSVC v2 Supplier Contacted: Yes. VEP does not apply.
See Table [10.26](#tab:VFDpxA_actions){reference-type="ref"
reference="tab:VFDpxA_actions"} for actions.

::: {#tab:VFDpxA_actions}
  Role   Action                                                   Reason                            Transition
  ------ -------------------------------------------------------- ------------------------------- --------------
  any    Publish detection(s) for attacks                         Detection                        $\mathbf{P}$
  any    Publish vul and any mitigations (if no active embargo)   Defense                          $\mathbf{P}$
  any    Publish vul and any mitigations                          Defense                          $\mathbf{P}$
  any    Publish vulnerability                                    Document for future reference    $\mathbf{P}$
  any    Publish vulnerability                                    Acknowledge contributions        $\mathbf{P}$
  any    Terminate any existing embargo                           Attacks observed                      \-
  any    Monitor for exploit publication                          SA                                    \-
  any    Monitor for additional attacks                           SA                                    \-

  : CVD Action Options for State $VFDpxA$
:::

## VFDpXa {#sec:VFDpXa}

Vendor is aware of vulnerability. Fix is ready. Fix has been deployed.
Public is unaware of vulnerability. Exploit(s) have been made public. No
attacks have been observed.

*Previous State(s):* $VFDpxa$ (p.)

*Next State(s):* $VFDPXa$ (p.)

*Desiderata met:* $\mathbf{D} \prec \mathbf{A}$,
$\mathbf{D} \prec \mathbf{P}$, $\mathbf{F} \prec \mathbf{A}$,
$\mathbf{F} \prec \mathbf{P}$, $\mathbf{V} \prec \mathbf{A}$,
$\mathbf{V} \prec \mathbf{P}$, $\mathbf{X} \prec \mathbf{A}$

*Desiderata blocked:* $\mathbf{P} \prec \mathbf{X}$

*Zero Day Definitions Matched:* Zero Day Exploit Type 3

*Other notes:* Attack success unlikely. CVSS 3.1 Exploit Maturity: high
(H), functional (F), or proof of concept (P). CVSS 3.1 remediation
level: Temporary Fix (T) or Official Fix (O). Embargo is at risk. Expect
Public awareness imminently. SSVC v2 Exploitation: PoC. SSVC v2 Public
Value Added: Precedence. SSVC v2 Report Public: No. SSVC v2 Supplier
Contacted: Yes. VEP does not apply. See Table
[10.27](#tab:VFDpXa_actions){reference-type="ref"
reference="tab:VFDpXa_actions"} for actions.

::: {#tab:VFDpXa_actions}
  Role   Action                                                   Reason                            Transition
  ------ -------------------------------------------------------- ------------------------------- --------------
  any    Draw attention to published exploit(s)                   SA                               $\mathbf{P}$
  any    Publish detection(s) for exploits                        Detection                        $\mathbf{P}$
  any    Publish vul and any mitigations (if no active embargo)   Defense                          $\mathbf{P}$
  any    Publish vul and any mitigations                          Defense                          $\mathbf{P}$
  any    Publish vulnerability                                    Document for future reference    $\mathbf{P}$
  any    Publish vulnerability                                    Acknowledge contributions        $\mathbf{P}$
  any    Terminate any existing embargo                           Exploit is public                     \-
  any    Monitor for exploit refinement                           SA                                    \-
  any    Monitor for attacks                                      SA                                    \-

  : CVD Action Options for State $VFDpXa$
:::

## VFDpXA {#sec:VFDpXA}

Vendor is aware of vulnerability. Fix is ready. Fix has been deployed.
Public is unaware of vulnerability. Exploit(s) have been made public.
Attacks have been observed.

*Previous State(s):* $VFDpxA$ (p.)

*Next State(s):* $VFDPXA$ (p.)

*Desiderata met:* $\mathbf{D} \prec \mathbf{P}$,
$\mathbf{F} \prec \mathbf{P}$, $\mathbf{V} \prec \mathbf{P}$

*Desiderata blocked:* $\mathbf{P} \prec \mathbf{A}$,
$\mathbf{P} \prec \mathbf{X}$

*Zero Day Definitions Matched:* Zero Day Exploit Type 3, Zero Day Attack
Type 3

*Other notes:* Attack success unlikely. CVSS 3.1 Exploit Maturity: high
(H) or functional (F). CVSS 3.1 remediation level: Temporary Fix (T) or
Official Fix (O). Embargo is at risk. Expect Public awareness
imminently. SSVC v2 Exploitation: Active. SSVC v2 Public Value Added:
Precedence. SSVC v2 Report Public: No. SSVC v2 Supplier Contacted: Yes.
VEP does not apply. See Table
[10.28](#tab:VFDpXA_actions){reference-type="ref"
reference="tab:VFDpXA_actions"} for actions.

::: {#tab:VFDpXA_actions}
  Role   Action                                                   Reason                            Transition
  ------ -------------------------------------------------------- ------------------------------- --------------
  any    Draw attention to published exploit(s)                   SA                               $\mathbf{P}$
  any    Publish detection(s) for exploits                        Detection                        $\mathbf{P}$
  any    Publish detection(s) for attacks                         Detection                        $\mathbf{P}$
  any    Publish vul and any mitigations (if no active embargo)   Defense                          $\mathbf{P}$
  any    Publish vul and any mitigations                          Defense                          $\mathbf{P}$
  any    Publish vulnerability                                    Document for future reference    $\mathbf{P}$
  any    Publish vulnerability                                    Acknowledge contributions        $\mathbf{P}$
  any    Terminate any existing embargo                           Exploit is public                     \-
  any    Terminate any existing embargo                           Attacks observed                      \-
  any    Monitor for exploit refinement                           SA                                    \-
  any    Monitor for additional attacks                           SA                                    \-

  : CVD Action Options for State $VFDpXA$
:::

## VFDPxa {#sec:VFDPxa}

Vendor is aware of vulnerability. Fix is ready. Fix has been deployed.
Public is aware of vulnerability. No exploits have been made public. No
attacks have been observed.

*Previous State(s):* $VFdPxa$ (p.), $VFDpxa$ (p.)

*Next State(s):* $VFDPxA$ (p.), $VFDPXa$ (p.)

*Desiderata met:* $\mathbf{D} \prec \mathbf{A}$,
$\mathbf{D} \prec \mathbf{X}$, $\mathbf{F} \prec \mathbf{A}$,
$\mathbf{F} \prec \mathbf{X}$, $\mathbf{P} \prec \mathbf{A}$,
$\mathbf{P} \prec \mathbf{X}$, $\mathbf{V} \prec \mathbf{A}$,
$\mathbf{V} \prec \mathbf{X}$

*Desiderata blocked:* N/A

*Other notes:* Attack success unlikely. CVSS 3.1 Exploit Maturity:
Unproven (U) or Not Defined (X). CVSS 3.1 remediation level: Temporary
Fix (T) or Official Fix (O). Embargo is no longer viable. SSVC v2
Exploitation: None. SSVC v2 Public Value Added: Limited. SSVC v2 Report
Public: Yes. SSVC v2 Supplier Contacted: Yes. VEP does not apply. See
Table [10.29](#tab:VFDPxa_actions){reference-type="ref"
reference="tab:VFDPxa_actions"} for actions.

::: {#tab:VFDPxa_actions}
  Role   Action                                      Reason                        Transition
  ------ ------------------------------------------- ---------------------------- ------------
  any    Terminate any existing embargo              Vul is public                     \-
  any    Monitor for exploit publication             SA                                \-
  any    Monitor for attacks                         SA                                \-
  any    Close case (unless monitoring for X or A)   No further action required        \-

  : CVD Action Options for State $VFDPxa$
:::

## VFDPxA {#sec:VFDPxA}

Vendor is aware of vulnerability. Fix is ready. Fix has been deployed.
Public is aware of vulnerability. No exploits have been made public.
Attacks have been observed.

*Previous State(s):* $VFdPxA$ (p.), $VFDpxA$ (p.), $VFDPxa$ (p.)

*Next State(s):* $VFDPXA$ (p.)

*Desiderata met:* $\mathbf{D} \prec \mathbf{X}$,
$\mathbf{F} \prec \mathbf{X}$, $\mathbf{P} \prec \mathbf{X}$,
$\mathbf{V} \prec \mathbf{X}$

*Desiderata blocked:* $\mathbf{X} \prec \mathbf{A}$

*Other notes:* Attack success unlikely. CVSS 3.1 remediation level:
Temporary Fix (T) or Official Fix (O). Embargo is no longer viable. SSVC
v2 Exploitation: Active. SSVC v2 Public Value Added: Limited. SSVC v2
Report Public: Yes. SSVC v2 Supplier Contacted: Yes. VEP does not apply.
See Table [10.30](#tab:VFDPxA_actions){reference-type="ref"
reference="tab:VFDPxA_actions"} for actions.

::: {#tab:VFDPxA_actions}
  Role   Action                                 Reason                         Transition
  ------ -------------------------------------- ---------------------------- --------------
  any    Publish detection(s) for attacks       Detection                     $\mathbf{P}$
  any    Terminate any existing embargo         Vul is public                      \-
  any    Terminate any existing embargo         Attacks observed                   \-
  any    Monitor for exploit publication        SA                                 \-
  any    Monitor for additional attacks         SA                                 \-
  any    Close case (unless monitoring for X)   No further action required         \-

  : CVD Action Options for State $VFDPxA$
:::

## VFDPXa {#sec:VFDPXa}

Vendor is aware of vulnerability. Fix is ready. Fix has been deployed.
Public is aware of vulnerability. Exploit(s) have been made public. No
attacks have been observed.

*Previous State(s):* $VFdPXa$ (p.), $VFDpXa$ (p.), $VFDPxa$ (p.)

*Next State(s):* $VFDPXA$ (p.)

*Desiderata met:* $\mathbf{D} \prec \mathbf{A}$,
$\mathbf{F} \prec \mathbf{A}$, $\mathbf{P} \prec \mathbf{A}$,
$\mathbf{V} \prec \mathbf{A}$, $\mathbf{X} \prec \mathbf{A}$

*Desiderata blocked:* N/A

*Other notes:* Attack success unlikely. CVSS 3.1 Exploit Maturity: high
(H), functional (F), or proof of concept (P). CVSS 3.1 remediation
level: Temporary Fix (T) or Official Fix (O). Embargo is no longer
viable. SSVC v2 Exploitation: PoC. SSVC v2 Public Value Added: Limited.
SSVC v2 Report Public: Yes. SSVC v2 Supplier Contacted: Yes. VEP does
not apply. See Table [10.31](#tab:VFDPXa_actions){reference-type="ref"
reference="tab:VFDPXa_actions"} for actions.

::: {#tab:VFDPXa_actions}
  Role   Action                                   Reason                         Transition
  ------ ---------------------------------------- ---------------------------- --------------
  any    Draw attention to published exploit(s)   SA                            $\mathbf{P}$
  any    Publish detection(s) for exploits        Detection                     $\mathbf{P}$
  any    Publish vul and any mitigations          Defense                       $\mathbf{P}$
  any    Terminate any existing embargo           Vul is public                      \-
  any    Terminate any existing embargo           Exploit is public                  \-
  any    Monitor for exploit refinement           SA                                 \-
  any    Monitor for attacks                      SA                                 \-
  any    Close case (unless monitoring for A)     No further action required         \-

  : CVD Action Options for State $VFDPXa$
:::

## VFDPXA {#sec:VFDPXA}

Vendor is aware of vulnerability. Fix is ready. Fix has been deployed.
Public is aware of vulnerability. Exploit(s) have been made public.
Attacks have been observed.

*Previous State(s):* $VFdPXA$ (p.), $VFDpXA$ (p.), $VFDPxA$ (p.),
$VFDPXa$ (p.)

*Next State(s):* N/A

*Desiderata met:* N/A

*Desiderata blocked:* N/A

*Other notes:* Attack success unlikely. CVSS 3.1 Exploit Maturity: high
(H) or functional (F). CVSS 3.1 remediation level: Temporary Fix (T) or
Official Fix (O). Embargo is no longer viable. SSVC v2 Exploitation:
Active. SSVC v2 Public Value Added: Limited. SSVC v2 Report Public: Yes.
SSVC v2 Supplier Contacted: Yes. VEP does not apply. See Table
[10.32](#tab:VFDPXA_actions){reference-type="ref"
reference="tab:VFDPXA_actions"} for actions.

::: {#tab:VFDPXA_actions}
  Role   Action                                   Reason                         Transition
  ------ ---------------------------------------- ---------------------------- --------------
  any    Draw attention to published exploit(s)   SA                            $\mathbf{P}$
  any    Publish detection(s) for exploits        Detection                     $\mathbf{P}$
  any    Publish detection(s) for attacks         Detection                     $\mathbf{P}$
  any    Publish vul and any mitigations          Defense                       $\mathbf{P}$
  any    Terminate any existing embargo           Vul is public                      \-
  any    Terminate any existing embargo           Exploit is public                  \-
  any    Terminate any existing embargo           Attacks observed                   \-
  any    Monitor for exploit refinement           SA                                 \-
  any    Monitor for additional attacks           SA                                 \-
  any    Close case                               No further action required         \-

  : CVD Action Options for State $VFDPXA$
:::

# Acronym List {#acronym-list .unnumbered}

::: acronym
\[ATT&CK\]Adversarial Tactics, Techniques, and Common Knowledge
\[CNA\][CVE]{acronym-label="CVE" acronym-form="singular+short"}
Numbering Authority \[CNAs\][CVE]{acronym-label="CVE"
acronym-form="singular+short"} Numbering Authorities \[IODEF+\]Incident
Object Description Exchange Format Extensions

\[SANS Institute\]Sysadmin, Audit, Network, and Security Institute
\[US-CERT\][US]{acronym-label="US" acronym-form="singular+abbrv"}
Computer Emergency Readiness Team
:::

[^1]: Specifically, skill in our model will align with fulfilling the
    duty of coordinated vulnerability disclosure, duty of
    confidentiality, duty to inform, duty to team ability, and duty of
    evidence-based reasoning.

[^2]: CERT/CC Vulnerability Information and Coordination Environment
    (VINCE). <https://www.kb.cert.org/vince/>

[^3]: Although we do believe there is some value in exploit publication
    because it allows defenders to develop detection controls (e.g., in
    the form of behavioral patterns or signatures). Even if those
    detection mechanisms are imperfect, it seems better that they be in
    place prior to adversaries using them than the opposite.

[^4]: <https://www.zerodayinitiative.com/blog>. The ZDI blog posts were
    more directly useful than the monthly Microsoft security updates
    because ZDI had already condensed the counts of how many
    vulnerabilities were known ($\mathbf{P}$) or exploited
    ($\mathbf{A}$) prior to their fix readiness $\mathbf{F}$. Retrieving
    this data from Microsoft's published vulnerability information
    requires collecting it from all the individual vulnerabilities
    patched each month. We are grateful to ZDI for providing this
    summary and saving us the effort.

[^5]: Borrowing the terminology of quantum mechanics

[^6]: On the other hand, some vendors might actually prefer public
    awareness before fix deployment even if they have the ability to
    deploy fixes, for example in support of transparency or trust
    building. In that case, $\mathbb{D_V} \not\subseteq \mathbb{D}$, and
    some portions of the analysis presented here may not apply.

[^7]: "Silent patches" can obviously occur when vendors fix a
    vulnerability but do not make that fact known. In principle, silent
    patches could achieve $\mathbf{D} \prec \mathbf{P}$ even in
    traditional COTS or OSS distribution models. However, in practice
    silent patches result in poor deployment rates precisely because
    they lack an explicit imperative to deploy the fix.

[^8]: A [CVD]{acronym-label="CVD" acronym-form="singular+short"} embargo
    is analogous to a news embargo used in journalism, often in the
    context of scientific publications. Like [CVD]{acronym-label="CVD"
    acronym-form="singular+short"} embargoes, the use of scientific news
    embargoes is not without controversy.
    [@angell1991ingelfinger; @delkic2018embargo; @oransky2016embargo]

[^9]: It is of course appropriate to use discretion as to how much
    detail is released.

[^10]: Public awareness notwithstanding, an engaged adversary can begin
    using a public exploit as soon as it becomes available.

[^11]: The phrase *zero day* means many things to many people. We
    provide more formal definitions in
    §[6.5](#sec:defining_common_terms){reference-type="ref"
    reference="sec:defining_common_terms"}

[^12]: User concentration is one way to think about risk, but it is not
    the only way. Value density, as defined in [@spring2020ssvc] is
    another.

[^13]: We also admit our omission from consideration of whether
    utilitarianism is even the best way to approach these problems; and
    if it is, which variety of utilitarianism may be best suited. Such
    topics, while both interesting and relevant, lie too far afield from
    our main topic for us to to them justice here. We direct interested
    readers toward [@sep-utilitarianism-history] as an introduction to
    the general topic.

[^14]: https://ethicsfirst.org/
