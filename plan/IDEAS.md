# Project Ideas

## Backfill pre-case events into case log on creation

When a new case is created, there will have already been a few events that 
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
lot of extra code in the case management steps.

## Non-empty string checks can be DRYed up

There are a lot of places where we check for non-empty strings in the code, 
such as in `case_event.py`. There is no reason for this to be repeated 
everywhere. Come up with a way to consolidate these checks into a single 
location that enforces the check across the codebase. Pydantic validators 
should be able to do this in a more consolidated way without having to have 
separate methods for every single non-empty string field. Perhaps it could 
be by defining a NonEmptyString type that enforces the check then replacing 
all the relevant fields with that type?

