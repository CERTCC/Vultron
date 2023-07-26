# Report Management Process Model

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

In this page, we describe a high-level workflow for the CVD Report Management (RM) process. 
The RM process should be reasonably familiar to anyone familiar with [IT Service Management](https://en.wikipedia.org/wiki/IT_service_management) (ITSM) workflows such as problem, change, 
incident or service request management.
In particular, any workflow in which work items (e.g., incident reports, problem tickets, change requests) are received, validated, prioritized, and work is subsequently
completed, should map onto the RM process outlined in this chapter.

In the interest of maintaining the potential for interoperability among different organizations' internal processes, our protocol does not
specify intra-organizational subprocesses within each state, although we give examples of such subprocesses in 
{== {== §[\[sec:do_work\]](#sec:do_work){reference-type="ref"
reference="sec:do_work"} ==} ==}.
For further reference, [ISO/IEC 30111:2019(E)](https://www.iso.org/standard/69725.html) provides recommendations for Vendors' *internal* processes
that can be mapped into the RM process. We provide such a mapping in {== Appendix
[\[app:iso_crosswalk\]](#app:iso_crosswalk){reference-type="ref"
reference="app:iso_crosswalk"} ==}.

## RM State Machine

???+ note inline end "DFA Defined"
    A DFA is defined as a 5-tuple $(\mathcal{Q},q_0,\mathcal{F},\Sigma,\delta)
    ~$[@kandar2013automata]:

    - $\mathcal{Q}$ is a finite set of states.
    - $q_0 \in \mathcal{Q}$ is an initial state.
    - $\mathcal{F} \subseteq \mathcal{Q}$ is a set of final (or accepting)
    states.
    - $\Sigma$ is a finite set of input symbols.
    - $\delta$ is a transition function of the form $\delta: \mathcal{Q} \times \Sigma \xrightarrow{} \mathcal{Q}$.

In this section, we first cover the states themselves before proceeding
to a discussion of the transitions between them. Next, we provide a
discussion of the Participant-specific semantics of the state
transitions. We use DFA notation to describe our
RM model.

### RM States

Our proposed RM DFA models a report lifecycle containing seven states, defined below.


<!-- rm-state-machine-start -->
```mermaid
stateDiagram-v2
    direction LR
    state Reporting {
        R: Received
        [*] --> R : receive
    }
    state Validation {
        I: Invalid
        V: Valid
    }
    state Prioritization {   
        D: Deferred
        state Action {
            A: Accepted
        }
    }
    
    state Closure {
        C: Closed
        C --> [*]
    }

    R --> I: invalidate
    R --> V : validate
    I --> V : validate
    V --> A : accept
    V --> D : defer
    A --> D : defer
    D --> A : accept
    D --> C : close
    A --> C : close
    I --> C : close
```
<!-- rm-state-machine-end -->



???+ note inline end "RM States $\mathcal{Q}^{rm}$ Defined" 
    $$
        \begin{split}
        \mathcal{Q}^{rm} = \{ & \underline{S}tart, \\
                              & \underline{R}eceived,\\
                              & \underline{I}nvalid, \\
                              & \underline{V}alid, \\
                              & \underline{A}ccepted, \\
                              & \underline{D}eferred, \\
                              & \underline{C}losed \}
        \end{split}$$

In this example, we use underlined capital letters as a shorthand for
the state names. We use this convention throughout the remainder of this
report. Each Participant in a CVD case will have their own
RM state.

RM states are not the same as CVD case states. Case states follow the Householder-Spring model summarized
in [Case State Model](./case_state.md). Further discussion of the interactions of the RM and CS models is found
in [Model Interactions](./model_interactions.md).

#### The _Start_ (_S_) State

The _Start_ state is a simple placeholder state for reports that have
yet to be received. It is, in effect, a null state that no
CVD Participant
would be expected to reflect in their report tracking system. We include
it here because it is useful when modeling coordination
that spans multiple Participants in the [formal protocol](../formal_protocol/index.md).
Otherwise, the discussion until then will mostly ignore it.

#### The _Received_ (_R_) State

Reports initially arrive in the _Received_ state.

Vendors lacking the ability to receive reports will find it exceedingly
difficult if not impossible to participate in the
CVD process. Therefore,

!!! note ""
    Vendors SHOULD have a clearly defined and publicly available 
    mechanism for receiving reports.

Similarly, those who coordinate others' responses to vulnerability
reports also need to have a report receiving capability; otherwise, they
are not capable of coordinating vulnerability disclosures. Hence,

!!! note ""
    Coordinators MUST have a clearly defined and publicly available
    mechanism for receiving reports.

Exiting the _Received_ state requires a Participant to assess the
validity of a report. Note that validation is distinct from
prioritization, as covered in our description of the [_Valid_](#the-valid-v-state) state.
As an example, a Vendor might later choose to _defer_ further response on a _Valid_ report due to other priorities.

Validity criteria need not be limited to technical analysis. For
instance, a Coordinator might only accept reports within their specific
scope of concern and consider reports outside their scope to be
_Invalid_ even if they believe the report accurately describes a real
vulnerability. Alternatively, a Vendor might institute a policy
designating reports unaccompanied by a working proof-of-concept exploit
as _Invalid_ by default.

!!! note ""
    Participants SHOULD have a clearly defined process for
    validating reports in the _Received_ state.

!!! note ""
    Participants SHOULD have a clearly defined process for
    transitioning reports from the _Received_ state to the _Valid_ or
    _Invalid_ states.

!!! note ""
    Participants MAY perform a more technical report validation process
    before exiting the _Received_ state.

!!! note ""
    Regardless of the technical rigor applied in the validation process,
    Participants SHOULD proceed only after validating the reports they
    receive.

!!! note ""
    Participants SHOULD transition all valid reports to the _Valid_
    state and all invalid reports to the _Invalid_ state.

!!! note ""
    Regardless of the content or quality of the initial report, once a
    Vendor confirms that a reported vulnerability affects one or more of
    their product(s) or service(s), the Vendor SHOULD designate the
    report as _Valid_.

#### The _Invalid_ (_I_) State

Reports in the _Invalid_ state have been evaluated and found lacking by
the recipient. This state allows time for the Reporter to provide
additional information and for the receiver to revisit the validation
before moving the report to _Closed_.

The reasons for a report to be put in this state will vary based on each
recipient's validation criteria, and their technical capability and
available resources. The _Invalid_ state is intended to be used as a
temporary holding place to allow for additional evidence to be sought to
contradict that conclusion.

!!! note ""
    Participants SHOULD temporarily hold reports that they cannot
    validate pending additional information.

!!! note ""
    Participants SHOULD provide Reporters an opportunity to update their
    report with additional information in support of its validity before
    closing the report entirely.

!!! note ""
    Participants MAY set a timer to move reports from _Invalid_ to
    _Closed_ after a set period of inactivity.

#### The _Valid_ (_V_) State

Reports in the _Valid_ state are ready to be prioritized for possible
future work. The result of this prioritization process will be to either
accept the report for follow-up or defer further effort.

!!! note ""
    Once a report is in the _Valid_ state, Participants MAY choose to
    perform a shallow technical analysis on it to prioritize any further
    effort relative to other work.

!!! note ""
    Participants SHOULD have a bias toward accepting rather than
    deferring cases up to their work capacity limits.

In other words, prioritization is only necessary if the workload
represented by active valid reports exceeds the organization's capacity
to process those reports.

Prioritization schemes, such as [SSVC](https://github.com/CERTCC/SSVC) or the
[CVSS](https://first.org/cvss), are commonly used to
prioritize work within the CVD process; however, specific details are
left to Participant-specific implementation.[^1]

#### The _Accepted_ (_A_) State

The _Accepted_ state is where the bulk of the work for a given
CVD Participant
occurs. Reports reach this state for a Participant only once the
Participant has deemed the report to be both valid and of sufficient
priority to warrant further action. The _Accepted_ state has a different
meaning for each different Participant.

-   For our purposes, Finders/Reporters enter the _Accepted_ state only
    for reports that they intend to put through the
    CVD process. If
    they have no intention of pursuing CVD, there is no need for them to track
    their actions using this protocol. See [the secret lives of finders](#the-secret-lives-of-finders) for more.

-   Vendors usually do root cause analysis, understand the problem, and
    produce a fix or mitigation.

-   Coordinators typically identify potentially affected Vendors, notify
    them, and possibly negotiate embargoes.

We provide additional elaboration on the sorts of activities that might
happen in the _Accept_ state in
{== §[\[sec:do_work\]](#sec:do_work){reference-type="ref"
reference="sec:do_work"} ==} .

!!! note ""
    A report MAY enter and exit the _Accepted_ state a number of times
    in its lifespan as a Participant resumes or pauses work (i.e.,
    transitions to/from the _Deferred_ state).

#### The _Deferred_ (_D_) State

The _Deferred_ state is reserved for valid, unclosed reports that are
otherwise not being actively worked on (i.e., those in _Accepted_). It
parallels the _Invalid_ state for reports that fail to meet the
necessary validation criteria in that both states are awaiting closure
once it is determined that no further action is necessary.

For example, a Participant might use the _Deferred_ state when a valid
report fails to meet their prioritization criteria
[\[eq:prioritize_report\]](#eq:prioritize_report){reference-type="eqref"
reference="eq:prioritize_report"}, or when a higher priority task takes
precedence over an active report, as in
[\[eq:pause_report\]](#eq:pause_report){reference-type="eqref"
reference="eq:pause_report"}.

!!! note ""
    A report MAY enter and exit the _Deferred_ state a number of times
    in its lifespan as a Participant pauses or resumes work (i.e.,
    transitions from/to the _Accepted_ state).

!!! note ""
    Reports SHOULD exit the _Deferred_ state when work is resumed
    [\[eq:resume_report\]](#eq:resume_report){reference-type="eqref"
    reference="eq:resume_report"}, or when the Participant has
    determined that no further action will be taken
    [\[eq:close_report\]](#eq:close_report){reference-type="eqref"
    reference="eq:close_report"}.

!!! note ""
    CVD Participants MAY set a policy timer on reports in the _Deferred_
    state to ensure they are moved to _Closed_ after a set period of
    inactivity.

#### The _Closed_ (_C_) State

The _Closed_ state implies no further work is to be done; therefore, any
pre-closure review (e.g., for quality assurance purposes) should be
performed before the case moves to the _Closed_ state (i.e., while the
report is in _Invalid_, _Deferred_, or _Accepted_).

!!! note ""
    Reports SHOULD be moved to the _Closed_ state once a Participant has
    completed all outstanding work tasks and is fairly sure that they
    will not be pursuing any further action on it.

???+ note inline end "RM Start and End States ($q^{rm}_0, \mathcal{F}^{rm}$) Defined"
    
    The RM process
    starts in the _Start_ state.
    
    $$q^{rm}_0 = Start$$
    
    The RM process ends
    in the _Closed_ state.
    
    $$\mathcal{F}^{rm} = \{Closed\}$$


### RM

The actions performed in the RM process represent the allowed state
transitions in the corresponding DFA.

-   A Participant's RM process begins when the Participant
    receives a report.

!!! note ""
    Each Participant SHOULD subject each _Received_ report to some sort
    of validation process, resulting in the report being designated as
    _valid_ or _invalid_ based on the Participant's particular criteria.

In other words, the _Received_ state corresponds to the Validation phase
of *The CERT Guide to Coordinated Vulnerability Disclosure*
[@householder2017cert].

!!! note ""
    For _Valid_ reports, the Participant SHOULD perform a prioritization
    evaluation to decide whether to _accept_ or _defer_ the report for
    further work.

Similarly, the _Valid_ state is equivalent to the Prioritization
(Triage) phase of the *CVD Guide* [@householder2017cert]. The
SSVC model is
illustrative here, although any prioritization scheme could be
substituted as long as it emits a result that can be mapped onto the
semantics of "continue work" or "defer further
action" [@spring2021ssvc]. Appendix
[\[app:ssvc_mpcvd_protocol\]](#app:ssvc_mpcvd_protocol){reference-type="ref"
reference="app:ssvc_mpcvd_protocol"} takes a closer look at how
SSVC fits into the
protocol we are defining.

!!! note ""
    Participants SHOULD _close_ reports that require no further work
    (e.g., those that have been in _Invalid_ or _Deferred_ for some
    length of time, or those in _Accepted_, where all necessary tasks
    are complete.)

???+ note inline end "RM Symbols ($\Sigma^{rm}$) Defined"
    These actions constitute the set of symbols for the
    RM DFA. 

    $$
    \begin{align*}
      \Sigma^{rm} = \{ & \underline{r}eceive, \\
                       & \underline{v}alidate, \\
                       & \underline{i}nvalidate, \\
                       & \underline{a}ccept, \\
                       & \underline{d}efer, \\
                       & \underline{c}lose \}
    \end{align*}
    $$

#### RM Transitions Defined

In this section, we define the allowable transitions between states in
the RM process
model. The RM
process, including its states and transitions, is depicted in Figure
[\[fig:rm_states\]](#fig:rm_states){reference-type="ref"
reference="fig:rm_states"}.

##### Receive Report

To begin, a Participant must receive a report. Recall that the _Start_
state is a placeholder, so this action simply puts the receiving
Participant into the _Received_ state at the beginning of their
involvement in the case. 

```mermaid
stateDiagram-v2
    direction LR
    [*] --> Received: receive report
```

##### Validate Report

The Participant must validate the report to exit the _Received_ state.
Depending on the validation outcome, the report will be in either the
_Valid_ or _Invalid_ state. _Invalid_ reports are often waiting for
additional information from the reporter, but they may also be reports
that are not in scope for the Participant. Some Participants may choose
to close _Invalid_ reports immediately, while others may choose to
periodically revalidate them to see if they have become _Valid_.

!!! note ""
    Participants SHOULD create a case for all _Valid_ reports. 
    
!!! note ""
    Paricipants MAY create a case for _Invalid_ reports.

!!! note ""
    Participants MAY periodically revalidate _Invalid_ reports to
    determine if they have become _Valid_.

```mermaid
stateDiagram-v2
    direction LR
    state Received {
        state validate <<choice>>
        evaluate: Valid?
        [*] --> evaluate
        evaluate --> validate
    }
    state Invalid {
        state revalidate <<choice>>
        await: More info?
        [*] --> await
        await --> revalidate
        revalidate --> await: no change
    }
    validate --> Valid: validate (create case)
    validate --> Invalid: invalidate
    revalidate --> Valid: validate (create case)
```

##### Prioritize Report

Once a report has been validated (i.e., it is in the
RM _Valid_ state,
$q^{rm} \in V$), the Participant must prioritize it to determine what
further effort, if any, is necessary. 

!!! note ""
    Participants MUST prioritize _Valid_ cases.

{== Appendix
[\[app:ssvc_mpcvd_protocol\]](#app:ssvc_mpcvd_protocol){reference-type="ref" reference="app:ssvc_mpcvd_protocol"} ==} contains an example of how the
SSVC model can be applied here, although any prioritization scheme could be substituted.
Prioritization ends with the report in either the _Accepted_ or _Deferred_ state.

A Participant might choose to pause work on a previously _Accepted_
report after revisiting their prioritization decision. When this
happens, the Participant moves the report to the _Deferred_ state.
Similarly, a Participant might resume work on a _Deferred_ report,
moving it to the _Accepted_ state.

!!! note ""
    Participants MAY re-prioritize _Accepted_ or _Deferred_ cases.



```mermaid
stateDiagram-v2
    direction LR
    state Valid {
        state prioritize <<choice>>
        evalp: Priority?
        [*] --> evalp
        evalp --> prioritize
    }
    state Deferred {
        state reprioritize <<choice>>
        eval: Priority?
        wait: Wait
        [*] --> wait
        wait --> eval
        eval --> reprioritize
    }
    state Accepted {
        state reprioritize2 <<choice>>
        do_work: Do work
        evala: Priority?
        [*] --> do_work
        do_work --> evala
        evala --> reprioritize2
    }
    
    prioritize --> Accepted: accept
    prioritize --> Deferred: defer
    reprioritize --> Accepted: accept
    reprioritize --> wait: defer
    reprioritize2 --> do_work: accept
    reprioritize2 --> Deferred: defer
```


##### Participants Interact from the Accepted State

Some Participants (e.g., Finders and Coordinators) need to engage
someone else (e.g., a Vendor) to resolve a case. To do this, the
_sender_ Participants must also be in the _Accepted_ state; otherwise,
why are they working on the case? In the following diagram, we show the interaction between two
instances of the RM model: the left side represents the _sender_ while the right side represents the _recipient_.
Although the _sender_'s state does not change, the _recipient_'s state moves from _Start_ to _Received_.

!!! note ""
    Participants initiating CVD with others MUST do so from the _Accepted_ state.

```mermaid
stateDiagram-v2
    direction LR
    state Sender {
        direction LR
        other: ...
        [*] --> other
        other --> Accepted: accept
    }
    state Recipient {
        direction LR
        [*] --> Received: receive
    }
    Accepted --> Recipient: send
```

##### Case Closure

Finally, a Participant can complete work on an _Accepted_ report or
abandon further work on an _Invalid_ or _Deferred_ report.

!!! note ""
    Participants MAY close _Accepted_ or _Deferred_ cases or _Invalid_ reports.

```mermaid
stateDiagram-v2
    direction LR
    Accepted --> Closed: close
    Deferred --> Closed: close
    Invalid --> Closed: close
```

Our model assumes that _Valid_ reports cannot be closed directly without
first passing through either _Accepted_ or _Deferred_. It is reasonable
to wonder why _close_ is not a valid transition from the _Valid_ state.
The answer is that we wanted to allow prioritization and closure to be
distinct activities; deferral is reversible, whereas closure is not.
Often a Participant might initially _defer_ a case only to resume work
later, once more information has arrived. However, there is nothing
stopping a Participant from instituting a process that goes from _Valid_
to _Deferred_ to _Closed_ in rapid (even immediate) succession.

!!! note ""
    Participants MUST NOT close cases or reports from the _Valid_ state.


#### Possible Report Management Histories

???+ note inline end "RM Transition Function ($\delta^{rm}$) Defined"

    Following the state machine diagram above, we represent the RM process model as a right-linear grammar:
    
    $$\label{eq:rm_grammar}
    \delta^{rm} = 
    \begin{cases}
    S & \to rR \\
    R & \to vV~|~iI \\
    I & \to vV~|~cC \\
    V & \to aA~|~dD \\
    A & \to dD~|~cC \\
    D & \to aA~|~cC \\
    C & \to \epsilon \\
    \end{cases}$$

The strings generated in the language defined by this grammar can be
useful for exploring the possible sequences of states each report might
encounter for each Participant. The 15 shortest paths are _ric_, _rvac_,
_rvdc_, _rivac_, _rivdc_, _rvadc_, _rvdac_, _rivadc_, _rvadac_,
_rvdadc_, _rivdac_, _rivdadc_, _rvdadac_, _rivadac_, and _rvadadc_. Due
to the structure of the RM DFA, longer strings just add more
_defer_-_accept_ (_da_) or _accept_-_defer_ (_ad_) cycles prior to
closure (_c_). The usually limited duration of the
RM process coupled
with the tendency for CVD Participants to prefer to avoid frequent
starts and stops means that we expect the vast majority of reports to
follow one of the above paths, with the remainder falling into marginal
extensions. Further discussion of a reward function to evaluate
RM
DFA strings is
discussed as future work in
{== §[\[sec:rm_reward_function\]](#sec:rm_reward_function){reference-type="ref"
reference="sec:rm_reward_function"} ==}.

!!! note "RM DFA Fully Defined"
    Taken in combination, the full definition of the RM DFA is as follows:
    
    $$\label{eq:rm_dfa}
        RM = 
        \begin{pmatrix}
                \begin{aligned}
                    \mathcal{Q}^{rm} = & \{ S,R,I,V,A,D,C \} \\
                    q^{rm}_0 = & S  \\
                    \mathcal{F}^{rm} = & \{ C \} \\
                    \Sigma^{rm} = & \{ r,i,v,a,d,c \} \\
                    \delta^{rm} = &
                        \begin{cases}
                            S \to & rR \\
                            R \to & vV~|~iI \\
                            I \to & vV~|~cC \\
                            V \to & aA~|~dD \\
                            A \to & dD~|~cC \\
                            D \to & aA~|~cC \\
                            C \to & \epsilon \\
                        \end{cases}
                \end{aligned}
        \end{pmatrix}$$

???+ note "RM State Subsets Defined"
    
    Before proceeding, we pause to define a few useful subsets of
    RM states
    ($\dots \subset \mathcal{Q}^{rm}$) for future use:
    
    $$\label{eq:Qrm_subsets}
        \begin{align}
            Open &= \{ R,I,V,D,A \} \\
            Valid~Yet~Unclosed &= \{ V,D,A \} \\
            Potentially~Valid~Yet~Unclosed &= \{ R,V,D,A\} \\
            Active &= \{ R,V,A \} \\
            Inactive &= \{ I,D,C \} 
        \end{align}$$




[^1]: See also Appendix
    [\[app:ssvc_mpcvd_protocol\]](#app:ssvc_mpcvd_protocol){reference-type="ref"
    reference="app:ssvc_mpcvd_protocol"}, where we connect a few of the
    dots between SSVC and this protocol model.
