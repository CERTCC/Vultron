# Project Ideas

## ~~Documentation bug: misplaced references to demo in `IDEAS.md`~~

> ✅ Captured: `plan/PRIORITIES.md` Priority 300 updated to reference
> `notes/demo-future-ideas.md`; `notes/domain-model-separation.md` reference
> fixed. No remaining references to `plan/IDEAS.md` for demo content.

~~In a few places there are references to a Priority 300 item about future
demo ideas that point to `plan/IDEAS.md` but that content has migrated to
`notes/demo-future-ideas.md`. Those references should be updated to point
to the correct location.~~

## ~~Backfill pre-case events into case log on creation~~

> ✅ Captured: `notes/case-state-model.md` "Pre-Case Event Backfill on Case
> Creation" section; design options (event-logger decorator) and open
> question about implementation mechanism documented there.

~~When a new case is created, there will have already been a few events that
happened that should be added to the case log, such as the Offer of the
initial report, any pre-case messages about the report or offer between the
recipient and the initial reporter, acknowledgment (if any) of the Offer,
acceptance of the Offer, the creation of the case, the creation and addition
of the initial participants on the case, etc. These events should be
backfilled into the case at time of case creation. Events like adding the
participants can just be captured in the add participant step, but some of
those events need to be inserted at case startup.

This might also imply the need for a sort of event logger decorator that can
be used to automatically capture timestamps on activities when events happen
on cases. That might be the easiest way to do this without having to add a
lot of extra code in the case management steps.~~

## ~~Non-empty string checks can be DRYed up~~

> ✅ Captured: `specs/code-style.md` CS-08-001 and CS-08-002 define the
> `NonEmptyString` / `OptionalNonEmptyString` type pattern.

~~There are a lot of places where we check for non-empty strings in the code,
such as in `case_event.py`. There is no reason for this to be repeated
everywhere. Come up with a way to consolidate these checks into a single
location that enforces the check across the codebase. Pydantic validators
should be able to do this in a more consolidated way without having to have
separate methods for every single non-empty string field. Perhaps it could
be by defining a NonEmptyString type that enforces the check then replacing
all the relevant fields with that type?~~

## ~~Case state action rules will need to parse case and participant statuses~~

> ✅ Captured: `notes/case-state-model.md` "Multi-Vendor Case State Action
> Rules" section; participant-specific vs case-level rules distinction and
> threshold heuristic open question documented there.

~~When we get around to the case state action rules implementation (see
`specs/agentic-readiness.md` and `specs/case-management.md`), we will need
to be able to parse the case status objects and participant status objects
in order to evaluate the rules. Some of the rules are based on
participant-agnostic status items, while others are based on
participant-specific items. Furthermore, for the CaseActor or the Case Owner,
they will need to account for the status of all the relevant participants.
For example in a case with multiple vendors who might be in various VFD
states or even different RM states, the rules for an individual participant
will only need to account for that participant's status, but the Case Owner
(and therefore CaseActor's perspective) will need to account for the
statuses of all the Vendor participants. This subtlety is not reflected in
the original description of the CVD action rules, as they were more geared
towards describing what an individual participant should do rather than how
to coordinate across them. Especially with respect to the VFD states, it's
going to be important that a CaseActor doesn't see that one vendor out of
dozens has a fix ready (while the others don't) and then jump the gun on
ending the embargo or pushing for public disclosure. It will need to be more
balanced at that level, whether that is expressed as a judgment call to a
cognitive agent to decide, or perhaps there might be some threshold
heuristics like "at least X% of vendors with VFD state of Fix Ready" or at
least "all engaged vendors with VFD state of Fix Ready" or something like
that. This is an important nuance that will need to be accounted for in the rules
implementation.~~

## ~~New ideas in notes need to be propagated~~

> ✅ Captured: `specs/architecture.md` created from
> `notes/architecture-ports-and-adapters.md` (ARCH-01 to ARCH-08);
> `notes/architecture-review.md` and `notes/federation_ideas.md` listed in
> `notes/README.md`; forward reference added from
> `specs/prototype-shortcuts.md` to `notes/federation_ideas.md`.

~~There have been additions captured in
`notes/architecture-ports-and-adapters.md`, `notes/federation_ideas.md`, and
`notes/architecture-review.md` that have not yet been propagated into
`specs/`, `notes/`, or `plan/IMPLEMENTATION_PLAN.md`. These ideas should be
reviewed and integrated into the appropriate files as needed, or
cross-referenced as appropriate. These notes contain important architecture
and design insights that need to be reflected in plans and specs going
forward.~~