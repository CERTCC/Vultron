# Project Idea History

Ideas that have been processed into specs, notes, or implementation plans
are archived here for traceability.

---

## IDEA-260402-01 Config files should be YAML and loaded into a structured config object

relevant on or after commit: 3fdbfa96155d87d716027c5d3a1fb929d0968b28

When we have a need for config files, we should use YAML for readability and
ease of editing. We should also load the YAML config into a structured
config object using Pydantic so that we can enforce types and have a clear
schema for our configuration. Rough sketch of the workflow: Load YAML config
into a dict (`config_dict=yaml.safe_load()`), then pass that dict to a Pydantic
model (`Config.model_validate(config_dict)`) that defines the schema for our
configuration. This can also allow us to have nested configuration sections
for different components, and modularity in how we define and validate
config for different adapters or features.

**Processed**: 2026-04-23 — design decisions captured in
`specs/configuration.md` (CFG-01 through CFG-06) and
`notes/configuration.md`.

---

## IDEA-26040903 Do not worry about backward compatibility in prototype phase

We are still squarely in a prototyping phase, and there are no outside users
of the code we are developing here. When we make changes to the codebase we do
not need to worry about backward compatibility at all. If you're making a
change, make the change all the way. Do not hedge to preserve backward
compatibility (but obviously do not break the code in a way that prevents
you from testing your changes).

**Processed**: 2026-04-23 — design decisions captured in
`specs/prototype-shortcuts.md` (PROTO-08-001 through PROTO-08-004).

---

## IDEA-26041501 Need spec to avoid compatability shims in prototype

We need a spec that is declarative about avoiding the use of compatability
shims when refactoring code. We're in prototype development mode so there
are no
external dependencies that we need to maintain downstream. When we change
something it should be complete and permanent. Search notes/ for "shim" and
you'll see where this has come up before. We just need to make it an
explicit principle in the specs. Compatibility shims are technical debt that
we do not want to take on right now.

**Processed**: 2026-04-23 — folded into IDEA-26040903 processing; design
decisions captured in `specs/prototype-shortcuts.md` (PROTO-08-001 through
PROTO-08-004).

---

## IDEA-26041001 Outbox posting must have `to:` field requirement

The fact that D5-7-TRIGNOTIFY-1 even had to be a task is an indicator that
we are missing a requirement: Only activities can be posted to an outbox.
And activities must have a `to:` field. We are not supporting `bto:` or
`cc:` or `bcc:`, and so far we are assuming that all Vultron exchanges are
DMs. There
are no public messages (which in ActivityPub would be an Activity lacking a
`to:`). So we should make it a requirement (or two) that only activities
with a `to:` field can be posted an outbox, and this should be on the outbox
port itself as an acceptance criteria that raises an exception when violated.

**Processed**: 2026-04-23 — design decisions captured in
`specs/outbox.md` (OX-08-001 through OX-08-004) and `notes/outbox.md`.

---

## IDEA-26042201 append-only means append, not "insert at specific location"

I notice that agents often try to "insert at specific location in file" even
when the file is intended to be append-only, like the implementation history.
This is a sign that the agent is not fully understanding the intended use and
structure of the file. For append-only files, the agent should just be adding
new content to the end of the file, not trying to edit or rearrange existing
content. There is no need to read or understand the existing content in
order to add new entries to an append-only file. The equivalent of a shell
command like `echo "new entry" >> file.txt` should be the mental model for how to
handle append-only files. The agent should not be trying to parse the file and
figure out where to insert the new entry, it should just be adding it to the end.

**Processed**: 2026-04-23 — design decisions captured in
`specs/project-documentation.md` (PD-05-001 through PD-05-005) and
`notes/append-only-file-handling.md`.

---

## IDEA-26042301 Do not check existence of append-only files before appending

When adding entries to append-only files like the implementation history,
idea history, priority history, etc., there is no need to check for the
existence of the file before appending. The agent can just open the file in
append mode and write the new entry, and if the file does not exist it will
be created automatically. This simplifies the logic and avoids unnecessary
checks for file existence. The agent should just assume that the file is
there or will be created as needed when appending new entries.

Antipattern:

```text
Check if IDEA-HISTORY.md exists (shell)
│ ls /Users/adh/Documents/git/vultron_pub/plan/IDEA-HISTORY.md 2>/dev/null && echo "EXISTS" || echo "NOT FOUND"
└ 3
 lines...
```

