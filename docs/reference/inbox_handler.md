# Inbox Handler Design

Vultron is designed with the ActivityPub protocol in mind. Most activity
in Vultron involves actors exchanging activity messages containing objects.

!!! example "Submitting a Vulnerability Report"

    For example, an actor might _create_ a `VulnerabilityReport` object and then
    _offer_ it to another actor, who can then _accept_, _tentatively reject_, or 
    _reject_ the offer.

Actors in ActivityPub can be of various types, such as `Person`, `Organization`,
`Group`, `Application`, `Service`, etc. Each actor has an _inbox_ and an _outbox_.
The inbox is where the actor receives activities, and the outbox is where the actor
sends activities.

!!! example "Actor Inboxes and Outboxes"

    For example, if Alice is a `Person` actor, she has an inbox at `https://example.com/users/alice/inbox`
    and an outbox at `https://example.com/users/alice/outbox`. If Bob is another `Person` actor, he has
    his own inbox and outbox.

    When Alice wants to send an activity to Bob, she creates the activity
    with the `to` field set to Bob's actor ID (e.g., `https://example.com/users/bob`)
    and places it in her outbox. The ActivityPub server then delivers the activity to Bob's inbox.
    Bob can then process the activity and respond by sending an activity to his outbox,
    with the `to` field set to Alice's actor ID. He can also set the `inReplyTo` field
    to reference the original activity from Alice to indicate that it is a response.
    The ActivityPub server handles the delivery of the activity to Alice's inbox, 
    and the cycle continues.

!!! note "Scope of Vultron's ActivityPub Implementation"

    However, in our Vultron prototype, we are not implementing a full
    ActivityPub server. Instead, we're initially focusing on the core functionality
    of actors sending activities directly to each other's inboxes. This simplifies
    the implementation while still allowing us to demonstrate the core concepts of
    ActivityPub interactions.

## Inbox Handler Architecture

Our initial architecture is as follows: An actor has an inbox implemented as a
FastAPI endpoint that accepts POST requests containing activity messages.
When a message is received, the inbox handler processes the activity and routes it
to an appropriate handler based on the activity's semantics.

!!! example "Activity Handling"

    For example, if the activity is an `Offer` of a `VulnerabilityReport`, it would be
    routed to a `submit_report` handler function, which contains the logic for processing
    a vulnerability report submission.


### Out of scope

We are deferring authentication, authorization, and server-to-server federation for
future implementation. 

This design also does not describe what happens inside each handler function; that is
left to the specific handler implementations to come later.
The focus of this design is on the inbox handler and dispatching logic that routes
activities to the appropriate handler functions.

### Inbox Handler Process

The inbox handler process consists of the following steps:

1. **Receive Activity**: The inbox endpoint receives a POST request containing an activity message in JSON format.
2. **Validate Activity**: The inbox endpoint validates the activity message structure to ensure it conforms to the ActivityPub specification.
3. **Log Activity**: The inbox endpoint logs the received activity message for debugging and auditing purposes.
4. **Queue Activity**: (only if **Validate Activity** succeeds) The inbox endpoint places the activity message into an asynchronous processing call to the inbox handler function, allowing the endpoint to respond immediately while the activity is processed in the background.
5. **Acknowledge Receipt**: The inbox endpoint responds to the POST request with a 200 OK status to acknowledge receipt of the activity message. If the validation failed, it can respond with an appropriate error status (e.g., 400 Bad Request) and log the error.
6. **Extract Routing Information**: The inbox handler extracts key fields from the activity message (e.g., `type`, `object`, `to`, `inReplyTo`) to determine routing.
   It creates a `DispatchActivity` header object containing the routing information and attaches the original activity message as the payload.
7. **Dispatch Activity**: The inbox handler invokes a dispatch function that routes the `DispatchActivity` object to the appropriate handler function based on the activity's semantic type.



## Activity Patterns and Semantics

Routing semantics are identified by `ActivityPattern` objects, which define patterns
for matching activity messages to specific enumerated semantic meanings. This
decouples the raw activity message structure from the higher-level semantics
of the Vultron protocol, allowing us to translate raw messages into meaningful
semantics that drive application logic.

!!! example "Defining Activity Patterns"

    We might define an activity pattern for submitting a vulnerability report
    as an `Offer` activity with an object of type `VulnerabilityReport`. 
    Responses to that offer follow their own patterns:
    
    ```python
    ReportSubmission = ActivityPattern(
        activity_=TAtype.OFFER,
        object_=VOtype.VULNERABILITY_REPORT,
    )
    AckReport = ActivityPattern(activity_=TAtype.READ, object_=ReportSubmission)
    ValidateReport = ActivityPattern(
        activity_=TAtype.ACCEPT, object_=ReportSubmission
    )
    InvalidateReport = ActivityPattern(
        activity_=TAtype.TENTATIVE_REJECT, object_=ReportSubmission
    )
    CloseReport = ActivityPattern(
        activity_=TAtype.REJECT, object_=ReportSubmission
    )
    ```

    The various `*type`s are string enumerations defined elsewhere.

!!! example "Mapping Activity Patterns to Semantics"

    We define the mapping from raw activity message patterns to higher-level semantics:
    
    ```python
    SEMANTICS_ACTIVITY_PATTERNS: dict[MessageSemantics, ActivityPattern] = {
        MessageSemantics.SUBMIT_REPORT: ap.ReportSubmission,
        MessageSemantics.ACK_REPORT: ap.AckReport,
        MessageSemantics.VALIDATE_REPORT: ap.ValidateReport,
        MessageSemantics.INVALIDATE_REPORT: ap.InvalidateReport,
        MessageSemantics.CLOSE_REPORT: ap.CloseReport,
        # ...etc.
    }
    ```

