## D5-6a Finder actions not appearing in log

In the following log snippet from the two-actor demo, the demo-runner-1
reports that the finder is submitting a vulnerability report, but we don't
actually observe the `finder-1` container logging anything. We should see a
log entry for the finder creating a report, and then another for offering
the report to the vendor. We don't need these to be super detailed because
the vendor receiving the offer has the details of both the offer and the
report. But we do need to at least see them in the combined log.

```text
demo-runner-1  | 2026-04-06 13:42:55,629 INFO     vultron.demo.two_actor_demo: Finder peer registered on Vendor container: http://finder:7999/api/v2/actors/b02aee70-1a8c-4230-a55e-cf2601c887c7
demo-runner-1  | 2026-04-06 13:42:55,629 INFO     vultron.demo.utils: 🟢 Seeding both containers with actor records
demo-runner-1  | 2026-04-06 13:42:55,634 INFO     vultron.demo.utils: 🚥 Finder submits vulnerability report to Vendor's inbox
vendor-1       | INFO:     Parsing activity from request body. {'@context': 'https://www.w3.org/ns/activitystreams', 'type': 'Offer', 'id': 'urn:uuid:2862bf81-beb3-4b05-86a3-11274be6a87a', 'name': 'http://finder:7999/api/v2/actors/b02aee70-1a8c-4230-a55e-cf2601c887c7 Offer Remote Code Execution in Network Stack', 'published': '2026-04-06T13:42:55+00:00', 'updated': '2026-04-06T13:42:55+00:00', 'to': ['http://vendor:7999/api/v2/actors/c383ac21-12eb-4518-8f0d-60a7450afc03'], 'actor': 'http://finder:7999/api/v2/actors/b02aee70-1a8c-4230-a55e-cf2601c887c7', 'object': {'@context': 'https://www.w3.org/ns/activitystreams', 'type': 'VulnerabilityReport', 'id': 'urn:uuid:18f933a5-b163-4aa5-8645-5833b65bed4e', 'name': 'Remote Code Execution in Network Stack', 'published': '2026-04-06T13:42:55+00:00', 'updated': '2026-04-06T13:42:55+00:00', 'content': 'A critical remote code execution vulnerability was discovered in the network stack component. An attacker can exploit this issue to execute arbitrary code with elevated privileges.', 'attributedTo': 'http://finder:7999/api/v2/actors/b02aee70-1a8c-4230-a55e-cf2601c887c7'}}
vendor-1       | INFO:     Parsing activity from body (type='Offer')
vendor-1       | INFO:     Processing inbox for actor http://vendor:7999/api/v2/actors/c383ac21-12eb-4518-8f0d-60a7450afc03
vendor-1       | INFO:     Processing item 'http://finder:7999/api/v2/actors/b02aee70-1a8c-4230-a55e-cf2601c887c7 Offer Remote Code Execution in Network Stack' for actor 'http://vendor:7999/api/v2/actors/c383ac21-12eb-4518-8f0d-60a7450afc03'
vendor-1       | INFO:     Dispatching activity of type 'VulnerabilityReport' with semantics 'submit_report'
vendor-1       | INFO:     Stored VulnerabilityReport with ID: urn:uuid:18f933a5-b163-4aa5-8645-5833b65bed4e
vendor-1       | INFO:     Stored ParticipantStatus (report-phase RM.RECEIVED) 'urn:uuid:e8e3f075-07e3-58ed-89cf-ef64c10290a9'
vendor-1       | INFO:     RM START → RECEIVED for report 'urn:uuid:18f933a5-b163-4aa5-8645-5833b65bed4e' (actor 'http://finder:7999/api/v2/actors/b02aee70-1a8c-4230-a55e-cf2601c887c7')
vendor-1       | INFO:     Processing outbox for actor http://vendor:7999/api/v2/actors/c383ac21-12eb-4518-8f0d-60a7450afc03
demo-runner-1  | 2026-04-06 13:42:56,646 INFO     vultron.demo.utils: 🟢 Finder submits vulnerability report to Vendor's inbox
```

