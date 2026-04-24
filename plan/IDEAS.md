# Project Ideas

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
