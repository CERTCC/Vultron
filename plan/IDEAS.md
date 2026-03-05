# Project Ideas

## ~~More thoughts on triggerable behaviors~~

> **Captured in:** `notes/triggerable-behaviors.md` (BT Node Classification,
> Three-Way Report Validation, Side Effects, SSVC Prioritization, Per-Behavior
> Design Notes, Placeholder Behaviors, Additional Candidate Behaviors,
> Invitation-Ready Case Object, Per-Participant Embargo Acceptance Tracking);
> `specs/triggerable-behaviors.md` (TB-02-001 reject-report, TB-02-003
> additional candidates, TB-03-001 offer_id, TB-03-003 note field);
> `mkdocs.yml` (typo fix).

~~Looking at the Report Management Behavior Tree (`docs/topcis/behavior_logic/rm_bt.md`),
the things that stand out at first glance as triggerable behaviors include:~~

- validate
- close
- prioritize

because these behaviors are kind of "chunky" and get reused elsewhere.
For example, observe that all three of them appear in more than one branch 
of the tree. This pattern indicates that they are already conceived as modular
behaviors that can be triggered from multiple parent behavior tree branches, 
so they are good candidates to be implemented as triggerable behaviors.

*However*, there is some nuance to this, because when we look 
closely at 
the 
"validate" behavior as described in `docs/topics/behavior_logic/rm_validation_bt.md`,
we see that it is composed of some nodes that represent condition checks, 
some that represent evaluation tasks, and some that are basically execution 
tasks.

(Note that Condition checks use the "stadium" node shape in mermaid diagrams.
But the mermaid diagrams were built by hand and might have errors or 
inconsistencies, so when in doubt, use the text of the documentation to resolve 
discrepancies.)

The parts that are evaluation tasks are the ones most likely to be 
associated with "fuzzer" nodes in the original simulation (see 
`notes/bt-fuzzer-nodes.md`), because they involve some kind of judgment or  
decision-making process that is not entirely specified. So from this 
perspective, it may not be possible to implement the entire "validate" 
behavior as a triggerable behavior, but maybe there is a "mark as valid" 
behavior that could be triggered that essentially would replace the "emit 
RV" node or another to replace the "emit RI" node that would handle the 
emission of the right message (in this case, `Accept(Offer)` or 
`TentativelyReject(Offer)`).

By analogy, if we're going to have triggerable "Accept(Offer(Report))" and 
"TentativelyReject(Offer(Report))" behaviors, then we will also need to have a 
triggerable "Reject(Offer(Report))" behavior as well, which would be the  
"hard close" option mentioned in the side note below.

### ~~Side note: Refining the report validation behavior structure~~

> **Captured in:** `notes/triggerable-behaviors.md` "Three-Way Report Validation"

~~The report validation behavior does not currently have a "hard
close" option that would result in a `Reject(Offer)` message being emitted,~~
but the protocol implementation does, so we should split the "D" branch of 
the diagram (and update text correspondingly) in `rm_validation_bt.md` to 
have a short branch where there a question of whether to "strong 
invalidate/hard close/reject" or "soft invalidate/tentatively reject". The 
change would also affect the "C" branch, because in a sense, both "evaluate 
credibility" and "evaluate validity" should produce some sort of data that 
is then evaluated against a policy to determine whether the resulting action 
is to accept, tentatively reject, or reject. Part of that evaluation might 
include some analyst notes as well as some flags like "credible: true/false"
and "valid: true/false" that are then fed into a policy engine that 
determines the resulting action. It seems likely that those might not be 
purely binary values, but might have one or two intermediate levels as well. 
This is a refinement of the simpler model described in the documentation.

### ~~Side effects of triggerable behaviors~~

> **Captured in:** `notes/triggerable-behaviors.md` "Side Effects of Emit FOO Behaviors"

~~Although in the diagram and docs it might look like "emit RV" is a simple~~ 
matter of sending a single message, note from elsewhere in the docs that 
validating a report has side effects as consequences like creating 
instantiating a case object, linking the reporter and receiver as 
participants to the case (receiver as owner), creating and 
attaching a CaseActor to it, triggering embargo resolution if not already 
complete, and so on. So the "mark as valid" behavior that would replace 
"emit RV" will need to be more complex than just sending a message, but it 
can still be modeled as a behavior tree with appropriate structure to cause 
those side effects to happen as well (think pre-condition checks, tasks to 
do things, post-condition checks to ensure that things happened, etc.) This 
caveat will be true of all such "emit FOO" replacements with triggerable behaviors,
because the original diagrams are simplified and do not show all the side  
effects that are described in the text of the documentation. So when we  
implement triggerable behaviors to replace "emit FOO" nodes, we will need  
to make sure that we capture all the relevant side effects in the structure  
of the behavior tree for that behavior, even if they are not explicitly  
shown in the original diagrams. (Code, notes, specs, docs and diagrams are 
all sources of truth, and they all need to be aligned, but they all have different
levels of detail and abstraction.)

