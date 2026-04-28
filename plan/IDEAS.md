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

## IDEA-26042801 `build` skill should be clear on distinction between "notes" and "history"

The `build` skill has sometimes resulted in updates to
`plan/IMPLEMENTATION_NOTES.md` that are largely just status updates that are
better suited for the `plan/IMPLEMENTATION_HISTORY.md` file. The difference
in intent is that `IMPLEMENTATION_HISTORY.md` is for "what was done" whereas
`IMPLEMENTATION_NOTES.md` is for "what was learned". The `build` skill should
be clear on this distinction and should aim to put information in the right
place. If it's a status update or summary of what was done, it should go in the
history file. If it's an insight, learning, or lesson that could inform future
work, it should go in the notes file. This will help keep the notes file
focused on actionable knowledge that can be extracted and applied, while the
history file serves as a chronological record of implementation progress.

Perhaps consider changing name from `IMPLEMENTATION_NOTES.md` to `IMPLEMENTATION_LEARNINGS.md`
or `BUILD_LEARNINGS.md` to make the distinction clear in the name itself.
Also we should do a similar "migrate to history" process for whatever this
file ends up being called to move processed items (e.g., during `learn`
skill) from the `LEARNINGS` file into the appropriate `HISTORY` file, to keep
the learnings file focused on unprocessed insights that have not yet been
digested into durable specs or notes.

Also clarify that when updating the implementation plan, any "things you
should know when implementing" should go into `notes/` files instead of the
learnings file so that learnings are a focused channel for build to send
information back upstream.

A change like this will need to touch multiple files since we refer to the
`IMPLEMENTATION_NOTES.md` in a lot of docs and skills. We should make sure
to update all of them as part of any resulting change. Possibly also need to
update either `specs/` or `notes/` files that address which files are
intended for which use too.

Also note that IDEA-26042702 has relevant implications for managing history
files over time that will matter here as well.