## D5-6b Parsing activity from request body formatting

The log entry below would be better if it were formatted as multiline indented
json rather than a single long line of text.

```text
vendor-1       | INFO:     Parsing activity from request body. {'@context': 'https://www.w3.org/ns/activitystreams', 'type': 'Offer', 'id': 'urn:uuid:2862bf81-beb3-4b05-86a3-11274be6a87a', 'name': 'http://finder:7999/api/v2/actors/b02aee70-1a8c-4230-a55e-cf2601c887c7 Offer Remote Code Execution in Network Stack', 'published': '2026-04-06T13:42:55+00:00', 'updated': '2026-04-06T13:42:55+00:00', 'to': ['http://vendor:7999/api/v2/actors/c383ac21-12eb-4518-8f0d-60a7450afc03'], 'actor': 'http://finder:7999/api/v2/actors/b02aee70-1a8c-4230-a55e-cf2601c887c7', 'object': {'@context': 'https://www.w3.org/ns/activitystreams', 'type': 'VulnerabilityReport', 'id': 'urn:uuid:18f933a5-b163-4aa5-8645-5833b65bed4e', 'name': 'Remote Code Execution in Network Stack', 'published': '2026-04-06T13:42:55+00:00', 'updated': '2026-04-06T13:42:55+00:00', 'content': 'A critical remote code execution vulnerability was discovered in the network stack component. An attacker can exploit this issue to execute arbitrary code with elevated privileges.', 'attributedTo': 'http://finder:7999/api/v2/actors/b02aee70-1a8c-4230-a55e-cf2601c887c7'}}
```

## D5-6c Unclear log meaning

The log entry below is unclear. Is this indicating that the vendor is
marking the finder as being at RM.RECEIVED? Or is it the vendor logging that
the vendor has gone to RM.RECEIVED?

```text
vendor-1       | INFO:     RM START → RECEIVED for report 'urn:uuid:18f933a5-b163-4aa5-8645-5833b65bed4e' (actor 'http://finder:7999/api/v2/actors/b02aee70-1a8c-4230-a55e-cf2601c887c7')
```

The details matter here because in fact any finder who is reporting must by
definition be at RM.ACCEPTED in order for them to even be submitting a
report in the first place. (But we're not usually tracking them until the
report is received so this may be the first time we have a log entry for the
finder at all. So if this is the vendor logging the finder state, the finder
state should be RM.ACCEPTED, not RM.RECEIVED. If this is the vendor logging the
vendor state, then it should be RM.RECEIVED but the log entry should be clearer about that.)
And both finder=RM.ACCEPTED and vendor=RM.RECEIVED are correct for the state
immediately after a report is received by the vendor, and should be tracked.
This might highlight the need for us to spawn a case participant status
already in progress for the finder at the receipt of the report so that we
can maintain the finder state from the very beginning of the process.

## D5-6d Logging vs storage formats

When `demo-runner-1` logs that the offer is stored in the vendor's datalayer,
it appears that the object of the offer is being duplicated (as we just
confirmed before these logs that the report is also in the vendor's
datalayer). We shouldn't be storing redundant copies of the same object in
the datalayer, but this could be a logging issue where the log is showing a
rehydrated version of the offer that includes the full report object, even
though the datalayer is only storing a reference to the report object. If that's
the case, the log should be updated to clarify that this is a rehydrated
version of the offer for logging purposes, and that the datalayer is only  
storing a reference to the report object rather than a full copy of it.

However, if it is the case that the datalayer is actually storing a full
copy of the report object as part of the offer object, then this is a
problem that needs to be addressed, because we don't want to be storing
redundant copies of the same object in the datalayer. In that case, the
implementation should be updated to ensure that the offer object only
contains a reference to the report object rather than a full copy of it,
and the log should be updated to reflect this change as well.