**Processed**: 2026-04-23 — design decisions captured in
`specs/project-documentation.md` (PD-05-001 through PD-05-005) and
`notes/append-only-file-handling.md`.

## IDEA-26041704 Bugfix skill prematurely locks in on simple fixes

Sometimes the bugfix skill is used to fix a bug that has a simple surface
fix but is an indication of a deeper underlying issue that is not being
addressed. The agent is often overly narrow in its analysis of the scope and
does not currently ask enough questions to get to the true root cause of the
issue, resulting in more bugs later on that are related to the same
underlying issue. I want to update the bugfix skill to be more rigorous
itself, but also to have more explicit instructions for when to use the ask user
tool to have a conversation about the bug with the user so we can come to a
shared understanding before setting off on implementation. Sort of similar
to the "grill me" skill but for bugs. Ask the user to help you understand
the bug better, and check in periodically to ask the user if you are on the
right track in your analysis and implementation plan. You are not expected
to solve the entire problem in an autonomous one-shot way. Sometimes bugfix
analysis will lead to a recognition that there are multiple issues that must
be addressed in order to fully resolve the problem, and that is okay, but
the bugfix skill should recognize when that is the case and suggest breaking
the work into new tasks in the implementation plan and/or capturing
additional bugs.

**Processed**: 2026-04-23 — design decisions captured in
`specs/bugfix-workflow.md` (BFW-01 through BFW-04) and
`notes/bugfix-workflow.md`.

## IDEA-26042202 bugfix skill should move fixed bugs out of BUGS.md

The bugfix skill should be updated (and any relevant specs as well) to adopt
similar behavior to what the build skill does with implementation plan tasks.
Namely: When a bug is fixed, the implementation history file should be
appended and then the bug should be removed from BUGS.md entirely rather
than leaving a tombstone or summary behind. BUGS.md should only contain open
bugs, not closed ones.

**Processed**: 2026-04-23 — design decisions captured in
`specs/bugfix-workflow.md` (BFW-04-001 through BFW-04-004) and
`notes/bugfix-workflow.md`.

## IDEA-26041002 Default embargo should result in `EM.ACTIVE` not `EM.PROPOSED`

Contrary to what was implemented in `D5-7-EMSTATE-1`, when a default embargo
is applied to a newly created case, the resulting embargo state should be
`EM.ACTIVE`, not `EM.PROPOSED`. The rationale for this is that if the
reporter did not request otherwise, then the submission of the report signals
the reporter tacitly accepting the receiver's default embargo. So when a
case is created and a default embargo is applied, the embargo can be
considered to be active immediately. The reporter can always propose a
revision later if desired, but we don't want to leave the case in a limbo
state of `EM.PROPOSED`, which would imply that *no embargo exists* until the
reporter explicitly accepts the default embargo. See
`docs/topics/process_models/em/defaults.md` for more discussion.

**Processed**: 2026-04-24 — design decisions captured in
`specs/embargo-policy.md` (EP-04-001 through EP-04-004) and
`notes/embargo-default-semantics.md`. Implementation task added to
`plan/IMPLEMENTATION_PLAN.md` as EMDEFAULT-1.

## IDEA-26041601 Recurring problem: Actors assuming that everyone knows what they know

There appears to be a structural problem in the way that inter-Actor
communication is happening in the codebase right now (as of commit
70c28e544335f83d41aa17d332b59ed23c20958e). We've seen this in a few recent
bugs, including BUG-26041601 but that was not the first time it happened.
The root cause is that Actors are sending activities to other Actors using
object references instead of full objects when the receiver has no such
object in their system. Actors should not assume knowledge of objects that
they have in their system when communicating with other Actors. We saw this
with report submission. We saw this with case log distribution. And now
we're seeing with other things. It causes our semantic extraction and
therefore message routing to fail because Activities wind up with
'object=None' and fail to rehydrate properly. We need to
find all instances of this pattern in the codebase and fix them. There may
be a solution in tracking CaseLogEntries and what objects are known to have
been shared up to a particular log hash item. That would keep down on
duplicative object transmission, but that might be a lot of bookkeeping
compared to a simple rule like "always include the full object in an
activity when sending to another Actor". I'm not sure whether anything
beyond that is premature optimization or not.

