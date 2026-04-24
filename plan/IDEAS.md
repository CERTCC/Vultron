# Project Ideas

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
