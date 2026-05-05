# Project Ideas

ID format: IDEA-YYMMDDNN

## IDEA-26050404 Clearly delineate specs vs ADRs

We have both specs in `specs/` and any decision records in `docs/adr`, and
we have mechanisms in place for ingesting ideas and learnings into `specs/`
but we're less clear on when a spec goes beyond just being a spec and should
be an ADR instead (or both?). We should clarify the distinction and
establish guidelines for when creating an ADR is warranted.

## IDEA-26050501 Clarify order of operations on case creation

When a case is created, there are a number of consequences/side
effects/cascade of events that need to happen in a specific order. In
general, the principle is that the case creator is the first participant
added to the case, and has the case owner role from the start. If there is
either an embargo already proposed or a default embargo available, then this
should also be added to the case immediately upon case creation, with the
case creator accepting it as the case owner, (which means that the embargo
is active on the case from the start). Adding the reporter to the case is
also automatic as it is assumed that by submitting a report they are already
expressing their intent to participate in the case, and that they expect to
accept the embargo (they already have the information so there's no reason
to ask them to accept the embargo before sharing information with them).
This happens AFTER the case creator does their initialization routine thing.

Everything else (inviting additional parties, embargo changes, etc.) happens
after there is already a case owner and reporter in place.