**Processed**: 2026-04-24 — design decisions captured in
`specs/actor-knowledge-model.md` (AKM-01 through AKM-04) and
`notes/actor-knowledge-model.md`. Code audit and violation fixes deferred
to a follow-on implementation task.

## IDEA-26041602 Clarification on Actor knowledge assumptions in specs

`vultron/errors.py` contains the following docstring:

```text
    Outbound initiating activities (Create, Offer, Invite, Announce, Add,
    Remove, etc.) MUST carry a fully inline typed object so that recipients
    can determine the semantic type without a round-trip to the sender's
    DataLayer.  See specs/message-validation.md MV-09-001, MV-09-002.
```

What concerns me is the phrase "without a round-trip to the sender's
DataLayer". The concern is that Actors will *never* have access to each
others' datalayers, and this is not a possibility. This comment could be
read as saying that sometimes Actors can access each others' datalayers, but
that we are just avoiding doing that here for efficiency reasons. The
reality is that Actors will never have access to each others' datalayers.
This might just be a misguided statement in a docstring, or it might be an
indication of a deeper misunderstanding in the specs or codebase about how
Actors are supposed to interact with each other. We need to review the specs and
codebase to ensure that there is a clear and consistent understanding that
Actors do not, will not, must not have access to each others' datalayers, and
that inter-Actor comms always happens at the wire AS2 activity level.

**Processed**: 2026-04-24 — design decisions captured in
`specs/actor-knowledge-model.md` (AKM-01 through AKM-04) and
`notes/actor-knowledge-model.md`. The misleading docstring in
`vultron/errors.py` was corrected in the same commit.

---

## IDEA-260402-02 Does each participant need their own stub Case Actor clone to manage their copy of the case?

relevant on or after commit: d2d2e3b5c285c9af66fad717697e9795707d2978

One of the ideas of Vultron is that each participant in a case is able to
maintain their own copy of the case object, and that the main objective of
the protocol is to ensure that thes copies are kept in sync across
participants. That said, there is a distinction between the Actors who are
long-lived entities that represent people, organizations, services, etc.
that exist outside of cases, and Participants who are wrappers around such
actors providing context within a specific case. So Actor A might be a
reporter in one case, the owner of another, and the vendor in a third. But
each case is effectively operating independently at its own pace.

We have the idea of a Case Actor being created by the receiver of a report
who then decides to create a case based on that report. But the problem at
that point is that the case creator has a case object and a case actor, but
the reporter has neither of these things. So how does the reporter get their
own copy of the case object? This seems like it could be solved by the
receiver sending the reporter a CREATE activity containing a snapshot of the
case with the reporter already included as a participant in the case, and
the case would refer to the report that the reporter sent in the first place.
So now the reporter checks their open submissions and recognizes that this
is a case based on a report that they sent, and so they create their own
case object as a copy of the one in the CREATE activity, and they establish
a link between messages having the context of that case and the case object
in their system. Subsequent messsages from the case actor about that case
would need to include a reference to the case (in the context or something)
so that the reporter actor can recognize that this message is for the case.
So a message `To:` the reporter with a `context:` of the case ID would be
routed to a dedicated case handler in the reporters system that is
responsible for maintaining the reporter's copy of the case object. This is
in essence an update-only Case Actor owned by the reporter.

The finder/reporter could check the status of their local case copy and then
emit messages back to the "primary" case actor to update the case state as
needed, and those updates need to sync back via the case actor to the local
copy. (Hint: the local case should only accept updates `AttributedTo:` the
case actor, not from other actors, even if they are participants. Later on
we'll add cryptographic identities to enforce this, but for now we can just
have the case handler log as error but otherwise ignore any messages not
from the case actor that attempt to update the case state.)

This general model needs to be extended to all case participants, in fact.
Participants have their own copy of the case object. They need a mechanism
to sync their copy from the lead case actor. They need to post updates
directly to the lead case actor. The lead case actor is responsible for  
maintaining the "source of truth" and sending out updates to the participants.

We want to avoid the complexity of each Actor having a separate inbox from
their case-clone-maintainers, though, so the existence of the case replica
handler isn't something the primary case actor even really needs to be aware
of. They're just sending updates to the actors who are participants in the
case, and those actors have enough internal logic to recognize that this
message is destined for this case and that message is destined to another,
regardless of how many cases they might be involved in at any given time.
From the outside world, the Actor is the only addressible entity, and
there's only one Case Actor per case operated by the case creator/owner.
(Who is also an actor participant in the case as well, so they too have a
local copy of the case object and are not directly writing to their own copy
either but routing their updates through the Case Actor too).

