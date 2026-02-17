# Bugs to fix

Items in this file supersede IMPLEMENTATION_PLAN.md.

You will need to run the server to reproduce these bugs.
hint: `uv run uvicorn vultron.api.main:app --host localhost --port 7999`

---
2026-02-17 13:01:39,325 INFO Posting activity to vendorco's inbox: {
  "@context": "https://www.w3.org/ns/activitystreams",
  "type": "Accept",
  "id": "fc34e835-51f4-41ba-a20e-88a098a6b55a",
  "name": "https://vultron.example/organizations/vendorco Accept 3d5d8acb-0e9a-42aa-868d-f91efebebd94",
  "published": "2026-02-17T18:01:39+00:00",
  "updated": "2026-02-17T18:01:39+00:00",
  "content": "Validating the report as legitimate. Creating case.",
  "actor": "https://vultron.example/organizations/vendorco",
  "object": "3d5d8acb-0e9a-42aa-868d-f91efebebd94"
}
2026-02-17 13:01:39,325 INFO Calling POST http://localhost:7999/api/v2/actors/vendorco/inbox/
2026-02-17 13:01:39,326 DEBUG Starting new HTTP connection (1): localhost:7999
2026-02-17 13:01:39,332 DEBUG http://localhost:7999 "POST /api/v2/actors/vendorco/inbox/ HTTP/1.1" 202 4
2026-02-17 13:01:39,332 INFO Response status: 202
2026-02-17 13:01:39,333 DEBUG Response JSON: null
2026-02-17 13:01:40,338 INFO Calling GET http://localhost:7999/api/v2/datalayer/fc34e835-51f4-41ba-a20e-88a098a6b55a
2026-02-17 13:01:40,339 DEBUG Starting new HTTP connection (1): localhost:7999
2026-02-17 13:01:40,343 DEBUG http://localhost:7999 "GET /api/v2/datalayer/fc34e835-51f4-41ba-a20e-88a098a6b55a HTTP/1.1" 200 244
2026-02-17 13:01:40,343 INFO Response status: 200
2026-02-17 13:01:40,343 DEBUG Response JSON: {
  "@context": "https://www.w3.org/ns/activitystreams",
  "type": "Accept",
  "id": "fc34e835-51f4-41ba-a20e-88a098a6b55a",
  "name": "https://vultron.example/organizations/vendorco Accept 3d5d8acb-0e9a-42aa-868d-f91efebebd94",
  "preview": null,
  "mediaType": null
}
2026-02-17 13:01:40,343 INFO ValidateReport stored: {
  "@context": "https://www.w3.org/ns/activitystreams",
  "type": "Accept",
  "id": "fc34e835-51f4-41ba-a20e-88a098a6b55a",
  "name": "https://vultron.example/organizations/vendorco Accept 3d5d8acb-0e9a-42aa-868d-f91efebebd94",
  "preview": null,
  "mediaType": null
}
2026-02-17 13:01:40,343 INFO Calling GET http://localhost:7999/api/v2/datalayer/VulnerabilityCases/
2026-02-17 13:01:40,344 DEBUG Starting new HTTP connection (1): localhost:7999
2026-02-17 13:01:40,348 DEBUG http://localhost:7999 "GET /api/v2/datalayer/VulnerabilityCases/ HTTP/1.1" 200 258
2026-02-17 13:01:40,348 INFO Response status: 200
2026-02-17 13:01:40,348 DEBUG Response JSON: {
  "ebb777cb-1b56-461e-8145-b6206eee6ad3": {
    "@context": "https://www.w3.org/ns/activitystreams",
    "type": "VulnerabilityCase",
    "id": "ebb777cb-1b56-461e-8145-b6206eee6ad3",
    "name": "Case for Report bfb8bbfa-6341-4ff3-9c81-f90da7f77d60",
    "preview": null,
    "mediaType": null
  }
}
2026-02-17 13:01:40,348 INFO Calling GET http://localhost:7999/api/v2/datalayer/ebb777cb-1b56-461e-8145-b6206eee6ad3
2026-02-17 13:01:40,350 DEBUG Starting new HTTP connection (1): localhost:7999
2026-02-17 13:01:40,354 DEBUG http://localhost:7999 "GET /api/v2/datalayer/ebb777cb-1b56-461e-8145-b6206eee6ad3 HTTP/1.1" 200 217
2026-02-17 13:01:40,355 INFO Response status: 200
2026-02-17 13:01:40,355 DEBUG Response JSON: {
  "@context": "https://www.w3.org/ns/activitystreams",
  "type": "VulnerabilityCase",
  "id": "ebb777cb-1b56-461e-8145-b6206eee6ad3",
  "name": "Case for Report bfb8bbfa-6341-4ff3-9c81-f90da7f77d60",
  "preview": null,
  "mediaType": null
}
2026-02-17 13:01:40,355 ERROR Could not find case related to this report.
2026-02-17 13:01:40,355 ERROR Demo 1 failed: Could not find case related to this report.
Traceback (most recent call last):
  File "/Users/adh/Documents/git/vultron_pub/vultron/scripts/receive_report_demo.py", line 752, in main
    demo_validate_report(client, finder, vendor)
    ~~~~~~~~~~~~~~~~~~~~^^^^^^^^^^^^^^^^^^^^^^^^
  File "/Users/adh/Documents/git/vultron_pub/vultron/scripts/receive_report_demo.py", line 470, in demo_validate_report
    raise ValueError("Could not find case related to this report.")
ValueError: Could not find case related to this report.
...
2026-02-17 13:01:48,555 ERROR ================================================================================
2026-02-17 13:01:48,555 ERROR ERROR SUMMARY
2026-02-17 13:01:48,555 ERROR ================================================================================
2026-02-17 13:01:48,555 ERROR Total demos: 3
2026-02-17 13:01:48,555 ERROR Failed demos: 1
2026-02-17 13:01:48,555 ERROR Successful demos: 2
2026-02-17 13:01:48,555 ERROR 
2026-02-17 13:01:48,555 ERROR Demo 1: Validate Report:
2026-02-17 13:01:48,555 ERROR   Could not find case related to this report.
2026-02-17 13:01:48,555 ERROR 
2026-02-17 13:01:48,555 ERROR ================================================================================