### ~~Prioritization behavior~~

> **Captured in:** `notes/triggerable-behaviors.md` "SSVC-Based Prioritization"
> and "Placeholder Behaviors and Logging"

~~Again, when we look closer at~~ 
`docs/topics/behavior_logic/rm_prioritization_bt.md`, we see the same 
categories of nodes: condition checks, evaluation tasks, and execution tasks.
Condition checks can be implemented as direct API calls that return boolean  
values, and execution tasks (emit RA, emit RD) can be implemented as 
triggerable behaviors. 

"gather info" is rather generic and at present likely represents an external 
process that is just running continuously, which would make the "no new 
info" box turn into a condition check.

The "evaluate priority" node is expected to turn into a callout to a 
yet-unspecified behavior that will collect known information about the case, 
pass it to a series of SSVC evaluators that select decision 
point values (e.g., potential prompt to a human or LLM evaluator: "Given the 
information from the 
case, 
answer the following 
decision points as multiple choice questions and provide your answers. 
Deselect answers that can be ruled out by the information in the case, 
select answers that can be supported by information in the case. If you 
can't rule out an answer, select it. Explain your reasoning for your choices.
"). Then after the value selection has happened, an SSVC `DecisionTable` is 
applied to the selected values, and a prioritization outcome is produced. 
The simplified version of Vultron that we have in the documentation only 
discriminates on a binary outcome of "act" or "defer" (act is sometimes 
labeled as "accept" but we might need to avoid that to minimize confusion 
with the "accept offered report" activity). However, an actual SSVC based 
prioritization can have more than two outcomes. But for the prototype we can 
simplify our assumption to "defer" vs (anything else is equivalent to) "act",
which is basically captured in the "priority is not defer?" condition check 
in the current diagram.

The "accept" and "defer" nodes in the diagram are there as placeholders for 
local processes that might create side effects in internal systems. So they 
aren't really implementable here yet, they can just have a "always succeed" 
behavior that represents the fact that they are basically no-ops in the current implementation, but they are there to represent the fact that in a more complete 
implementation and are placeholders for callback hooks later.

As above, the "emit RA" and "emit RD" nodes can become triggerable behaviors,
and probably named "mark case as active" or "mark case as deferred" for 
names (follow naming conventions as appropriate)

### ~~Close report behavior~~

> **Captured in:** `notes/triggerable-behaviors.md` "Placeholder Behaviors and Logging"

~~We have a "close report" behavior in~~ 
`docs/topics/behavior_logic/rm_closure_bt.md`, and like "accept" and "defer" 
above, has a "close report" node that is really a placeholder for local 
processes to be determined. These placeholder nodes should emit log events 
when executed.

The "close criteria met" evaluation is underspecified and might represent a 
local policy evaluation based on facts of the case including case state, 
embargo state, etc. But it likely also requires some judgment regarding the 
state of the case based on the semantic content of the case history and 
notes. (E.g., "has the case been resolved? Is there any indication that the  
case is still active?").


### ~~Embargo Management Behaviors~~

> **Captured in:** `notes/triggerable-behaviors.md` "Per-Behavior Design Notes"

~~Many of the condition checks in the EM tree are mechanical value checks.~~

Some are judgment calls: "stop trying?", "current terms ok?" — these are 
questions to pose to a cognitive agent (human or LLM) that would be 
evaluating them in the context of the case and its history, along with the 
history of the participants and general experience in handling similar cases.
Some reporters or vendors might be more or less cooperative, or perhaps 
there are other constraints that make it more or less likely that an embargo 
agreement can be reached with them. Later elements in child trees like 
"willing to counter?" are of the same nature.

The "chunky" parts of the embargo management tree are "terminate", 
"evaluate", "propose" and "reject".

#### ~~Evaluate Embargo~~

> **Captured in:** `notes/triggerable-behaviors.md` "Embargo Evaluation"

~~"evaluate" in `docs/topics/behavior_logic/em_bt.md` is expanded in~~ 
`docs/topics/behavior_logic/em_evaluation_bt.md`, and it has similar 
components. "emit EA" may have side effects (enumerate these in notes, specs,
and docs as appropriate). The "Action" nodes are:

- evaluate
- accept
- propose

"evaluate" is part mechanical evaluation: does the proposed embargo meet the 
the policy criteria (note we have not yet defined how to express embargo 
policies). Does it have a valid end date? Is that date within an acceptable 
timeframe? 
And part judgment: is the justification for the embargo reasonable? Is the
proposed embargo duration appropriate given the circumstances? Is it 
commensurate with the case (are they asking for four years of embargo for a 
simple fix? are they asking for 2 days of embargo for a critical 
multi-vendor implementation that will require standards bodies to coordinate 
in order to resolve?) Does it generally follow the good practices outlined in 
`docs/topics/process_models/em/*.md`? 

The mechanical part can be implemented as a straightforward behavior tree.

The judgement part could be another placeholder to ask for help from a human 
or LLM evaluator, with a prompt that provides the relevant context (case, 
plus questions like those above).


#### ~~Propose Embargo~~

> **Captured in:** `notes/triggerable-behaviors.md` "Embargo Proposal";
> `mkdocs.yml` (typo fix applied).

~~Continuing an emergent theme, there are condition checks, evaluation tasks,~~ 
and execution tasks in the "propose embargo" behavior as well.
Emit EV, Emit EP are things that may have side effects (consult the rest of 
the documentation to find those). EM and CS state checks are straightforward 
condition checks. "Select terms" might be a judgment call, but it can be 
stubbed out as an "apply default policy" (see discussion of default policies 
in `docs/topics/process_models/em/defaults.md`) followed by a placeholder 
that could allow "customize defaults" but be stubbed out as a no-op for the 
prototype (again, placeholders should log when executed to show that they're 
happnening).

**Documentation bug:** There is a typo in the `mkdocs.yml` where "Propose 
Embargo Behavior" is misspelled as "Propse Embargo Behavior". This should be 
fixed in the navigation (filename is okay: `em_propose_bt.md`).

#### ~~Terminate Embargo~~

> **Captured in:** `notes/triggerable-behaviors.md` "Embargo Termination"

~~"other reason?" is a judgment call. "Emit ET" and "emit ER" are execution~~ 
tasks that may have side effects. "timer expired?" is a condition check that 
can directly query the current time against the embargo end date in the case.

"exit embargo" is another local process placeholder that is there for a 
callback hook to trigger external processes in the future.


### ~~Assign CVE ID behavior~~

> **Captured in:** `notes/triggerable-behaviors.md` "CVE ID Assignment";
> `specs/triggerable-behaviors.md` TB-02-003.

~~`docs/topics/behavior_logic/id_assignment_bt.md` has a simplified tree based~~ 
on the CNA assignment rules, and some of its condition checks can be 
implemented as lookups on a case ("id assigned?"). Some are about the actor 
("is CNA?"). Others might be judgment calls or evaluations against a rule 
set ("in scope?", "assignable?") CNA rules are defined in "4.1 Vulnerability 
Determination" https://www.cve.org/resourcessupport/allresources/cnarules#section_4_CNA_Operational_Rules"
The rules defined there can likely be built into a series of question and 
answers that lead the evaluator through the decision process. This is ripe 
for automation or at least automation assistance (e.g., prompting an 
evaluator with the case as context, asking them to answer a series of 
questions based on the requirements in the CNA rules)

### ~~Identify Participants Behavior~~

> **Captured in:** `notes/triggerable-behaviors.md` "Identify Participants";
> `specs/triggerable-behaviors.md` TB-02-003.

~~Although this is a judgment call, it's one that is informed by understanding~~ 
the case/report and who the affected parties are. So it's something that can 
become a human-in-the-loop behavior or could be an LLM-assisted behavior 
where the LLM is prompted to suggest potential participants based on the 
case information, and then a human can review and confirm or modify the 
suggestions. Note that the "suggest new participant" process is already 
supported semantically within the protocol, so there's the potential for a 
sort of agent whose job is to evaluate a case, look up potential participant 
contacts, and propose participants to the case. Then the normal case owner 
accept/reject of those proposals can be used to in turn trigger invitations 
to the accepted suggestions.

### ~~Notify Others Behavior~~

> **Captured in:** `notes/triggerable-behaviors.md` "Notify Others",
> "Invitation-Ready Case Object", "Per-Participant Embargo Acceptance Tracking";
> `specs/triggerable-behaviors.md` TB-02-003, TB-03-001.

~~This process seems pretty straightforward to automate as behaviors. The~~ 
"recipient policy compatible?" condition check is really a policy comparison 
to the existing case embargo (if any). (In fact, it would be easier for the 
process to require that an embargo be established on the case before the 
notify others behavior starts.) "effort limit exceeded?" is a judgment call 
that could reflect a policy, but can be stubbed as another no-op placeholder.

The "send report" at this level is not so much about `Offer(Report)` as it 
is about `Invite(Actor,Case)`. Note that the embargo resolution thing needs 
to be hammered out first before the `Invite` is sent though, because we 
don't want to invite Actors to cases when they have not yet agreed to the 
embargo terms. However, that could be as simple as inviting them to a case 
with their acceptance of the embargo implied as their acceptance of the 
invitation. That means that any version of the case shared pre-embargo 
agreement would need to not include the full report or case history details 
including any discussion among prior participants UNTIL such time as the 
invitation is accepted. This might imply the need for a secondary 
"invitation-ready case object" that is a stripped down version of the case 
that can be shared with potential participants to allow them to evaluate the 
case and the embargo terms before accepting, and then once they accept, they
get added as a participant to the full case. 

Side note: The paragraph above also implies the potential need for 
VulnerabilityCase objects to track embargo acceptance at a per-participant 
level. This could be an addition to the Participant Status object that is 
already there. Since cases can have a series of embargos over time (but only 
one active at a time), it might be useful to track which embargos a 
participant has explicitly accepted and ensure they have always accepted the 
latest one. If they've accepted previously but have not yet accepted the 
latest one, they might need to accept the new one before receiving any 
further updates to the case. This refinement could also address the some of 
the items in VP-05-* about participants signaling their intent to comply 
with embargoes.



The rest of the process is basically a loop iterator ("for recipient in 
recipients: ...") This could be triggered as a one-off after an individual 
proposed participant is accepted, or could be a loop over a queue of 
proposed participants if needed. Direct event-driven triggering of the 
behavior (as a single iteration of the loop) is probably ideal, because it 
can always be wrapped in a loop if needed, but it allows it to be triggered 
on demand as soon as there's someone new to invite. 

### ~~Fix development behavior~~

> **Captured in:** `notes/do-work-behaviors.md` "Fix Development: Automation
> Potential and Future Direction".

~~This is entirely underspecified in the documentation, and one version of it~~ 
is just that fix development happens outside of the Vultron code and reports 
back. And this is where "create fix" might just be a placeholder. However, 
there's also the possibility that this could plug into something that 
automates the fix creation (feed the source code and vul report and case 
details into the right agent and have it propose a fix). We are not trying 
to implement automated fixes at this time, but we already recognize the 
potential for this to be automated in the future. So we should ensure that 
the notes reflect this potential direction.

### ~~Out of scope behaviors~~

> **Captured in:** `notes/do-work-behaviors.md` "Not Implementable Inside Vultron"
> and "Do-Work Parallel Node: Preconditions".

~~Don't bother with any of these "do work" behaviors for the prototype (from~~ 
`docs/topics/behavior_logic/do_work_bt.md`). They are all external processes 
that are not in scope for either the prototype or initial implementation.

- deployment
- publication
- monitor threats
- acquire exploit
- other work

Also, the parallel node that is the parent of all these might need to be 
rethought, because for each subnode of that parallel node (even the ones we 
have discussed 
here like assign CVE ID, report to others) there is probably some set of 
preconditions that could be defined to determine when that behavior should 
be triggered. This is one of those places where the design documentation 
simplifies something that will likely be a bit more complex in practice, but 
it also highlights the need to ensure that we capture the relevant 
preconditions to trigger some of these behaviors.


### ~~General notes on triggerable behaviors~~

> **Captured in:** `notes/triggerable-behaviors.md` (Placeholder Behaviors,
> Side Effects, "mark x as y" pattern); `specs/triggerable-behaviors.md`
> TB-03-003 (note field requirement).

~~Keep track of all the places where we've identified the need for placeholder~~ 
behaviors, cross reference these with the `notes/bt-fuzzer-nodes.md` items too.

"emit FOO" messages (which will result in an outgoing activity) will need to 
support inclusion of a comment / content / note with some explanation at 
times (why are we rejecting this report? why are we proposing an embargo 
change? why did the embargo terminate?) This should be accommodated in the 
ActivityStreams object model, so it should be easy enough to include, but we 
need to make sure we capture the need for this as a requirement.

Note that there are more than a few "mark x as y" behaviors that can 
implement portions of the "emit FOO" behaviors including side effects and 
emission of appropriate messages. Look for other opportunities for similar 
things as you review the documentation, processes, and code.

The documentation in `docs/topics/behavior_logic/` is currently a simplified 
version of the process we are actually implementing. We should be careful to 
ensure that as the implementation process unfolds, we are capturing any 
additional complexity or nuance that we encounter in the implementation process
and reflecting that back in the documentation as well as in the notes and 
specs as appropriate. Note that the files in `docs/` are meant for humans 
and others not working on the implementation to understand the design and 
process, while `notes/` and `specs/` are intended to capture details of use 
to the implementers, human and machine alike. So the documentation in 
`docs/` needs to be clear and concise but does not need to capture every 
detail, while the notes and specs should be more comprehensive and detailed 
to ensure that the implementation is well-informed and captures all the  
necessary subtle details and edge cases that may not be fully reflected in 
the higher level documentation.