# Project Ideas

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
