---
title: TRIG-02-003 says the CS notify-* behaviors are triggerable via the trigger API, but the only routes are demo-only under /demo/ and TRIG-02-006 does not list them
type: learning
timestamp: 2026-09-30T20:45:00Z
source: ISSUE-3829
signal: spec-ambiguity
---

Repointing the trigger routers' `Implements:` citations (#3829) meant deciding
which `TRIG-02` sub-requirement each endpoint implements. `TRIG-02-003` reads
"the following CS state-notification behaviors SHOULD be individually
triggerable via the trigger API: notify-fix-ready, notify-fix-deployed,
notify-published, notify-public-exploit, notify-attacks-observed". The only
routes that exist for `notify-fix-ready`, `notify-fix-deployed` and
`notify-published` are in `demo_triggers.py`, mounted under
`/actors/{actor_id}/demo/` and absent in `RunMode.PROD` (TRIG-09-002/003).
`notify-public-exploit` and `notify-attacks-observed` have no route at all.

`TRIG-02-006` enumerates the demo-only behaviors ("add-note-to-case,
close-case, sync-log-entry") and does not list the notify verbs, while
`TRIG-08-002` defines demo-only as "the only reason it exists is to let a demo
script puppeteer an actor through a step the actor's own BT would handle
autonomously" — which is a fair description of a vendor announcing fix
readiness in a scripted demo, and equally a fair description of a legitimate
actor decision a human operator would take.

So the corpus says three things at once about the notify verbs: they SHOULD be
on the trigger API (TRIG-02-003), they are not in the demo-only list
(TRIG-02-006), and the code exposes them only where demo-only triggers live
(TRIG-08-004 / TRIG-09-001). The pre-PR spec review flagged the citation of
`TRIG-02-003` on `/demo/` routes as claiming a SHOULD met only in PROTOTYPE
mode. The PR kept the citation, because the verbs *are* the TRIG-02-003
behaviors and where they are mounted is TRIG-08/09's business, but a reader
cannot tell from the spec whether the notify verbs belong under `/trigger/`
(and the demo mounting is a shortcut) or under `/demo/` (and TRIG-02-006's
list is incomplete).

What would resolve it: either add the three (five) notify verbs to
`TRIG-02-006` and say why a CS notification is puppeteering, or say in
`TRIG-02-003` that a general-purpose `/trigger/` route is expected and the
demo mounting is provisional. The trigger registry (ADR-0110, TRIG-12-004)
will carry an exposure column per verb, so whichever answer is chosen becomes
a data-table fact rather than a docstring judgment.
