# Project Ideas

## Evaluate readiness and upgrade to Python 3.14

Python 3.14.3 is the latest stable Python release as of this writing. Since
we have been developing the prototype using Python 3.12 and 3.13, we should
try an upgrade in a branch to 3.14 to see if everything works as expected so
we can take advantage of the latest language features and improvements. If
it works without issue, we can make it permanent. Otherwise we can abandon
the upgrade and stay with what we have.

## Get rid of `as_` prefix on fields across the board

The difference between when to use `as_object` and `object_`  (and
all other `as_<python_keyword>` vs `<python_keyword>_` fields) depending on
which vultron submodule you're in is a source of confusion and inconsistency.
We should just go through and standardize on the "trailing underscore"
convention for all fields across the codebase where there is a conflict with
a Python reserved keyword. (Note that *prefixing* with an underscore is not
an option because these are not private fields to begin with, and Pydantic will
complain about private fields with leading underscores.) So
underscore-suffix is the way to go for all fields that conflict with
reserved keywords. Create a task to do a global search and replace for any
`as_` prefixed fields and replace them with the trailing underscore
convention. E.g., `as_foo` becomes `foo_`. Note that this requirement only
applies to fields, not to class names where the `as_` prefix is actually  
helpful to indicate that it's an ActivityStreams-specific model. Update  
`specs/`, `notes/`, `AGENTS.md`, `plan/` docs as appropriate to reflect this
new naming convention (but only where the `as_` prefix is used in the
context of a field name).

## Treat test warnings as errors to be fixed

Test suite warnings from pytest are a sign of technical debt and potential
issues that need to be addressed in the codebase. It is not acceptable to
commit code that generates warnings in the test suite, as this can lead to
overlooked problems and a degraded code quality over time. Update `pyproject.
toml` to reflect the expectation that warnings are errors (hint: tool.pytest.
ini_options, filterwarnings, error). Then update `AGENTS.md`, `specs/`,
and `.github/skills/**/SKILL.md` and any other relevant files where `pytest`
invocation may need to be updated to reflect this change.

## Clarify that IMPLEMENTATION_HISTORY.md is intended to be appended

IMPLEMENTATION_HISTORY.md is intended to serve as an append-only log of
completed tasks, with new entries added to the end of the file as tasks are
completed. We have had instances where agents have inserted new entries at
the top or in the middle of the file. This needs to be addressed in the
documentation to clarify that new entries should always be appended to the
end of the file. Update `plan/IMPLEMENTATION_HISTORY.md` to include a clear
note at the top of the file stating that this file is intended to be an
append-only log and that new entries should always be added to the end of
the file. Also update `AGENTS.md`, and any relevant `specs/*.md` or `.
github/skills/**/SKILL.md` files to reflect this expectation in agent
behavior when updating IMPLEMENTATION_HISTORY.md.

## Github actions MUST pin versions to specific commit SHAs

Github actions that are used in our workflows must pin versions to specific
commit SHAs rather than just to a version tag. Version tags can be moved or
updated, which can lead to unnecessary supply chain risks if an attacker is
able to compromise the repository to change a tag. By pinning to a specific
commit SHA, we ensure that our workflows are using a specific, known version
of the action that cannot be changed without our knowledge. This needs to be
an ADR (`docs/adr/`) and reflected in the `specs/*.md` where appropriate. A
task to audit our existing Github actions and update any that are not currently
pinned to specific commit SHAs should be added to the implementation plan as
well.

## Review and update outdated `notes/` files

There are a number of `notes/` files that contain forward-looking statements
that have since been implemented, are no longer relevant, or need to be
updated to reflect the current state of the codebase. A review of these
files should be conducted to identify any outdated information and update it
accordingly. This will require a careful review of the `notes/` files in
comparison with the `IMPLEMENTATION_HISTORY.md`, and potentially
confirmation within the codebase itself to verify statuses and completeness.

Some notes may have been
snapshots-in-time that were relevant at the time they were created but if
everything they described has since been implemented, they can be removed.
This would include things like older code or architecture reviews that have
been fully addressed (or sufficiently addressed that the remaining items fit
better elsewhere in another note for example). `notes/state-machine-findings.
md`, `notes/datalayer-refactor.md`, etc. are examples of this, but a full
review should be conducted to identify others that may be in a similar state.

Because this is bigger than a normal "learn" tasks, and requires significant
focused attention to detail, this is better suited to be a follow-up task in
its own right rather than being completed within the current "learn" cycle.
A clear and detailed task should be added to the implementation plan to perform
this review and update, with a focus on ensuring that the `notes/` files  
accurately reflect
the current state of the project and do not contain outdated or misleading
information. Apply an editorial pass on notes/: update concrete status language
("not yet implemented" → "implemented in Phase X"), fix module paths to their
canonical current locations (see IMPLEMENTATION_HISTORY phases P60–P75),
and mark historical items where appropriate.