Activity semantics are determined by the `type` field of the
activity message, along with fields such as `object`, `to`,
and `inReplyTo`. The dispatch function uses this information to determine
which handler function should process the activity.

!!! example "DispatchActivity Object"

    A `DispatchActivity` object encapsulates the routing information needed by the
    dispatch function. At the time of writing, the `DispatchActivity` object is defined as:

    ```python
    @dataclass
    class DispatchActivity:
        semantic_type: MessageSemantics
        activity_id: str
        payload: as_Activity
    ```

## Dispatch Function

The dispatch function uses the `semantic_type` field of the `DispatchActivity`
to look up the appropriate handler function from a mapping of `MessageSemantics`
to handler functions. The handler function is then invoked with the `DispatchActivity`
object as an argument.

!!! example 

  The following is an example of the `ActivityDispatcher` Protocol that defines 
  the interface for dispatching activities:

  ```python
  class ActivityDispatcher(Protocol):
      """
      Protocol for dispatching activities to their corresponding handlers based on message semantics.
      """
  
      def dispatch(self, dispatchable: DispatchActivity) -> None:
          """Dispatches an activity to the appropriate handler based on its semantic type."""
          ...
  ```

!!! note "On the Modularity of Dispatchers"

    The dispatch function is designed as a Python `Protocol` to allow for different
    dispatcher implementations. This provides flexibility in connecting the inbox 
    handler to specific handler functions for each semantic type. A simple 
    implementation might use a dictionary mapping from semantic types to handler 
    functions, while a more complex implementation could involve message queues 
    or other routing mechanisms.

    This modularity allows us to easily extend dispatching logic by defining new 
    `ActivityPattern`s with corresponding `MessageSemantics`, then adding new 
    handler functions to the dispatch mapping. By decoupling routing logic from 
    handling logic, we maintain clean separation of concerns and facilitate 
    future protocol extensions.


## Direct Dispatch Implementation

Our first dispatch function implementation uses a simple direct dispatch approach
with a dictionary mapping from `MessageSemantics` to handler functions.
The dispatch function looks up the `semantic_type` from the `DispatchActivity`
object in the mapping and invokes the corresponding handler function with the
`DispatchActivity` as an argument.

This direct dispatch implementation is straightforward and allows us to quickly
begin handling activities based on their semantics.

!!! question "Into the Unknown?"

  What happens if an activity is received that does not match any known `ActivityPattern`?
  In this case, the semantic match function can return a special 
  `MessageSemantics.UNKNOWN` value, which the dispatch function can handle by 
  logging an error or ignoring the activity. This allows us to gracefully handle
  unexpected or malformed activities without crashing the system. In fact, if we
  implement this early, we will be able to detect and log any activities that 
  don't match our defined patterns, which will be useful to identify any issues
  with our pattern definitions, omitted patterns, or unexpected activity messages
  during testing and development.


## Handler Functions

Handler functions contain the logic for processing specific types of activities
based on their semantics. Each handler function is responsible for implementing the
application logic for a particular semantic type, such as processing a vulnerability
report submission, acknowledging receipt of a report, validating a report, etc.

!!! example "Defining Handler Functions"

    Following is an example of how handler functions can be defined for each 
    semantic type. Each handler function takes a `DispatchActivity` object as
    an argument and contains the logic for processing that specific type of
    activity.
  
    ```python
    class BehaviorHandler(Protocol):
        """
        Protocol for behavior handler functions.
        """
    
        def __call__(self, dispatchable: DispatchActivity) -> None: ...
    ```
    So a potential handler function for the `SUBMIT_REPORT` semantic type might look like this:
    
    ```python
    def handle_submit_report(dispatchable: DispatchActivity) -> None:
        # logic for processing a vulnerability report submission goes here
        ...
    ```

## Development Goals

### Phase 1: Core Infrastructure

- [ ] Implement actor-specific inbox handler as a FastAPI POST endpoint (`/inbox`) that receives activity messages in JSON format
- [ ] Create activity validation logic to ensure conformance with ActivityPub specification
- [ ] Define core `ActivityPattern` class and implement pattern matching logic for routing semantics
- [ ] Create `MessageSemantics` enumeration for Vultron protocol semantics
- [ ] Build `SEMANTICS_ACTIVITY_PATTERNS` mapping dictionary from `MessageSemantics` to `ActivityPattern`s

### Phase 2: Dispatching

- [ ] Implement `DispatchActivity` dataclass to encapsulate routing information (`semantic_type`, `activity_id`, `payload`)
- [ ] Create routing logic to extract semantic information from incoming activities and construct `DispatchActivity` objects
- [ ] Define `Dispatcher` Protocol interface for pluggable dispatch implementations
- [ ] Implement direct dispatch function using dictionary mapping from `MessageSemantics` to handler functions

### Phase 3: Handler Stubs

- [ ] Create handler function stubs for vulnerability report submission semantics:
  - [ ] `SUBMIT_REPORT` handler (processes `Offer` of `VulnerabilityReport`)
  - [ ] `ACK_REPORT` handler (processes `Read` acknowledgment)
  - [ ] `VALIDATE_REPORT` handler (processes `Accept` response)
  - [ ] `INVALIDATE_REPORT` handler (processes `TentativeReject` response)
  - [ ] `CLOSE_REPORT` handler (processes `Reject` response)
- [ ] Add basic logging to each handler stub for debugging and demonstration purposes
- [ ] Create unit tests for inbox handler pipeline from POST request through dispatch to handler invocation
