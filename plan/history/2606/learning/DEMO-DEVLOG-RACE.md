---
source: DEMO-DEVLOG-RACE
timestamp: '2026-06-22T19:35:30.377467+00:00'
title: 'Demo devlog race: use BackgroundTasks for demo step logging'
type: learning
---

When a demo step writes a `demo_step` devlog entry while a background task
is still processing the previous step, `asyncio.run()` inside the background
thread can conflict with the running event loop. Use `starlette`
`BackgroundTasks` for all demo devlog writes (never `asyncio.run()` from a
sync thread). Register the `DevlogWriter` task via `background_tasks.add_task()`
so it runs after the response is sent.

**Promoted**: 2026-06-22 — captured in `notes/bt-integration.md`
(Demo Devlog Race Fix section).
Docs PR: <https://github.com/CERTCC/Vultron/pull/1112>.