It is important that the
`notes/` files are kept up to date as they are a key resource for agents and
developers to understand the history, rationale, and current state of the
project.

## Expand task D5-1 to include an architectural review and specs updates

Task D5-1 in the implementation plan currently focuses on

> Confirm the PRIORITY-200 CA-2 follow-up is complete and refresh
> demo assumptions for isolated actor/container scenarios before implementing
> the multi-actor demos.

But we should expand this task to review the current architecture as
specified in `specs/` and as implemented in the codebase, and clarify
assumptions prior to embarking on D5-2 and later multi-actor demo
implementations.

## Implement replicated log synchronization for CaseActor followers

Build a distributed append-only log with eventual consistency using
RAFT-inspired primitives, leveraging AS2 Announce activities as the transport
layer. The CaseActor (acting as a de facto lead) maintains authoritative case
event history and replicates it to Participant Actors (followers) via log
synchronization. Implement this in phases: (SYNC-1) local append-only log
with
indexing, (SYNC-2) one-way replication with strict conflict handling (reject
mismatched prev_log_index, retry with decremented index), (SYNC-3) full sync
loop
with retry/backoff, and (SYNC-4) multi-peer synchronization with per-peer
replication
state. This approach treats the log as the system of record—all case state is a
projection of logged events—and ensures that all replicas eventually converge to
identical histories without requiring leader election or membership changes.

Place replication logic in core domain (for example you might consider
transport-agnostic
`CaseEventLog`,
`ReplicationState`, `LogSyncEngine`, and `ConsistencyRules` classes); implement
AS2 Announce mappings and persistence in adapters (outbound Announce, inbound
handler responses, file/database log storage). Use idempotent log appends,
message deduplication by event ID, and causal timestamp ordering to handle
duplicates and out-of-order delivery. Define explicit replication ports (
`OutboundReplicationPort`, `InboundReplicationPort`) to maintain hexagonal
architecture boundaries. Avoid premature commitment to leader election or actor
mobility; Phase SYNC-2 can introduce soft leadership (preferred writer) and
Phase SYNC-3 and SYNC-4
can add full RAFT with quorum commit once the log foundation is solid and
well-tested across 2–3 node scenarios.

SYNC-2 will need to rectify the
concept of "leadership" with the existing concept of Case Owner, which is a
separate concern. Case Ownership is about who gets to control the case
lifecycle and make certain decisions, whereas replication leadership is
about which node is currently responsible for accepting writes to the log
and replicating them to followers. We need to ensure that these concepts are
clearly delineated and do not conflict with each other as we evolve the
design. In the future, a case ownership transfer likely implies that
replication leadership will also change, but a leadership change alone does
not imply an ownership transfer.

More important to SYNC-1 will shoring up the idea that a case is mostly a
log of events that have occurred either locally or remotely, and that there
is an authoritative sequence of what has happened that is maintained by the
CaseActor and replicated to other participants. This is conceptually aligned
with our intent in Vultron that all participants maintain a shared
understanding of the case history and state, but it does conflict with
earlier documentation like `docs/howto/case_object.md` that describes the
log as a nice-to-have rather than a core part of the case model. This will
also force us to reconsider a case log as the source of truth for the case
state, with other case attributes like status being a static reflection of
the most-recently-received updates to the case log rather than being
entirely independent data blobs that could go out of sync with the log if
not updated.

## `vultron/core/use_cases` organization

`vultron/core/use_cases` could be reorganized into `messages received` and
`triggered events` collections. `triggers` already captures the latter. But
the former is just spread out in `use_cases`. It might help to have a
clearer separation between use cases that are intended to be responses to
incoming messages (most of which are updating case state in some way, and
therefore primarily relevant to a CaseActor managing the case) vs. use cases
that are intended for a participant actor to trigger against their local
(synchronized per the SYNC-1/2/3/4 roadmap item) case state in order to
generate outgoing messages (I.e., participants do triggers, case actor
catches the messages emitted as a result and updates the case state
accordingly, and sync ensures the case state is consistent across all
participants). So there are two ideas here: one is to make it clearer which
use cases are which through file system organization (keep tests in sync
with the structure), and the other is to clarify that
trigger->received->sync information flow in the documentation, notes, and
specs where appropriate.

## Update `notes/user-stories-trace.md` to reflect current state of `specs/`

Update `notes/user-stories-trace.md` (the traceability matrix) to map every user
story in `docs/topics/user_storie`s to the exact implementing requirements in
`specs/`. Because `specs/` has changed significantly, perform a thorough review of
`specs/`, add a mapping for each user story, and mark any stories that lack
requirement coverage. Stories with insufficient coverage should also be
noted in a new section in `plan/IMPLEMENTATION_NOTES.md` to be addressed later.
This will restore clear traceability between stories and requirements and
reveal gaps that need follow-up.
