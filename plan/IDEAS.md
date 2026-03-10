# Project Ideas

## vultron/api/v2 needs to turn into a driving adapter layer

The vultron/api/v2 module is currently a mix of domain logic and API routing.
It needs to be refactored to separate concerns and turn it into a proper 
driving adapter layer that translates external inputs (HTTP requests) into  
calls to the core domain logic. This will involve:

- `vultron/api/v2/backend/handlers` are ports / use cases that belong 
  somewhere in `vultron/core`
- most of the rest of `vultron/api/v2` are basically driving adapters that 
  will interface with the core use cases.
- Note the long-running distinction between "handlers" are dealing with 
  messages received (someone else did something) vs "triggered behaviors" are 
  locally-initiated actions is still relevant to use cases too, we need to 
  distinguish between "received a message that foo accepted a report" vs "I 
  accepted a report and now there are side effects that need to happen". 
  (receipt can also have side effects, of course, as we've already worked 
  out in the code.)

## `vultron/api/v1` is really an adapter too.

The difference between `v1` and `v2` is that `v2` is driven by AS2 messages 
arriving in inboxes, whereas `v1` is basically a direct datalayer access 
backend for prototype purposes. `v2` is semantic, `v1` is more of a "get 
objects" API. However, `v1` is still an adapter layer, just one that basically
talks almost directly to the backend data layer port. It still needs to be 
refactored to fit the port and adapter design. There might be a very thin 
core use case layer that it interfaces with, or if that's overkill, we could 
just let it talk to the data layer port directly. `v1` is essentially an 
administrative visibility and management API for development and testing 
purposes, but we should still refactor it to fit the architecture we're 
moving towards.

