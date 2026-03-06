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
