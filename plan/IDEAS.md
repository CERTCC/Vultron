# Project Ideas

ID format: IDEA-YYMMDDNN

## IDEA-26042701 Implementation plan groups should be approximately Issue or PR sized

We should be thinking about the groups in implementation plans as being
approximately the size of an Issue or PR. We're going to need to migrate
back towards using Github Issues to capture chunky tasks that require
multiple steps to complete instead of having everything live in a single
implementation plan markdown file. The implementation plan should become
more of a tactical task tracking within an implementation phase, whereas we
could start capturing issues in Github for bigger chunks of work. Issues can
either have markdown checklists `- [ ] foo` or can use sub-issues to link
between big chunks and smaller chunks. But even the smaller chunks are not
necessarily single atomic tasks, so we still need a local-to-the-developer
implementation plan that will have the right level of granularity to track
implementation progress.

## IDEA-26042702 "History" files should be chunked by time to avoid unlimited growth

We have a number of `*HISTORY.md` files (implementation, ideas, priorities)
that are append-only and will grow indefinitely over time. We should consider
chunking these files by time (e.g., monthly) to avoid having the latest one
become too large to easily navigate. An agent that needs to review history
will most often be looking at recent history, so if the current month is always
the one that is being appended to, it will be more manageable. We could
develop a tool that agents can use to do something like `append-history`
with arguments for which history type (ideas, implementation, priorities)
and it could just use a date command like `date +"%y%m"` to generate the
filename suffix `IDEA-HISTORY-YYMM.md` and then append the text to that file.
The append part can be fully automated so that the agent doesn't have to
worry about which file to append to, or where in the file to insert, it just
knows to call the tool command we give it with the text to append (piping it
in, passing it as an argument, HERE files, etc. whatever make sense to
implement to make it easy for the agent to use and get it right the first time.)
History files should probably belong in their own folder (e.g., `plan/history/`)
instead of being in the `plan/` folder, since they are not really part of
the active planning process, but are more like a record of what has happened
over time.