**Processed**: 2026-04-24 — design decisions captured in
`specs/participant-case-replica.md` (PCR-01 through PCR-07) and
`notes/participant-case-replica.md`.

## IDEA-26041003 Differentiate between "demo" triggers and "normal" triggers

Some of the triggerable behaviors we have implemented only exist because we
need them to initiate events for the demos. They are not general purpose
triggers that we would expect to be used in the normal course of operations.
For example, an "Add(Note) to case" trigger is really specific to our demo.
But an "Add(object) to case" might be a more general trigger that could be
used for other purposes in the future. So when we are adding specific
triggers for demo purposes, we should consider whether they are exclusively
demo-centric triggers or if there is a generalized version that would be
worth implementing. If so, we should implement the generalized one, and
have the demo just use that with its specific object types or needs.

**Processed**: 2026-04-24 — design decisions captured in
`specs/triggerable-behaviors.md` (TRIG-08 through TRIG-10) and
`notes/trigger-classification.md`.

## IDEA-26041702 Generalize behavior nodes to avoid overfitting to the demo

There should not be a `CreateFinderParticipantNode` behavior. This is
overfitting the codebase to the demo. There should be a more general
`CreateCaseParticipantNode` behavior that can be used to create any type of
participant node. This is generally true of any behavior node that
explicitly references a specific role or type of participant. So in the BT
that creates a case from a report Offer, the participant is the
attributed_to Actor of the Offer(Report) with the role of reporter (we don't
actually know who the finder is at that point, we only know that they
reported it to us so they are the reporter). But for reuse purposes, the
same create participant node would be used for creating the case
creator/owner participant node first, and so the actor identity and the role
(s) would be parameters to the node, not hardcoded in the node itself.

**Processed**: 2026-04-24 — design decisions captured in
`specs/behavior-tree-node-design.md` (BTND-05-001 through BTND-05-003) and
`specs/configuration.md` (CFG-07-001 through CFG-07-004); implementation
guidance updated in `notes/bt-reusability.md`.

## IDEA-26041701 Clarification of intended control flow

Vultron is inherently designed to be an event-driven system. Messages arrive
and are processed into events that trigger behaviors. The same goes for core
interactions outbound from the system. When a message is added to the outbox,
it should be the outbox's job to process and deliver the message, not the
core's job to trigger it. When a demo injects an event into an actor to kick
off a demo, the actors behaviors should be responsible for processing that
event and generating the next steps, not relying on the demo script to
trigger events (except for events where the demo is explicitly simulating an
external stimulus that might be expected in real life, like a report
submission, or a case participant actor discovering that there is a public
exploit for the vulnerability and reporting that information as a status
update to the case, etc.). Demos are intended to show that the protocol AND
the behaviors behind the protocol are working together to produce the expected
outcomes. If the demo script is doing too much work to trigger events, then
the demo is not really demonstrating the protocol and behaviors, it's just
demonstrating that a demo script can pull the strings to make the system dance.
We need the demos to kick things off then get out of the way so that we can
see the system working as intended. Basically most processes in Vultron
should look like "on event do" rather than "upstream controls flow by
manipulating downstream events directly".

Extending this further, conceptually it looks like queues, sometimes topics,
and workers/processors that hang off of them, even if we don't have actual
queues or topics or workers implemented in the codebase. A different
implementation (or possible future
refactor) of Vultron might have a core that looks a lot more like a message
broker with queues and workers consuming from those queues. Some of that intent
is already present in the thinking that went into the design of the system
even though we are not implementing it that way in the prototype. So we
should preserve that intent in the way we write the code and structure the
interactions between components in the architecture. The prototype is geared
toward single process actors. A future production implementation might look
a lot more like a distributed system with separate services and message
queues with workers that handle individual use cases etc.

**Processed**: 2026-04-24 — design decisions captured in
`specs/event-driven-control-flow.md` (EDF-01 through EDF-05) and
`notes/event-driven-control-flow.md`.

## IDEA-26041703 Concern about behavior tree integration into design

