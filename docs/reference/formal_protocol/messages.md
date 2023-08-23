# Message Types

In [States](./formal_protocol/states.md), we identified four main roles in the
MPCVD process:

- Finder/Reporter
- Vendor
- Coordinator
- Deployer
 
Here we will examine the messages passed between them.
Revisiting the definitions from the [Formal Protocol Introduction](./formal_protocol/index.md):,

> $\langle M_{ij} \rangle_{i,j=1}^N$ are $N^2$ disjoint finite sets with
> $M_{ii}$ empty for all $i$: $M_{ij}$ represents the messages that can
> be sent from process $i$ to process $j$.

The message types in our proposed MPCVD protocol arise primarily from the following principle taken directly from the 
[CVD Guide](https://vuls.cert.org/confluence/display/CVD/2.3.+Avoid+Surprise):

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

!!! note ""

    Participants whose state changes in the RM, EM, or CVD State Models SHOULD send a message to
    other Participants for each transition.

If you are looking for a one-sentence summary of the entire
MPCVD protocol, that was it.

!!! note inline end "State Transitions"

    -   RM state transitions $\Sigma^{rm} = \{ r,v,a,i,d,c\}$
    -   EM state transitions $\Sigma^{em} = \{ p,a,r,t\}$
    -   CVD state transitions
    $\Sigma^{cs} = \{\mathbf{V},\mathbf{F},\mathbf{D},\mathbf{P},\mathbf{X},\mathbf{A}\}$

As a reminder, those transitions are shown at right.

We will address the specific circumstances when each message should be emitted in
[Transitions](./formal_protocol/transitions.md), but first we need to 
introduce the message types this recommendation implies.
We cover messages associated with each state model, in turn, below, concluding the section with a few message types not
directly connected to any particular state model.

## RM Message Types

!!! tip inline end "Finders have hidden states"
    
    As we discuss in [RM Interactions](../topics/process_models/rm/rm_interactions/#the-secret-lives-of-finders),
    the Finder's states $q^{rm} \in \{R,I,V\}$ are not observable to the CVD process because Finders start 
    coordination only when they have already reached $q^{rm} = A$.

With the exception of the Finder/Reporter, each Participant's involvement in a CVD case starts with the receipt of a 
report from another Participant who is already in the $Accepted$ ($q^{rm} \in A$) state.
The remainder of a Participant's RM process is largely independent of the other Participants' RM processes.
Therefore, the RM message types are primarily used to inform other Participants of the sender's state.

<!-- this hr is just here to adjust vertical spacing between the inset above and the table below -->
---

| Message Type | Name | Description                                                                            |
| --- | --- |----------------------------------------------------------------------------------------|
| _RS_ | Report Submission | A message from one Participant to a new Participant containing a vulnerability report. |
| _RI_ | Report Invalid | A message indicating the Participant has designated the report as invalid.             |
| _RV_ | Report Valid | A message indicating the Participant has designated the report as valid.               |
| _RD_ | Report Deferred | A message indicating the Participant is deferring further action on a report.          |
| _RA_ | Report Accepted | A message indicating the Participant has accepted the report for further action.       |
| _RC_ | Report Closed | A message indicating the Participant has closed the report.                            |
| _RK_ | Report Acknowledgement | A message acknowledging the receipt of any RM message listed above.           |
| _RE_ | Report Error | A message indicating a Participant received an unexpected RM message.                  |


A summary of the RM message types is shown below.

!!! note "RM Message Types"

    $$M^{rm} = \{RS,RI,RV,RD,RA,RC,RK,RE\}$$

All state changes are from the Participant's (sender's) perspective, not the recipient's perspective.
We will see in [Transitions](./formal_protocol/transitions.md) that the receipt of a *Report Submission* is the 
only message whose *receipt* directly triggers an RM state change in the receiver.
All other RM messages are used to convey the sender's status.

!!! note ""

    Participants SHOULD act in accordance with their own policy and process in deciding when to transition states in the
    RM model.

!!! note ""

    Participants SHOULD NOT mark duplicate reports as invalid.

!!! note ""

    Instead, duplicate reports SHOULD pass through $Valid$ ($q^{rm} \in V$), although they MAY be subsequently
    (immediately or otherwise) deferred ($q^{rm} \in V \xrightarrow{d} D$) in favor of the original.
 
!!! note ""

    Participants SHOULD track the RM states of the other Participants in the case.

An example object model for such tracking is described in
{== §[\[sec:case_object\]](#sec:case_object.md){reference-type="ref"
reference="sec:case_object"} ==}.
Furthermore, while these messages are expected to inform the receiving Participant's choices in their own RM process,
this protocol intentionally does not specify any other recipient RM state changes upon receipt of an RM message.

## EM Message Types
 
Whereas the RM process is unique to each Participant, the EM process is global to the case.
Therefore, we begin with the list of message types a Participant SHOULD emit when their EM state changes.

| Message Type | Name | Description                                                                                                                                                                             |
| --- | --- |-----------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------|
| _EP_ | Embargo Proposal | A message containing proposed embargo terms (e.g., date/time of expiration).                                                                                                            |
| _ER_ | Embargo Proposal Rejection | A message indicating the Participant has rejected an embargo proposal.                                                                                                                  |
| _EA_ | Embargo Proposal Acceptance | A message indicating the Participant has accepted an embargo proposal.                                                                                                                  |
| _EV_ | Embargo Revision Proposal | A message containing a proposed revision to embargo terms (e.g., date/time of expiration).                                                                                              |
| _EJ_ | Embargo Revision Rejection | A message indicating the Participant has rejected a proposed embargo revision.                                                                                                          |
| _EC_ | Embargo Revision Acceptance | A message indicating the Participant has accepted a proposed embargo revision.                                                                                                          |
| _ET_ | Embargo Termination | A message indicating the Participant has terminated an embargo (including the reason for termination). Note that an *Embargo Termination* message is intended to have immediate effect. |
| _EK_ | Embargo Acknowledgement | A message acknowledging receipt of any of the above EM message types.                                                                                                                   |
| _EE_ | Embargo Error | A message indicating a Participant received an unexpected EM message.                                                                                                                   |

!!! note ""
    If an early termination is desired but the termination date/time is in the future, this SHOULD be achieved through
    an *Embargo Revision Proposal* and additional communication as necessary to convey the constraints on the proposal.

A summary of the EM message types is shown below.

!!! note "EM Message Types"

    $$M^{em} = \{EP,ER,EA,EV,EJ,EC,ET,EK,EE\}$$

## CS Message Types {#sec:cs_message_types}

From the [CS process model](../topics/process_models/cs/index.md), the following is the list of messages associated with CS state
changes:

| Message Type | Name | Description                                                                                                                                                                                                                                                                      |
| --- | --- |----------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------|
| _CV_ | Vendor Awareness | A message to other Participants indicating that a report has been delivered to a specific Vendor. Note that this is an announcement of a state change for a Vendor, not the actual report to the Vendor, which is covered in the *Report Submission* (_RS_) above.             |
| _CF_ | Fix Readiness | A message from a Participant (usually a Vendor) indicating that a specific Vendor has a fix ready.                                                                                                                                                                               |
| _CD_ | Fix Deployed | A message from a Participant (usually a Deployer) indicating that they have completed their fix deployment process. This message is expected to be rare in most MPCVD cases because Deployers are rarely included in the coordination effort.                                    |
| _CP_ | Public Awareness | A message from a Participant indicating that they have evidence that the vulnerability is known to the public. This message might be sent after a Participant has published their own advisory or if they have observed public discussion of the vulnerability.                  |
| _CX_ | Exploit Public | A message from a Participant indicating that they have evidence that an exploit for the vulnerability is publicly available. This message might be sent after a Participant has published their own exploit code, or if they have observed exploit code available to the public. |
| _CA_ | Attacks Observed | A message from a Participant indicating that they have evidence that attackers are exploiting the vulnerability in attacks.                                                                                                                                                      |
| _CK_ | CS Acknowledgement | A message acknowledging receipt of any of the above CS message types.                                                                                                                                                                                                            |
| _CE_ | CS Error | A message indicating a Participant received an unexpected CS message.                                                                                                                                                                                                            |

!!! note ""
    **Vendor Awareness** (_CV_) messages SHOULD be sent only by Participants with direct knowledge of the notification (i.e.,
    either by the Participant who sent the report to the Vendor or by the Vendor upon receipt of the report).



A summary of the CS message types is shown below.

!!! note "CS Message Types"

    $$M^{cs} = \{CV,CF,CD,CP,CX,CA,CK,CE \}$$

## Other Message Types {#sec:gen_message_types}

Finally, there are a few additional message types required to tie the coordination process together.
Most of these message types are *not* associated with a specific state change, although they might trigger activities or
events that could cause a state change in a Participant (and therefore trigger one or more of the above message types to
be sent).

| Message Type | Name | Description                                                                                                 |
| --- | --- |-------------------------------------------------------------------------------------------------------------|
| _GI_ | General Inquiry | A message from a Participant to one or more other Participants to communicate non-state-change information. |
| _GK_ | General Acknowledgement | A message from a Participant indicating their receipt of a GI message.            |
| _GE_ | General Error | A message indicating a general error has occurred.                                                          |

    
Examples of general inquiry messages include but are not limited to

-   asking or responding to a question
-   requesting an update on a Participant's status
-   requesting review of a draft publication
-   suggesting a potential Participant to be added to a case
-   coordinating other events
-   resolving a loss of Participant state synchronization

A summary of the General message types is shown below.

!!! note "General Message Types"

    $$M^{*} = \{ GI,GK,GE \}$$

## Message Type Redux

Thus, the complete set of possible messages between processes is
$M_{i,j} = M^{rm} \cup M^{em} \cup M^{cs} \cup M^{*}$.
For convenience, we collected these into the table below.

| Process Model | $M_{i,j}$ | Message Type | Emit When |
| --- | --- | --- |  |
| RM | RS | Report Submission | sender $\in A$ |
| RM | RI | Report Invalid | $R \xrightarrow{i} I$ |
| RM | RV | Report Valid | $\{R,I\} \xrightarrow{v} V$ |
| RM | RD | Report Deferred | $\{V,A\} \xrightarrow{d} D$ |
| RM | RA | Report Accepted | $\{V,D\} \xrightarrow{a} A$ |
| RM | RC | Report Closed | $\{I,D,A\} \xrightarrow{c} C$ |
| RM | RK | Report Acknowledgement | any valid RM message |
| RM | RE | Report Error | any unexpected RM message |
| EM | EP | Embargo Proposal | $\{N,P\} \xrightarrow{p} P$ |
| EM | ER | Embargo Proposal Rejection | $P \xrightarrow{r} N$ |
| EM | EA | Embargo Proposal Acceptance | $P \xrightarrow{a} A$ |
| EM | EV | Embargo Revision Proposal | $A \xrightarrow{p} R$ |
| EM | EJ | Embargo Revision Rejection | $R \xrightarrow{r} A$ |
| EM | EC | Embargo Revision Acceptance | $R \xrightarrow{a} A$ |
| EM | ET | Embargo Termination | $\{A,R\} \xrightarrow{t} X$ |
| EM | EK | Embargo Acknowledgement | any valid EM message |
| EM | EE | Embargo Error | any unexpected EM message |
| CS | CV | Vendor Awareness | $vfd \cdot\cdot\cdot \xrightarrow{\mathbf{V}} Vfd \cdot\cdot\cdot$ |
| CS | CF | Fix Readiness | $Vfd \cdot\cdot\cdot \xrightarrow{\mathbf{F}} VFd \cdot\cdot\cdot$ |
| CS | CD | Fix Deployed | $VFd \cdot\cdot\cdot \xrightarrow{\mathbf{D}} VFD \cdot\cdot\cdot$ |
| CS | CP | Public Awareness | $\cdot\cdot\cdot p \cdot\cdot \xrightarrow{\mathbf{P}} \cdot\cdot\cdot P \cdot\cdot$ |
| CS | CX | Exploit Public | $\cdot\cdot\cdot\cdot x \cdot \xrightarrow{\mathbf{X}} \cdot\cdot\cdot\cdot X \cdot$ |
| CS | CA | Attacks Observed | $\cdot\cdot\cdot\cdot\cdot a \xrightarrow{\mathbf{A}} \cdot\cdot\cdot\cdot\cdot A$ |
| CS | CK | CS Acknowledgement | any valid CS message |
| CS | CE | CS Error | any unexpected CS message |
| * | GI | General Inquiry | any time |
| * | GK | General Acknowledgement | any valid GI message |
| * | GE | General Error | any unexpected GI message |

!!! note "Message Types Formally Defined"

    $$  M_{i,j} =
            \left\{ 
            \begin{array}{l}
                    RS,RI,RV,RD,RA,RC,RK,\\
                    RE,EP,ER,EA,EV,EJ,EC,\\
                    ET,EK,EE,CV,CF,CD,CP,\\
                    CX,CA,CK,CE,GI,GK,GE\\
            \end{array}
            \right\}\textrm{ where $i \neq j$; $\varnothing$ otherwise; for $i,j \leq N$}$$


Message _formats_ are left as future work.


