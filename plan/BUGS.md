# Bugs to fix

Items in this file supersede IMPLEMENTATION_PLAN.md.

Use format `BUG-YYMMDDXX` for bug IDs, where `YYMMDD` is the date the bug
was identified and `XX` is a sequential number for that day. For example,  
the first bug identified on March 26, 2026 would be `BUG-2026032601`.
Include a brief description in the title, and provide detailed reproduction
steps, root cause analysis, and resolution steps in the body.

---

## BUG-26041501 Two-actor demo fails when Finder receives Announce with bad type from Vendor

The two-actor emo fails with an error when the Finder receives the Announce
activity from the Vendor about the new case log entry. The error is an  
AttributeError indicating that a 'VultronObject' has no attribute 'case_id'.
This may imply a mismatch between what is being emitted and what is being
extracted on the receiving end. I believe the Announce in this case should
be announcing a CaseLogEntry, but the line
`INFO:     Dispatching activity of type 'None' with semantics 'announce_case_log_entry'`
suggests that the activity are being set correctly but the type or object is
not, which may be causing the receiving end to fail when it tries to extract
data from the object. A missing type will also break semantic dispatching as
well. Investigate thoroughly as this bug may be masking others in the
vicinity as we have not seen this code run successfully yet.

Full log follows.

```text
demo-runner-1  | 2026-04-15 15:39:10,266 INFO     vultron.demo.two_actor_demo: Log entry committed for case 'urn:uuid:a344d2d8-3747-4128-b80c-b278f9ce5e9d': hash=6cde3f6c9cf03410, index=0
demo-runner-1  | 2026-04-15 15:39:10,266 INFO     vultron.demo.utils: 🟢 Committing case log entry on Vendor (CaseActor)
demo-runner-1  | 2026-04-15 15:39:10,266 INFO     vultron.demo.utils: 🚥 Waiting for Finder to receive replicated log entry
vendor-1       | INFO:     Processing outbox for actor 515663dc-3ab9-4aa9-a0bc-6a97e8b710c6
finder-1       | INFO:     Parsing activity from request body (type='Announce'):
finder-1       | {
finder-1       |   "id": "urn:uuid:6035c298-dec3-4881-ba21-f12ed8b74b9f",
finder-1       |   "type": "Announce",
finder-1       |   "name": "http://vendor:7999/api/v2/actors/515663dc-3ab9-4aa9-a0bc-6a97e8b710c6 Announce None",
finder-1       |   "published": "2026-04-15T15:39:10Z",
finder-1       |   "updated": "2026-04-15T15:39:10Z",
finder-1       |   "to": [
finder-1       |     "http://finder:7999/api/v2/actors/1e28e488-e7d1-475f-9b42-e1f20be1b6cf"
finder-1       |   ],
finder-1       |   "actor": "http://vendor:7999/api/v2/actors/515663dc-3ab9-4aa9-a0bc-6a97e8b710c6",
finder-1       |   "object": "urn:uuid:a344d2d8-3747-4128-b80c-b278f9ce5e9d/log/0"
finder-1       | }
finder-1       | INFO:     Parsing activity from body (type='Announce')
vendor-1       | INFO:     HTTP Request: POST http://finder:7999/api/v2/actors/1e28e488-e7d1-475f-9b42-e1f20be1b6cf/inbox/ "HTTP/1.1 202 Accepted"
finder-1       | INFO:     Processing inbox for actor http://finder:7999/api/v2/actors/1e28e488-e7d1-475f-9b42-e1f20be1b6cf
vendor-1       | INFO:     Delivered activity urn:uuid:6035c298-dec3-4881-ba21-f12ed8b74b9f to http://finder:7999/api/v2/actors/1e28e488-e7d1-475f-9b42-e1f20be1b6cf/inbox/ (HTTP 202)
vendor-1       | INFO:     Delivered Announce activity 'urn:uuid:6035c298-dec3-4881-ba21-f12ed8b74b9f' (object: urn:uuid:a344d2d8-3747-4128-b80c-b278f9ce5e9d/log/0) to 1 recipient(s) [http://finder:7999/api/v2/actors/1e28e488-e7d1-475f-9b42-e1f20be1b6cf] for actor '515663dc-3ab9-4aa9-a0bc-6a97e8b710c6'.
finder-1       | INFO:     Processing item 'http://vendor:7999/api/v2/actors/515663dc-3ab9-4aa9-a0bc-6a97e8b710c6 Announce None' for actor 'http://finder:7999/api/v2/actors/1e28e488-e7d1-475f-9b42-e1f20be1b6cf'
finder-1       | INFO:     Dispatching activity of type 'None' with semantics 'announce_case_log_entry'
finder-1       | ERROR:    Unexpected error dispatching activity_id=urn:uuid:6035c298-dec3-4881-ba21-f12ed8b74b9f actor_id=http://vendor:7999/api/v2/actors/515663dc-3ab9-4aa9-a0bc-6a97e8b710c6 semantics=announce_case_log_entry
finder-1       | Traceback (most recent call last):
finder-1       |   File "/app/vultron/core/dispatcher.py", line 68, in _handle
finder-1       |     use_case_class(dl, event).execute()
finder-1       |     ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~^^
finder-1       |   File "/app/vultron/core/use_cases/received/sync.py", line 152, in execute
finder-1       |     case_id: str = entry.case_id
finder-1       |                    ^^^^^^^^^^^^^
finder-1       |   File "/app/.venv/lib/python3.13/site-packages/pydantic/main.py", line 1026, in __getattr__
finder-1       |     raise AttributeError(f'{type(self).__name__!r} object has no attribute {item!r}')
finder-1       | AttributeError: 'VultronObject' object has no attribute 'case_id'
finder-1       | ERROR:    Error processing inbox item for actor http://finder:7999/api/v2/actors/1e28e488-e7d1-475f-9b42-e1f20be1b6cf: 'VultronObject' object has no attribute 'case_id'
finder-1       | INFO:     Processing item 'http://vendor:7999/api/v2/actors/515663dc-3ab9-4aa9-a0bc-6a97e8b710c6 Announce None' for actor 'http://finder:7999/api/v2/actors/1e28e488-e7d1-475f-9b42-e1f20be1b6cf'
finder-1       | INFO:     Dispatching activity of type 'None' with semantics 'announce_case_log_entry'
finder-1       | ERROR:    Unexpected error dispatching activity_id=urn:uuid:6035c298-dec3-4881-ba21-f12ed8b74b9f actor_id=http://vendor:7999/api/v2/actors/515663dc-3ab9-4aa9-a0bc-6a97e8b710c6 semantics=announce_case_log_entry
finder-1       | Traceback (most recent call last):
finder-1       |   File "/app/vultron/core/dispatcher.py", line 68, in _handle
finder-1       |     use_case_class(dl, event).execute()
finder-1       |     ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~^^
finder-1       |   File "/app/vultron/core/use_cases/received/sync.py", line 152, in execute
finder-1       |     case_id: str = entry.case_id
finder-1       |                    ^^^^^^^^^^^^^
finder-1       |   File "/app/.venv/lib/python3.13/site-packages/pydantic/main.py", line 1026, in __getattr__
finder-1       |     raise AttributeError(f'{type(self).__name__!r} object has no attribute {item!r}')
finder-1       | AttributeError: 'VultronObject' object has no attribute 'case_id'
finder-1       | ERROR:    Error processing inbox item for actor http://finder:7999/api/v2/actors/1e28e488-e7d1-475f-9b42-e1f20be1b6cf: 'VultronObject' object has no attribute 'case_id'
finder-1       | INFO:     Processing item 'http://vendor:7999/api/v2/actors/515663dc-3ab9-4aa9-a0bc-6a97e8b710c6 Announce None' for actor 'http://finder:7999/api/v2/actors/1e28e488-e7d1-475f-9b42-e1f20be1b6cf'
finder-1       | INFO:     Dispatching activity of type 'None' with semantics 'announce_case_log_entry'
finder-1       | ERROR:    Unexpected error dispatching activity_id=urn:uuid:6035c298-dec3-4881-ba21-f12ed8b74b9f actor_id=http://vendor:7999/api/v2/actors/515663dc-3ab9-4aa9-a0bc-6a97e8b710c6 semantics=announce_case_log_entry
finder-1       | Traceback (most recent call last):
finder-1       |   File "/app/vultron/core/dispatcher.py", line 68, in _handle
finder-1       |     use_case_class(dl, event).execute()
finder-1       |     ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~^^
finder-1       |   File "/app/vultron/core/use_cases/received/sync.py", line 152, in execute
finder-1       |     case_id: str = entry.case_id
finder-1       |                    ^^^^^^^^^^^^^
finder-1       |   File "/app/.venv/lib/python3.13/site-packages/pydantic/main.py", line 1026, in __getattr__
finder-1       |     raise AttributeError(f'{type(self).__name__!r} object has no attribute {item!r}')
finder-1       | AttributeError: 'VultronObject' object has no attribute 'case_id'
finder-1       | ERROR:    Error processing inbox item for actor http://finder:7999/api/v2/actors/1e28e488-e7d1-475f-9b42-e1f20be1b6cf: 'VultronObject' object has no attribute 'case_id'
finder-1       | INFO:     Processing item 'http://vendor:7999/api/v2/actors/515663dc-3ab9-4aa9-a0bc-6a97e8b710c6 Announce None' for actor 'http://finder:7999/api/v2/actors/1e28e488-e7d1-475f-9b42-e1f20be1b6cf'
finder-1       | INFO:     Dispatching activity of type 'None' with semantics 'announce_case_log_entry'
finder-1       | ERROR:    Unexpected error dispatching activity_id=urn:uuid:6035c298-dec3-4881-ba21-f12ed8b74b9f actor_id=http://vendor:7999/api/v2/actors/515663dc-3ab9-4aa9-a0bc-6a97e8b710c6 semantics=announce_case_log_entry
finder-1       | Traceback (most recent call last):
finder-1       |   File "/app/vultron/core/dispatcher.py", line 68, in _handle
finder-1       |     use_case_class(dl, event).execute()
finder-1       |     ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~^^
finder-1       |   File "/app/vultron/core/use_cases/received/sync.py", line 152, in execute
finder-1       |     case_id: str = entry.case_id
finder-1       |                    ^^^^^^^^^^^^^
finder-1       |   File "/app/.venv/lib/python3.13/site-packages/pydantic/main.py", line 1026, in __getattr__
finder-1       |     raise AttributeError(f'{type(self).__name__!r} object has no attribute {item!r}')
finder-1       | AttributeError: 'VultronObject' object has no attribute 'case_id'
finder-1       | ERROR:    Error processing inbox item for actor http://finder:7999/api/v2/actors/1e28e488-e7d1-475f-9b42-e1f20be1b6cf: 'VultronObject' object has no attribute 'case_id'
finder-1       | ERROR:    Too many errors processing inbox for actor http://finder:7999/api/v2/actors/1e28e488-e7d1-475f-9b42-e1f20be1b6cf, aborting.
finder-1       | INFO:     Processing outbox for actor http://finder:7999/api/v2/actors/1e28e488-e7d1-475f-9b42-e1f20be1b6cf
demo-runner-1  | 2026-04-15 15:39:25,448 ERROR    vultron.demo.utils: 🔴 Waiting for Finder to receive replicated log entry
demo-runner-1  | 2026-04-15 15:39:25,449 ERROR    vultron.demo.two_actor_demo: Two-actor demo failed: Timed out waiting for log entry (hash='6cde3f6c9cf03410a4e73557e0c4743bf0ef40cad790fb54846f13226c8c2a9f') for case 'urn:uuid:a344d2d8-3747-4128-b80c-b278f9ce5e9d' to appear in finder's DataLayer — replication may not have completed
demo-runner-1  | Traceback (most recent call last):
demo-runner-1  |   File "/app/vultron/demo/two_actor_demo.py", line 1211, in main
demo-runner-1  |     run_two_actor_demo(
demo-runner-1  |     ~~~~~~~~~~~~~~~~~~^
demo-runner-1  |         finder_client=finder_client,
demo-runner-1  |         ^^^^^^^^^^^^^^^^^^^^^^^^^^^^
demo-runner-1  |     ...<3 lines>...
demo-runner-1  |         vendor_id=vendor_id,
demo-runner-1  |         ^^^^^^^^^^^^^^^^^^^^
demo-runner-1  |     )
demo-runner-1  |     ^
demo-runner-1  |   File "/app/vultron/demo/two_actor_demo.py", line 1136, in run_two_actor_demo
demo-runner-1  |     wait_for_finder_log_entry(
demo-runner-1  |     ~~~~~~~~~~~~~~~~~~~~~~~~~^
demo-runner-1  |         finder_client=finder_client,
demo-runner-1  |         ^^^^^^^^^^^^^^^^^^^^^^^^^^^^
demo-runner-1  |         case_id=case.id_,
demo-runner-1  |         ^^^^^^^^^^^^^^^^^
demo-runner-1  |         entry_hash=entry_hash,
demo-runner-1  |         ^^^^^^^^^^^^^^^^^^^^^^
demo-runner-1  |     )
demo-runner-1  |     ^
demo-runner-1  |   File "/app/vultron/demo/two_actor_demo.py", line 846, in wait_for_finder_log_entry
demo-runner-1  |     raise AssertionError(
demo-runner-1  |     ...<3 lines>...
demo-runner-1  |     )
demo-runner-1  | AssertionError: Timed out waiting for log entry (hash='6cde3f6c9cf03410a4e73557e0c4743bf0ef40cad790fb54846f13226c8c2a9f') for case 'urn:uuid:a344d2d8-3747-4128-b80c-b278f9ce5e9d' to appear in finder's DataLayer — replication may not have completed
demo-runner-1  | 2026-04-15 15:39:25,451 ERROR    vultron.demo.two_actor_demo: ================================================================================
demo-runner-1  | 2026-04-15 15:39:25,451 ERROR    vultron.demo.two_actor_demo: ERROR SUMMARY
demo-runner-1  | 2026-04-15 15:39:25,451 ERROR    vultron.demo.two_actor_demo: ================================================================================
demo-runner-1  | 2026-04-15 15:39:25,451 ERROR    vultron.demo.two_actor_demo: Timed out waiting for log entry (hash='6cde3f6c9cf03410a4e73557e0c4743bf0ef40cad790fb54846f13226c8c2a9f') for case 'urn:uuid:a344d2d8-3747-4128-b80c-b278f9ce5e9d' to appear in finder's DataLayer — replication may not have completed
demo-runner-1  | 2026-04-15 15:39:25,451 ERROR    vultron.demo.two_actor_demo: ================================================================================
demo-runner-1 exited with code 1
 Compose Stopping Aborting on container exit...
 Container vultron-it-demo-runner-1 Stopping 
 Container vultron-it-demo-runner-1 Stopped 
 Container vultron-it-vendor2-1 Stopping 
 Container vultron-it-vendor-1 Stopping 
 Container vultron-it-coordinator-1 Stopping 
 Container vultron-it-finder-1 Stopping 
 Container vultron-it-case-actor-1 Stopping 
```