Datalayer tests should confirm that any transitive activity is stored with
references rather than full copies of nested objects, but that fully rehydrated
versions of the activity can be generated on the fly for logging and other
purposes without affecting the underlying storage format.

This change generalizes to all demo-runner checks that are verifying transitive
activities in the datalayer.

```text
demo-runner-1  | 2026-04-06 13:42:56,652 INFO     vultron.demo.utils: 📋 Offer stored in Vendor's DataLayer
demo-runner-1  | 2026-04-06 13:42:56,657 INFO     vultron.demo.utils: Verified object stored: {
demo-runner-1  |   "@context": "https://www.w3.org/ns/activitystreams",
demo-runner-1  |   "type": "Offer",
demo-runner-1  |   "id": "urn:uuid:2862bf81-beb3-4b05-86a3-11274be6a87a",
demo-runner-1  |   "name": "http://finder:7999/api/v2/actors/b02aee70-1a8c-4230-a55e-cf2601c887c7 Offer Remote Code Execution in Network Stack",
demo-runner-1  |   "published": "2026-04-06T13:42:55+00:00",
demo-runner-1  |   "updated": "2026-04-06T13:42:55+00:00",
demo-runner-1  |   "to": [
demo-runner-1  |     "http://vendor:7999/api/v2/actors/c383ac21-12eb-4518-8f0d-60a7450afc03"
demo-runner-1  |   ],
demo-runner-1  |   "actor": "http://finder:7999/api/v2/actors/b02aee70-1a8c-4230-a55e-cf2601c887c7",
demo-runner-1  |   "object": {
demo-runner-1  |     "@context": "https://www.w3.org/ns/activitystreams",
demo-runner-1  |     "type": "VulnerabilityReport",
demo-runner-1  |     "id": "urn:uuid:18f933a5-b163-4aa5-8645-5833b65bed4e",
demo-runner-1  |     "name": "Remote Code Execution in Network Stack",
demo-runner-1  |     "published": "2026-04-06T13:42:55+00:00",
demo-runner-1  |     "updated": "2026-04-06T13:42:55+00:00",
demo-runner-1  |     "content": "A critical remote code execution vulnerability was discovered in the network stack component. An attacker can exploit this issue to execute arbitrary code with elevated privileges.",
demo-runner-1  |     "attributedTo": "http://finder:7999/api/v2/actors/b02aee70-1a8c-4230-a55e-cf2601c887c7"
demo-runner-1  |   }
demo-runner-1  | }
demo-runner-1  | 2026-04-06 13:42:56,657 INFO     vultron.demo.utils: ✅ Offer stored in Vendor's DataLayer
```

## D5-6e Vendor actions hidden

In the following log snippet, we see that teh vendor validates the report.
But we don't see any log entries indicating that the vendor is moving from
RM.RECEIVED to RM.VALID, or that the vendor is creating a case, or any
behavior tree sequences that fire along the way. We should see log entries
for all of these things. One-line descriptive logs are fine, we don't need
large data dumps, but we do need to see the key steps in the process reflected
in the logs so we know what's happening and can confirm that expected
behaviors are occurring.

When the case is created, we should see the vendor logging the creation of
the case, the creation of a participant record associating itself with the
case in the roles of vendor and case owner, the creation of a participant  
record associating the finder with the case in the role of reporter, the
creation of participant status records for both the vendor and the finder at
the initial relevant states (log states so we can inspect them), the
attachment of those participant status records to the participants, the
attachment of the participants to the case, and the creation and
attachment of at least one case status object to the case reflecting the
stakeholder-agnostic state of the case at the point of creation.

