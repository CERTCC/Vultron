# Inbox Handler Design

Vultron is designed with the ActivityPub protocol in mind. Most of the activity
done in Vultron is between actors exchanging activity messages containing objects.

!!! example "Submitting a Vulnerability Report"

    For example, an actor might _create_ a `VulnerabilityReport` object, and then
    _offer_ it to another actor, who can then *accept*, *tenatively reject*, or 
    *reject* the offer.

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
    with the `to` field set to Alice's actor ID. He can also set the `in-reply-to` field
    to reference the original activity from Alice to indicate that it is a response.
    Again, the ActivityPub server handles the delivery of the activity to Alice's inbox, 
    and the cycle continues.

!!! note "Scope of Vultron's ActivityPub Implementation"

    However, in our Vultron prototype, we are not attempting to implement a full
    ActivityPub server. Instead, we're initially focusing on the core functionality
    of actors sending activities directly to each other's inboxes. This simplifies
    the implementation while still allowing us to demonstrate the core concepts of
    ActivityPub interactions.

## Inbox Handler

Our initial architecture is as follows: An actor has an inbox. That inbox is a
FastAPI endpoint that accepts POST requests containing activity messages. When a
message is received, the inbox handler processes the activity and passes it
to an appropriate handler based on the semantics of the received activity.

!!! example "Activity Handling"

    For example, if the activity is an `Offer` of a `VulnerabilityReport`, it would be
    passed to the `submit_report` function, which would contain the logic for how to
    handle the submission of a vulnerability report.

We are skipping authentication and authorization for now, as well as any kind of 
federation or server-to-server communication. 

Nevertheless, there are a few important steps to the inbox handler process.

1. **Receive Activity**: The inbox handler receives a POST request containing an activity message in JSON format.
2. **Validate Activity**: The inbox handler validates the structure of the activity message to ensure it conforms to the ActivityPub specification.
3. **Extract Semantic Routing Info**: The inbox handler extracts key fields from the activity message, such as `type`, `object`, `to`, and `in-reply-to`, to determine how to route the activity.
   It does this by creating a `DispatchActivity` header object that contains the relevant information for routing, and appends the original activity message as the payload of the `DispatchActivity` object.
4. **Dispatch Activity**: The inbox handler then invokes a dispatch function that takes the `DispatchActivity` object and routes it to the appropriate handler function based on the `type` of the activity and other relevant fields.

### Introducing Activity Semantics

Routing semantics are identified by `ActivityPattern` objects, which define patterns
for matching activity messages to a specific enumerated semantic meaning. This
helps to decouple the raw activity message structure from the higher-level semantics
of the Vultron protocol, thereby allowing us to transition from raw messages
to more meaningful semantics that can be used to drive the logic of our application.

!!! example "Defining Activity Patterns"

    Extending the previous example, we might define an activity pattern for 
    submitting a vulnerability report as an `Offer` activity with an object of 
    type `VulnerabilityReport`. Responses to that offer would then follow patterns
    of their own.
    
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

    Where the various `*type`s are string enumerations defined elsewhere.


!!! example "Mapping Activity Patterns to Semantics"

    Next is an example of how we might define the mapping from raw activity message
    patterns to higher-level semantics:
    
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

As shown above, activity semantics are determined by the `type` field of the 
activity message, as well as other fields such as `object`, `to`, 
and `in-reply-to`. The dispatch function uses this information to determine 
which handler function should process the activity.

!!! example "Dispatch Activity"
    
    A `DispatchActivity` object is created by the inbox handler to encapsulate the
    relevant information for routing the activity. It contains just enough information
    for a dispatch function to quickly route the activity to the appropriate handler.
    At the time of writing, the `DispatchActivity` object is defined as follows:

    ```python
    @dataclass
    class DispatchActivity:
        semantic_type: MessageSemantics
        activity_id: str
        payload: as_Activity
    ```

## Dispatch Function

The dispatch function then uses the `semantic_type` field of the `DispatchActivity`
to find the appropriate handler function from a mapping of `MessageSemantics` 
to handler functions. The handler function is then invoked with the `DispatchActivity` 
object as an argument, allowing it to process the activity according to its semantics.

!!! note "On the Modularity of Dispatchers"

    The dispatch function is designed as a Python `Protocol`, to allow for different
    implementations of dispatchers. This provides flexibility in how we implement
    the connection between the inbox handler and the specific handler functions for each
    semantic type. A simple implementation might just use a dictionary mapping from
    semantic types to handler functions, while a more complex implementation could involve
    message queues or other message routing mechanisms.

    This modularity also allows us to easily extend the dispatching logic in the future,
    by defining new `ActivityPattern`s and corresponding `MessageSemantics`, and
    then adding new handler functions to the dispatch mapping. 
    By decoupling the routing logic from the specific handling logic, we can maintain a
    clean separation of concerns and facilitate future extensions to the protocol.

## Direct Dispatch Implementation

Our first implementation of the dispatch function will be a simple direct dispatch
where we have a dictionary mapping from `MessageSemantics` to handler functions.
The dispatch function will look up the `semantic_type` from the `DispatchActivity`
object in the mapping and invoke the corresponding handler function with the 
`DispatchActivity` as an argument.

This direct dispatch implementation is straightforward and allows us to quickly
get up and running with handling activities based on their semantics. 

### Initial development goals

- [ ] Implement an actor-specific inbox handler as a FastAPI endpoint that receives 
  activity messages.
- [ ] Define `ActivityPattern`s to identify routing semantics based on activity
  message structure.
- [ ] Create a mapping from `MessageSemantics` to `ActivityPattern`s to determine 
  the semantics of incoming activities.
- [ ] Implement a `DispatchActivity` object to encapsulate routing information for 
  dispatching activities.
- [ ] Develop a direct dispatch function that routes activities to handler functions 
  based on their semantics using a simple dictionary mapping.
- [ ] Stub out handler functions for key semantics such as `SUBMIT_REPORT`, 
  `ACK_REPORT`, `VALIDATE_REPORT`, etc., to demonstrate the routing of 
  activities to handlers.