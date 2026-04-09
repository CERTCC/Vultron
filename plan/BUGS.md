# Bugs to fix

Items in this file supersede IMPLEMENTATION_PLAN.md.

Use format `BUG-YYYYMMDDXX` for bug IDs, where `YYYYMMDD` is the date the bug
was identified and `XX` is a sequential number for that day. For example,  
the first bug identified on March 26, 2026 would be `BUG-2026032601`.
Include a brief description in the title, and provide detailed reproduction
steps, root cause analysis, and resolution steps in the body.

---

## BUG-2026040901 Two actor demo fails due to timeout — **FIXED**

**Status**: Fixed in commit (see IMPLEMENTATION_HISTORY.md for details).

`integration_tests/demo/run_multi_actor_integration_test.sh` fails with a
timeout waiting for a case to appear in the finder's DataLayer after the  
vendor engages the case and outbox delivery is triggered. The test fails  
with an assertion error indicating that the case did not appear in the  
finder's DataLayer within the expected time frame, suggesting that the  
outbox delivery may not have completed successfully.

```text
demo-runner-1  | 2026-04-09 19:28:56,291 INFO     vultron.demo.utils: 🚥 Vendor engages case (RM.VALID → RM.ACCEPTED)
demo-runner-1  | 2026-04-09 19:28:56,291 INFO     vultron.demo.utils: Posting trigger 'engage-case' for actor '68ab4176-ec93-442e-aa17-95d2f8d1d5a1': {'case_id': 'urn:uuid:77a41273-ef39-4084-bef3-f3cc1d258e86'}
vendor-1       | INFO:     Set participant 'http://vendor:7999/api/v2/actors/68ab4176-ec93-442e-aa17-95d2f8d1d5a1' RM state to ACCEPTED in case 'urn:uuid:77a41273-ef39-4084-bef3-f3cc1d258e86'
vendor-1       | INFO:     Actor 'http://vendor:7999/api/v2/actors/68ab4176-ec93-442e-aa17-95d2f8d1d5a1' engaged case 'urn:uuid:77a41273-ef39-4084-bef3-f3cc1d258e86' (RM → ACCEPTED)
demo-runner-1  | 2026-04-09 19:28:56,325 INFO     vultron.demo.utils: 🟢 Vendor engages case (RM.VALID → RM.ACCEPTED)
vendor-1       | INFO:     Processing outbox for actor 68ab4176-ec93-442e-aa17-95d2f8d1d5a1
demo-runner-1  | 2026-04-09 19:28:56,342 INFO     vultron.demo.utils: 📋 Finder's DataLayer received case via Vendor outbox delivery
demo-runner-1  | 2026-04-09 19:29:06,450 ERROR    vultron.demo.utils: ❌ Finder's DataLayer received case via Vendor outbox delivery
demo-runner-1  | 2026-04-09 19:29:06,451 ERROR    vultron.demo.two_actor_demo: Two-actor demo failed: Timed out waiting for case 'urn:uuid:77a41273-ef39-4084-bef3-f3cc1d258e86' to appear in finder's DataLayer — outbox delivery may not have completed
demo-runner-1  | Traceback (most recent call last):
demo-runner-1  |   File "/app/vultron/demo/two_actor_demo.py", line 923, in main
demo-runner-1  |     run_two_actor_demo(
demo-runner-1  |     ~~~~~~~~~~~~~~~~~~^
demo-runner-1  |         finder_client=finder_client,
demo-runner-1  |         ^^^^^^^^^^^^^^^^^^^^^^^^^^^^
demo-runner-1  |     ...<3 lines>...
demo-runner-1  |         vendor_id=vendor_id,
demo-runner-1  |         ^^^^^^^^^^^^^^^^^^^^
demo-runner-1  |     )
demo-runner-1  |     ^
demo-runner-1  |   File "/app/vultron/demo/two_actor_demo.py", line 815, in run_two_actor_demo
demo-runner-1  |     wait_for_finder_case(
demo-runner-1  |     ~~~~~~~~~~~~~~~~~~~~^
demo-runner-1  |         finder_client=finder_client,
demo-runner-1  |         ^^^^^^^^^^^^^^^^^^^^^^^^^^^^
demo-runner-1  |         case_id=case.id_,
demo-runner-1  |         ^^^^^^^^^^^^^^^^^
demo-runner-1  |     )
demo-runner-1  |     ^
demo-runner-1  |   File "/app/vultron/demo/two_actor_demo.py", line 700, in wait_for_finder_case
demo-runner-1  |     raise AssertionError(
demo-runner-1  |     ...<2 lines>...
demo-runner-1  |     )
demo-runner-1  | AssertionError: Timed out waiting for case 'urn:uuid:77a41273-ef39-4084-bef3-f3cc1d258e86' to appear in finder's DataLayer — outbox delivery may not have completed
demo-runner-1  | 2026-04-09 19:29:06,453 ERROR    vultron.demo.two_actor_demo: ================================================================================
demo-runner-1  | 2026-04-09 19:29:06,453 ERROR    vultron.demo.two_actor_demo: ERROR SUMMARY
demo-runner-1  | 2026-04-09 19:29:06,453 ERROR    vultron.demo.two_actor_demo: ================================================================================
demo-runner-1  | 2026-04-09 19:29:06,453 ERROR    vultron.demo.two_actor_demo: Timed out waiting for case 'urn:uuid:77a41273-ef39-4084-bef3-f3cc1d258e86' to appear in finder's DataLayer — outbox delivery may not have completed
demo-runner-1  | 2026-04-09 19:29:06,453 ERROR    vultron.demo.two_actor_demo: ================================================================================
demo-runner-1 exited with code 1
```

