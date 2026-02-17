# Bugs to fix

Items in this file supersede IMPLEMENTATION_PLAN.md.

Fix the following bugs. You will need to run the server to reproduce these bugs.
See AGENTS.md for instructions on how to run the server and validate your fixes.
hint: `uv run uvicorn vultron.api.main:app --host localhost --port 7999`

---

## ✅ FIXED (2026-02-17)

**Bug:** Demo 1 (Validate Report) failing with "Could not find case related to this report."

**Root Cause:** The `find_case_by_report()` function in `vultron/scripts/receive_report_demo.py` was checking `case_obj.content` instead of `case_obj.vulnerability_reports` to find cases containing a specific report.

**Fix:** Changed line 404 from:
```python
if case_obj.content and report_id in [str(r) for r in case_obj.content]:
```
to:
```python
if case_obj.vulnerability_reports and report_id in [str(r) for r in case_obj.vulnerability_reports]:
```

**Test:** Created `test/scripts/test_find_case_by_report.py` to verify the fix.

**Original Error Log:**
```
2026-02-17 12:46:42,314 INFO Calling GET http://localhost:7999/api/v2/datalayer/7aee73a9-73b2-4612-a6f5-1958ea6542d7
2026-02-17 12:46:42,315 DEBUG Starting new HTTP connection (1): localhost:7999
2026-02-17 12:46:42,320 DEBUG http://localhost:7999 "GET /api/v2/datalayer/7aee73a9-73b2-4612-a6f5-1958ea6542d7 HTTP/1.1" 200 217
2026-02-17 12:46:42,320 INFO Response status: 200
2026-02-17 12:46:42,320 DEBUG Response JSON: {
  "@context": "https://www.w3.org/ns/activitystreams",
  "type": "VulnerabilityCase",
  "id": "7aee73a9-73b2-4612-a6f5-1958ea6542d7",
  "name": "Case for Report 041bc195-e263-417e-b4ef-fadbf4205ce7",
  "preview": null,
  "mediaType": null
}
2026-02-17 12:46:42,321 ERROR Could not find case related to this report.
2026-02-17 12:46:42,321 ERROR Demo 1 failed: Could not find case related to this report.
Traceback (most recent call last):
  File "/Users/adh/Documents/git/vultron_pub/vultron/scripts/receive_report_demo.py", line 752, in main
    demo_validate_report(client, finder, vendor)
    ~~~~~~~~~~~~~~~~~~~~^^^^^^^^^^^^^^^^^^^^^^^^
  File "/Users/adh/Documents/git/vultron_pub/vultron/scripts/receive_report_demo.py", line 470, in demo_validate_report
    raise ValueError("Could not find case related to this report.")
ValueError: Could not find case related to this report.
...
2026-02-17 12:46:50,527 INFO ================================================================================
2026-02-17 12:46:50,527 INFO ALL DEMOS COMPLETE
2026-02-17 12:46:50,527 INFO ================================================================================
2026-02-17 12:46:50,527 ERROR 
2026-02-17 12:46:50,527 ERROR ================================================================================
2026-02-17 12:46:50,527 ERROR ERROR SUMMARY
2026-02-17 12:46:50,527 ERROR ================================================================================
2026-02-17 12:46:50,527 ERROR Total demos: 3
2026-02-17 12:46:50,527 ERROR Failed demos: 1
2026-02-17 12:46:50,527 ERROR Successful demos: 2
2026-02-17 12:46:50,527 ERROR 
2026-02-17 12:46:50,527 ERROR Demo 1: Validate Report:
2026-02-17 12:46:50,527 ERROR   Could not find case related to this report.
2026-02-17 12:46:50,527 ERROR 
2026-02-17 12:46:50,527 ERROR ================================================================================
```