```text
demo-runner-1  | 2026-04-06 13:42:56,658 INFO     vultron.demo.utils: 🚥 Vendor validates the vulnerability report
demo-runner-1  | 2026-04-06 13:42:56,658 INFO     vultron.demo.utils: Posting trigger 'validate-report' for actor 'c383ac21-12eb-4518-8f0d-60a7450afc03': {'offer_id': 'urn:uuid:2862bf81-beb3-4b05-86a3-11274be6a87a'}
vendor-1       | INFO:     BT setup complete for actor http://vendor:7999/api/v2/actors/c383ac21-12eb-4518-8f0d-60a7450afc03
vendor-1       | INFO:     Stored ParticipantStatus (report-phase RM.VALID) 'urn:uuid:7ce93c87-10e7-5a56-b219-d0286d62a110'
vendor-1       | INFO:     BT execution completed: Status.SUCCESS after 1 ticks - 
demo-runner-1  | 2026-04-06 13:42:56,720 INFO     vultron.demo.utils: 🟢 Vendor validates the vulnerability report
demo-runner-1  | 2026-04-06 13:42:56,720 INFO     vultron.demo.two_actor_demo: Validate-report trigger result for actor c383ac21-12eb-4518-8f0d-60a7450afc03
demo-runner-1  | 2026-04-06 13:42:56,720 INFO     vultron.demo.utils: 📋 VulnerabilityCase exists in Vendor's DataLayer
demo-runner-1  | 2026-04-06 13:42:56,776 INFO     vultron.demo.two_actor_demo: Case created: urn:uuid:ba578c74-7043-41ab-9124-0c7106aa0bff
demo-runner-1  | 2026-04-06 13:42:56,777 INFO     vultron.demo.utils: ✅ VulnerabilityCase exists in Vendor's DataLayer
```

## D5-6f Participant record creation hidden

We need logs to indicate that a participant record is created, attached to a
case, and has a status record created and attached to it. We should see this
for any participant record that is created including at case creation and
any time a new participant is added to an existing case. It is important
that the logs include the participant role and status so that we can confirm
these values are correct for the expected participants.

## D5-6g General principle for logs

We should be able to use INFO logs to tell what each part of the system is
doing at a high level. We don't need to see every bit of data and every
function call, but we need to be able to follow the process flow through the
logs to understand what is happening and confirm that expected behaviors are
occurring. Many of the logs in the current demo are too sparse to give us
confidence that the right steps are happening in the right order.

## D5-6h Ordering of events in the Vendor's case creation workflow

The vendor workflow appears to be 1) validate report (includes create case),
then 2) engage case and 3) create and add finder participant record, then 4)
add finder participant to case, and 5) notify finder. However, what we actually
expect to happen is this:

1. validate report
2. validation triggers create case behavior
3. create case behavior includes
   1. create case record
   2. create case status record with initial case state and attach to case record
   3. Initialize embargo on case
      1. start with embargo based on vendor default policy
   4. create vendor participant record with role of vendor and case owner
   5. attach prior vendor participant status logs to vendor participant record
   6. attach vendor participant record to case
   7. create finder participant record with role of reporter and finder
   8. attach prior finder participant status logs to finder participant record
   9. attach finder participant record to case
   10. update case status (remember, status logs are always updated by
       appending new entries, never modifying existing entries) to reflect
       any changes since 3.2 if necessary
   11. emit messages to finder
       1. vendor created case
       2. vendor added finder as participant to case with reporter role and
          status x
       3. vendor announces initial case embargo

In essence, the vendor validating the case should set off a single behavior
tree workflow that automates all the above consistently. There are no
separable choices to be made here, each item above is simply a consequence
of creating a case in response to a valid report.

Note that 3.3 leaves room for future expansion in that the reporter might
also propose an embargo different from the vendor default. But the vendor
should have a default that applies in the absence of any reporter-suggested
embargo.

3.11.3 captures an implied assumption that a reporter submission to a vendor
implies tacit acceptance of the default embargo by the reporter because if
the reporter doesn't agree they should propose a different embargo before or
concurrently with the report submission.

Note that the `default embargo` concept is elaborated in the docs:
`/docs/topics/process_models/em/defaults.md` and interactions between the RM
and EM models are described in
`docs/topics/process_models/model_interactions/rm_em.md` and captured in
specs section `VP-13-*`.