## BUG-2026040902 Finder timeout (incomplete fix of BUG-2026040901)

After the claimed fix to BUG-2026040901, the same test still fails.

`integration_tests/demo/run_multi_actor_integration_test.sh` fails with a
timeout waiting for a case to appear in the finder's DataLayer after the  
vendor engages the case and outbox delivery is triggered. Previous fix was
attempted but did not in fact resolve the issue.
BUG-2026040902 is not resolved until the shell script runs and exits with
"SUCCESS: scenario 'two-actor' passed."

```text
demo-runner-1  | 2026-04-09 20:25:21,079 INFO     vultron.demo.utils: 🚥 Vendor validates the vulnerability report
demo-runner-1  | 2026-04-09 20:25:21,079 INFO     vultron.demo.utils: Posting trigger 'validate-report' for actor '54dacb37-6f78-44e0-9824-617859138a99': {'offer_id': 'urn:uuid:f17497b0-fe3c-4f02-a448-7ae2eca3e883'}
vendor-1       | INFO:     BT setup complete for actor http://vendor:7999/api/v2/actors/54dacb37-6f78-44e0-9824-617859138a99
vendor-1       | INFO:     EvaluateReportCredibility: Evaluating credibility for report urn:uuid:8f8d05a0-df30-4270-93a2-74a318ac5743 (stub: always accepts)
vendor-1       | INFO:     EvaluateReportValidity: Evaluating validity for report urn:uuid:8f8d05a0-df30-4270-93a2-74a318ac5743 (stub: always accepts)
vendor-1       | INFO:     Stored ParticipantStatus (report-phase RM.VALID) 'urn:uuid:932a53fd-0170-575c-8ca4-c5ba6e9e37b0'
vendor-1       | INFO:     RM → VALID for report 'urn:uuid:8f8d05a0-df30-4270-93a2-74a318ac5743' (actor 'http://vendor:7999/api/v2/actors/54dacb37-6f78-44e0-9824-617859138a99')
vendor-1       | INFO:     Set participant 'http://vendor:7999/api/v2/actors/54dacb37-6f78-44e0-9824-617859138a99' RM state to VALID in case 'urn:uuid:2b55d408-dcde-46c3-a615-ee09f32fcca3'
vendor-1       | INFO:     BT execution completed: Status.SUCCESS after 1 ticks - 
demo-runner-1  | 2026-04-09 20:25:21,209 INFO     vultron.demo.utils: 🟢 Vendor validates the vulnerability report
demo-runner-1  | 2026-04-09 20:25:21,209 INFO     vultron.demo.two_actor_demo: Validate-report trigger result for actor 54dacb37-6f78-44e0-9824-617859138a99
demo-runner-1  | 2026-04-09 20:25:21,209 INFO     vultron.demo.utils: 📋 VulnerabilityCase exists in Vendor's DataLayer
vendor-1       | INFO:     Processing outbox for actor 54dacb37-6f78-44e0-9824-617859138a99
demo-runner-1  | 2026-04-09 20:25:21,251 INFO     vultron.demo.two_actor_demo: Case created: urn:uuid:2b55d408-dcde-46c3-a615-ee09f32fcca3
demo-runner-1  | 2026-04-09 20:25:21,251 INFO     vultron.demo.utils: ✅ VulnerabilityCase exists in Vendor's DataLayer
demo-runner-1  | 2026-04-09 20:25:21,252 INFO     vultron.demo.utils: 🚥 Vendor engages case (RM.VALID → RM.ACCEPTED)
demo-runner-1  | 2026-04-09 20:25:21,252 INFO     vultron.demo.utils: Posting trigger 'engage-case' for actor '54dacb37-6f78-44e0-9824-617859138a99': {'case_id': 'urn:uuid:2b55d408-dcde-46c3-a615-ee09f32fcca3'}
vendor-1       | INFO:     Set participant 'http://vendor:7999/api/v2/actors/54dacb37-6f78-44e0-9824-617859138a99' RM state to ACCEPTED in case 'urn:uuid:2b55d408-dcde-46c3-a615-ee09f32fcca3'
vendor-1       | INFO:     Actor 'http://vendor:7999/api/v2/actors/54dacb37-6f78-44e0-9824-617859138a99' engaged case 'urn:uuid:2b55d408-dcde-46c3-a615-ee09f32fcca3' (RM → ACCEPTED)
demo-runner-1  | 2026-04-09 20:25:21,301 INFO     vultron.demo.utils: 🟢 Vendor engages case (RM.VALID → RM.ACCEPTED)
vendor-1       | INFO:     Processing outbox for actor 54dacb37-6f78-44e0-9824-617859138a99
vendor-1       | INFO:     Processing outbox item for actor '54dacb37-6f78-44e0-9824-617859138a99': urn:uuid:b70325d2-f5ac-4f26-8820-bb1ceb406093
demo-runner-1  | 2026-04-09 20:25:21,324 INFO     vultron.demo.utils: 📋 Finder's DataLayer received case via Vendor outbox delivery
demo-runner-1  | 2026-04-09 20:25:31,437 ERROR    vultron.demo.utils: ❌ Finder's DataLayer received case via Vendor outbox delivery
demo-runner-1  | 2026-04-09 20:25:31,437 ERROR    vultron.demo.two_actor_demo: Two-actor demo failed: Timed out waiting for case 'urn:uuid:2b55d408-dcde-46c3-a615-ee09f32fcca3' to appear in finder's DataLayer — outbox delivery may not have completed
demo-runner-1  | Traceback (most recent call last):
demo-runner-1  |   File "/app/vultron/demo/two_actor_demo.py", line 923, in main
demo-runner-1  |     run_two_actor_demo(
demo-runner-1  |     ~~~~~~~~~~~~~~~~~~^
demo-runner-1  |         finder_client=finder_client,
demo-runner-1  |         ^^^^^^^^^^^^^^^^^^^^^^^^^^^^
demo-runner-1  |     ...<3 lines>...
demo-runner-1  |         vendor_id=vendor_id,
demo-runner-1  |         ^^^^^^^^^^^^^^^^^^^^
demo-runner-1  |     )
demo-runner-1  |     ^
demo-runner-1  |   File "/app/vultron/demo/two_actor_demo.py", line 815, in run_two_actor_demo
demo-runner-1  |     wait_for_finder_case(
demo-runner-1  |     ~~~~~~~~~~~~~~~~~~~~^
demo-runner-1  |         finder_client=finder_client,
demo-runner-1  |         ^^^^^^^^^^^^^^^^^^^^^^^^^^^^
demo-runner-1  |         case_id=case.id_,
demo-runner-1  |         ^^^^^^^^^^^^^^^^^
demo-runner-1  |     )
demo-runner-1  |     ^
demo-runner-1  |   File "/app/vultron/demo/two_actor_demo.py", line 700, in wait_for_finder_case
demo-runner-1  |     raise AssertionError(
demo-runner-1  |     ...<2 lines>...
demo-runner-1  |     )
demo-runner-1  | AssertionError: Timed out waiting for case 'urn:uuid:2b55d408-dcde-46c3-a615-ee09f32fcca3' to appear in finder's DataLayer — outbox delivery may not have completed
demo-runner-1  | 2026-04-09 20:25:31,439 ERROR    vultron.demo.two_actor_demo: ================================================================================
demo-runner-1  | 2026-04-09 20:25:31,439 ERROR    vultron.demo.two_actor_demo: ERROR SUMMARY
demo-runner-1  | 2026-04-09 20:25:31,439 ERROR    vultron.demo.two_actor_demo: ================================================================================
demo-runner-1  | 2026-04-09 20:25:31,439 ERROR    vultron.demo.two_actor_demo: Timed out waiting for case 'urn:uuid:2b55d408-dcde-46c3-a615-ee09f32fcca3' to appear in finder's DataLayer — outbox delivery may not have completed
demo-runner-1  | 2026-04-09 20:25:31,439 ERROR    vultron.demo.two_actor_demo: ================================================================================
demo-runner-1 exited with code 1
```
