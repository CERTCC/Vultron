---
source: Priority-345
timestamp: '2026-04-17T00:00:00+00:00'
title: 'Priority 345: DataLayer auto-rehydration'
type: priority
---

DL-REHYDRATE: auto-rehydration in SQLite/TinyDB adapters so `dl.read()` and
`dl.list()` always return fully typed domain objects. Audit and remove manual
`model_validate` coercion in use cases after completion.