The situation described in IDEA-26041702 is an example of a general concern
I have about whether or not we have truly captured the idea of the behavior
trees and how they are supposed to be used in the design, specs, and
codebase. The structure of the behavior logic is pretty clear in the
behavior tree structure file in notes/vultron-bt.txt but I am concerned the
BT notes and specs have misinterpreted the intent of the "trunkless branch"
idea to be overly literal. What was meant by "trunkless branch" was that
there are entire hierarchies of behavior trees that serve as reusable
branches that can be composed into larger behaviors. So things like
evaluating whether an embargo should be terminated based on a case update
shows up in multiple places in the BT structure. The idea was that this
logic would be implemented once as a reusable branch that could then be
composed into any larger behavior that needed that logic. Look at how
vultron/bt constructs the big tree that served as the origin of the BT
structure file and you'll see how we are reusing the same branches in
multiple places, and that the compositions themselves also serve as reusable
branches. There's a fractal pattern of behavior that comes through when you
understand that about the design. So far what I've seen is that we're
implementing a lot of one-off behaviors that are only used in one place and
then reconstructing nearly identical logic with different parameters in
other places, or sometimes avoiding building out behaviors in favor of just
putting logic directly in the code or demo scripts. The behavior tree
structure is meant to be the blueprint (and literal implementation structure)
of the internal logic of the system. Most of what you should be doing is
wiring up AS2 messages to use cases that trigger behaviors, and then a few
endpoints that trigger behaviors directly so that the demos can act as
puppeteers for the Actors involved in the demos. I don't know why there's a
tendency to avoid thinking in terms of behavior trees, but we need to
incorporate the use of behavior trees to capture process logic as a core
principle of how we build out the system.

**Processed**: 2026-04-24 — design decisions captured in
`specs/bt-composability.md` (BTC-01 through BTC-04) and
`notes/bt-composability.md`.

## IDEA-26042001 The Vultron-specific activities might make more sense as factory functions

Something I've observed in watching agents coding the implementation is that
often they get hung up on things like RmSubmitReportActivity as if it's a
full-blown class instead of just a convenience wrapper around an AS2 "Offer"
that happens to require a VulnerabilityReport as the object. I wonder if
maybe this "everything is a subclass" approach is actually making things
more complicated than necessary. For example, you could have something like
a factory method that:

```python
def rm_submit_report_activity(report: VulnerabilityReport, to: ActorID, 
                              **kwargs: dict) -> 
    as_Offer:
    return as_Offer(
        object_=report,
        to=[to],
        # other necessary fields and defaults
        **kwargs,
    )
```

This might completely eliminate the confusion around these
Vultron-customized activity types that are not really full-blown extensions
of AS2 activities but just convenience wrappers to create bog standard AS2
activities with the right fields and type hints for our use cases. This
might help us to also be able to specify the patterns to use in the semantic
extraction process as well. And it could even further decouple the core
logic from the AS2 message details.

**Processed**: 2026-04-24 — design decisions captured in
`specs/activity-factories.md` (AF-01 through AF-08) and
`notes/activity-factories.md`.

---

## IDEA-26042401 Priorities should be decoupled from the implementation plan

I don't like it when tasks are added to @IMPLEMENTATION_PLAN.md with the
priority either as the task name or the heading, etc. I want the PLAN to be
organized by topic areas with short ID tags, not by priority. The priority
should live in @plan/PRIORITIES.md which can just refer to those topic headings.
So instead of having a section in the plan called "Priority 100: Build the
fizzmonger" we should just have a section called "FIZZ-01: Build the
fizzmonger" with tasks "FIZZ-01-001: prepare the fizzmonger" etc. Then in
the PRIORITIES.md file we'd have a section called "## P100" that mentions that
FIZZ-01 tasks are part of that priority. This way the plan is organized by
topic and the priorities are organized separately. Rationale: Sometimes
priorities change but we still need to retain the tasks and topic groupings
because we're going to do the things, just not in the order they were
originally thought to be done. Changing this in the status quo means we have
to revise lots of tasks and headings in both files when priorities change
instead of just modifying the PRIORITIES.md file to reflect the new priority order.

**Processed**: 2026-04-24 — design decisions captured in
`specs/project-documentation.md` (PD-06-001 through PD-06-006) and
`notes/plan-organization.md`. Existing `plan/IMPLEMENTATION_PLAN.md` sections
migrated to `TASK-FOO` headings and dot-notation task IDs in the same commit.
