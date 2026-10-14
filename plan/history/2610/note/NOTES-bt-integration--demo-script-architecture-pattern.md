---
source: NOTES-bt-integration--demo-script-architecture-pattern
timestamp: '2026-10-12T19:35:42.328046+00:00'
title: Demo Script Architecture Pattern
type: note
---

**Archived:** 2026-10-12
**Reason:** superseded: demo scenarios are declared with @scenario and drive protocol activity through triggers in helpers/workflow.py
**Superseded by:** vultron/demo/AGENTS.md; ADR-0098

---

## Demo Script Architecture Pattern

Each demo script should follow `receive_report_demo.py` as the reference
pattern:

1. `setup_*()` — create preconditions (actors, prior state)
2. `demo_*(server_url)` — execute the workflow via HTTP inbox POSTs
3. `show_state(dl)` — display relevant DataLayer state after workflow
4. `main()` — orchestrate with logging, call setup then demos

Use `httpx` or `requests` against a live FastAPI test server (via
`TestClient` for in-process testing, or a running server for integration
tests).
