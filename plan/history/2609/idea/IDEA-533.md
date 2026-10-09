---
source: IDEA-533
timestamp: '2026-09-24T18:51:58.975310+00:00'
title: 'Idea: Interactive ReactFlow Demo UI with CYOA Scenarios for Stakeholder Presentations'
type: idea
---

## Summary

Replace log-scrolling demos with a polished, interactive ReactFlow web UI
that lets non-technical stakeholders experience Vultron's CVD protocol
behavior as a choose-your-own-adventure. The UI visualizes protocol state
in real time across all running actor containers and lets a presenter (or
viewer) make real protocol decisions at key branch points.

## Motivation

Watching Python logs scroll by convinces developers that the system works.
It does nothing for government funders deciding whether to invest, or
industry practitioners deciding whether to adopt Vultron. We need a
presentation artifact that:

- Shows the protocol as a living, interactive story
- Lets stakeholders take the role of a participant and feel the protocol
  working
- Works as a turnkey demo: `git clone; docker compose up; open browser`
- Scales from the two-actor simple CVD case to multi-vendor supply chain
  scenarios without changing the UI architecture

## Design (resolved via grill-me session 2026-05-15)

Full design notes: `notes/demo-interactive-ui.md`

### Three-Scenario Set

All three scenarios run in the same UI, differing only in actor count and
swim lanes:

| Scenario | Actors | Containers | Narrative |
|----------|--------|------------|-----------|
| A — Two-Actor | Finder, Vendor, Case Actor | 2 | Simple CVD: researcher reports a bug to a vendor directly |
| B — Three-Actor | Finder, Vendor, Coordinator, Case Actor | 4 | MPCVD: reporter routes through a neutral coordinator for a widely-used library |
| C — Multi-Vendor | Finder, Coordinator, Vendor1, Vendor2, Case Actor | 5 | Supply chain: shared component used by multiple vendors |

### CYOA Branch Points (priority order)

1. Report validation (validate / invalidate-hold / invalidate-close)
2. Embargo negotiation (accept / reject / counter-propose)
3. Publication (on schedule / early / request extension)
4. Embargo collapse response (re-negotiate / accelerate)
5. Case ownership transfer (retain / offer to coordinator)

The Python demo scripts remain as automated happy-path puppeteers and
can be observed through the same UI.

### UI Architecture

- **Frontend**: ReactFlow (JS/React) in a Docker Compose service
- **Deployment**: All-in-one `docker compose up` — turnkey for demos
- **Layout**: Top = actor network graph with visual state-machine
  scorecards; Bottom = vertical swimlane message timeline, newest at top
- **Live updates**: WebSocket event stream per actor container
  (`ws://actor-host/api/v2/demo/events`) — demo-only, not in production
- **Interactivity**: UI calls the same trigger endpoints as demo scripts;
  CYOA choices are labeled with role names ("As the Vendor, choose...")
- **Landing**: Scenario selector with CERT/CC branding and prototype
  disclaimer

<img width="800" height="800" alt="Image" src="https://github.com/user-attachments/assets/bc416b2e-1922-4b3b-a4cf-fd61f12350de" />

### Actor Scorecards

Each actor bubble in the graph shows:

- Visual LED-style state machine indicators for RM / EM / CS
- Plain-language narrative label ("Embargo Active", "Waiting for vendor")
- Role badges (REPORTER, VENDOR, COORDINATOR, CASE_MANAGER)

### Development Sequence

1. Finish two-actor happy path (current / in progress)
2. Build interactive UI on top of two-actor scenario
3. Port three-actor scenario (remove and reconstruct old broken code)
4. Port multi-vendor scenario

## References

- `notes/demo-interactive-ui.md` — full design notes from this session
- `notes/demo-future-ideas.md` — earlier scenario ideas
- `notes/two-actor-demo.md` — current two-actor demo design
- `wip_notes/roadmap.md` — mentions extending two-actor to more actors
- `notes/demo-review-26042001.md` — archived; explains why old demos all failed
- `vultron/demo/scenario/three_actor_demo.py` — old three-actor code (to be removed)
- `vultron/demo/scenario/multi_vendor_demo.py` — old multi-vendor code (to be removed)

**Processed**: 2026-09-24 — planned in group G19 (#2847); implementation tracked in #3640, #3641, #3642, #3643.
Docs PR: <https://github.com/CERTCC/Vultron/pull/3639>.
Notes: `notes/demo-interactive-ui.md`. ADR: `docs/adr/0104-interactive-demo-ui-live-ledger-watcher.md`.
