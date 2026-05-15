---
title: Interactive Demo UI — Scenarios and Architecture
status: draft
description: >
  Design notes for the Vultron interactive demo UI: a ReactFlow-based
  choose-your-own-adventure experience for stakeholder presentations,
  covering the three scenario set, UI architecture, actor visualization,
  WebSocket event streaming, and the relationship to existing demo scripts.
related_notes:
  - notes/demo-future-ideas.md
  - notes/two-actor-demo.md
related_specs:
  - specs/multi-actor-demo.yaml
  - specs/event-driven-control-flow.yaml
relevant_packages:
  - vultron/demo/scenario
---

# Interactive Demo UI — Scenarios and Architecture

**Source**: 2026-05-15 design session (grill-me).

---

## Purpose

The goal of the interactive demo UI is to make Vultron's CVD protocol
behavior legible and compelling to non-technical stakeholders — primarily
government funders and program managers, then industry practitioners
(vendors, coordinators, CNA staff). Watching Python logs scroll by
convinces developers; it does nothing for funders. The UI replaces logs
with a live, interactive visualization of protocol state and message
exchange that tells a story.

---

## Target Audiences (in priority order)

1. **Government funders / program managers** — Does this work? Is it
   worth continued investment?
2. **Industry security teams** (vendors, coordinators, CNA staff) — Does
   this fit into real CVD workflows? Would I use it?
3. **Policy researchers / academics** — Is the protocol formally correct?
   (This group requires the most polish; they come after 1 and 2 have
   bought in.)

---

## Three-Scenario Set

All three scenarios share the same UI; only the number of actor bubbles
and swim lanes differs.

### Scenario A — Two-Actor: Simple CVD

**Narrative framing**: A security researcher finds a bug in a single
product and reports it directly to the vendor.

**Actors**: Finder (Reporter), Vendor, Case Actor (co-located in Vendor
container)

**Docker containers**: 2 (`finder`, `vendor`)

**Status**: Being rebuilt from the ground up (current work). This is
the foundational scenario — all others depend on it.

### Scenario B — Three-Actor: MPCVD with Coordinator

**Narrative framing**: A widely-used open source library has a
vulnerability. The reporter doesn't know who all the affected vendors
are, so they report to a neutral coordinator (a CERT-style organization)
who manages the multi-party disclosure.

**Actors**: Finder (Reporter), Vendor, Coordinator, Case Actor

**Docker containers**: 4 (`finder`, `vendor`, `coordinator`,
`case-actor`)

**Status**: Existing code must be removed and reconstructed on the
rebuilt two-actor foundation.

### Scenario C — Multi-Vendor: Supply Chain

**Narrative framing**: A shared software component (e.g., a logging
library) is used by multiple vendors. A vulnerability is discovered,
requiring coordinated disclosure across an expanding set of vendors.

**Actors**: Finder (Reporter), Coordinator, Vendor1, Vendor2, Case Actor

**Docker containers**: 5 (`finder`, `coordinator`, `vendor1`, `vendor2`,
`case-actor`)

**Status**: Existing code must be removed and reconstructed.

---

## Choose-Your-Own-Adventure (CYOA) Model

The interactive UI lets a human viewer "play" one or more actors in the
scenario, making real protocol decisions at key branch points. The human
is explicitly assigned a role at each decision: **"As the Vendor, choose
one of the following..."**

### Branch Points (in priority order)

1. **Report Submission** — As the Vendor: validate / invalidate-hold /
   invalidate-close
2. **Embargo Negotiation** — As the Finder or Vendor: accept the
   proposed embargo / reject / counter-propose different terms
3. **Publication** — As any participant: publish on the agreed date /
   announce early publication / request embargo extension
4. **Embargo Collapse** — As participants: re-negotiate / agree to
   accelerate
5. **Case Ownership Transfer** — As the Vendor: retain ownership /
   offer to a Coordinator

The full set of CYOA branch points corresponds to protocol decision
nodes that the original Vultron simulator exposed via fuzzer BT nodes.
Any place the current demo scripts call a trigger that advances the
protocol state is a candidate branch point. Future work may expose all
of them; the priority order above governs what gets interactive first.

### Scripted Baseline

The Python demo scripts (`two_actor_demo.py`, etc.) remain as
**automated puppeteers** that take the happy-path branch at every
decision point. They are not replaced by the UI; they are a
complementary way to drive the same trigger endpoints. Critically, the
demo scripts can be observed through the same UI — a presenter can run
the script automatically while the audience watches the UI animate.

---

## UI Architecture

### Deployment

Single `docker compose up` includes the UI service alongside the
Vultron actor containers. The full stack is self-contained:
`git clone; docker compose up; open browser`.

### Frontend

**ReactFlow** (JS/React) for the network graph and interactive
node/edge rendering. ReactFlow was chosen over Streamlit because:

- Native graph visualization with animatable edges
- Interactive nodes that can surface action panels ("As the Vendor,
  choose...")
- Richer and more polished for stakeholder presentations

### Layout

```text
┌─────────────────────────────────────────────────────────┐
│  VULTRON DEMO   [Scenario A ▼]   [Reset]   [Run Auto]   │
│  CERT/CC — Research Prototype                           │
├─────────────────────────────────────────────────────────┤
│                                                         │
│   [Finder]  ──msgs──>  [Vendor]  ──msgs──>  [Case Actor]│
│   scorecard            scorecard            scorecard   │
│                                                         │
├─────────────────────────────────────────────────────────┤
│  Message Timeline (newest at top, history grows down)   │
│  ┌──────────────────────────────────────────────────┐  │
│  │ Finder ──[Offer(VulnReport)]──> Vendor           │  │
│  │ Vendor ──[Create(Case)]──> CaseActor             │  │
│  │ ...                                              │  │
│  └──────────────────────────────────────────────────┘  │
└─────────────────────────────────────────────────────────┘
```

**Top section**: Network graph of actor nodes with animated message
edges. Each actor node shows a **scorecard**: a visual LED-style
indicator panel for RM / EM / CS state machines (not raw enum labels)
plus a plain-language narrative status (e.g., "Embargo Active",
"Waiting for vendor response").

**Bottom section**: Vertical swimlane message timeline, newest messages
at the top. Each message is a row in the swimlane showing sender →
receiver, activity type, and a human-readable description.

**Landing page**: Scenario selector with CERT/CC branding and a
"Research Prototype — Not for Production Use" disclaimer.

### Actor Scorecards

Each actor bubble displays:

- **Visual state machine map**: small diagram or "LED row" for RM / EM
  / CS states — current state highlighted
- **Narrative label**: plain-English status (e.g., "Report received,
  waiting for validation", "Embargo active", "Case closed")
- **Role badges**: REPORTER, VENDOR, COORDINATOR, CASE_MANAGER

Raw state-machine labels (RM.V, EM.A, etc.) are available on hover /
expand, but are not the primary display.

### Live State Updates — WebSocket Event Stream

Each Vultron actor container exposes a **demo-only WebSocket endpoint**
(e.g., `ws://vendor:7902/api/v2/demo/events`). This endpoint streams
internal state-change events to any connected observer.

Key constraints:

- **Demo-only**: this endpoint MUST NOT be present in the production
  Vultron server. It is gated by a feature flag or build variant to
  prevent accidental information leakage in real deployments.
- The UI maintains one WebSocket connection per actor in the scenario.
- Each event message includes: actor ID, event type, new state,
  activity ID, and a human-readable description.

The UI does not poll DataLayer endpoints for live updates; it relies on
the WebSocket stream. DataLayer reads are used only for initial state
hydration on page load and for milestone verification assertions.

### Trigger Calls

The UI drives the scenario by calling the same trigger endpoints used
by the Python demo scripts:

```http
POST /actors/{id}/trigger/{behavior}
POST /actors/{id}/demo/{behavior}
```

When the user clicks a CYOA choice (e.g., "Validate Report"), the UI
POSTs the corresponding trigger and then waits for the resulting
WebSocket events to animate the message flow.

---

## Development Sequence

1. **Finish two-actor happy path** (current work) — automated scripted
   demo with milestone verification.
2. **Build the interactive UI** on top of the two-actor demo — ReactFlow
   graph + swimlane timeline + WebSocket event stream + CYOA branching
   for the two-actor scenario.
3. **Port three-actor scenario** (removing and reconstructing from old
   broken code) — the UI is already ready; plug in additional actor
   nodes and swim lanes.
4. **Port multi-vendor scenario** — same pattern.

The old demo scripts (`three_actor_demo.py`, `multi_vendor_demo.py`)
MUST be removed before reconstruction. They are built on the old
(broken) architecture and will create confusion if kept alongside the
new implementations.

---

## Relationship to the Roadmap

This design fits into the roadmap at two points:

- **Now** (completing two-actor): foundational scenario is the
  prerequisite for the UI.
- **Later** (full protocol behavior): the CYOA branching model is the
  natural home for failure-mode scenarios — embargo collapse, vendor
  decline, reporter going silent. Once the happy-path UI exists, adding
  non-happy branches is a matter of wiring up new CYOA options.

---

## Open Questions / Future Work

- **WebSocket event schema**: needs to be formally specified as part of
  the demo-only API surface.
- **CYOA script format**: the branching scenario logic may benefit from
  a declarative format (e.g., a YAML scenario tree) rather than
  hard-coded React state.
- **State machine visualization**: LED-style indicators need a visual
  design pass. Could use SVG state diagrams from the existing Vultron
  documentation as the base.
- **Multi-actor container startup sequence**: the "Start Demo" button
  behavior (spinning up containers vs. assuming they're already up)
  needs to be decided for the docker-compose integration.
- **Accessibility**: the graph visualization must be accessible for
  stakeholders who cannot read color-coded state indicators.
