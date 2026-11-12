---
status: accepted
status_override: >-
  Decided by the maintainer in the planning interview for #6336 on 2026-11-12.
date: 2026-11-12
created: 2026-11-12
updated: 2026-11-12
revision: 1
deciders: Allen D. Householder
consulted: Vultron maintainers
informed: Vultron implementers
stakeholder_type: [project-contributor]
---

# The Shadow Is a Streamlit Dashboard, Shipped as a Compose Service

## Context and Problem Statement

The shadow ([ADR-0190](0190-shadow-mode-is-a-standalone-read-only-advisor-that-translates-a-case-on-request.md)) needs a user interface: an analyst enters a case number and a credential, and sees Vultron's analysis of the case.
The project's existing browser interface is the React app in `ui/` ([ADR-0104](0104-interactive-demo-ui-live-ledger-watcher.md)).
Its Log Replay mode maps ledger entries to states and checks transitions in TypeScript, a second model of the protocol beside the Python one, and the maintainer does not work in TypeScript.
Getting the shadow running should take a clone and one command.

**What does the shadow's interface run on, and how is it packaged?**

## Decision Drivers

- The analysis is Python, and the people maintaining it read Python.
- A second implementation of the protocol's state model can drift from the Python state machines.
- An analyst should read a case's standing at a glance, not from paragraphs.
- The shadow holds embargoed case data in memory, so the page must not be reachable from elsewhere on the network, and nothing should persist.

## Considered Options

- Add a mode to the React app in `ui/`, backed by a small local Python service.
- A Streamlit app in Python.
- A Streamlit app for the shadow, plus moving the React app's Log Replay to Python now.

## Decision Outcome

Chosen option: "A Streamlit app in Python", because the whole tool stays in the language of its analysis and reuses the Python projection and measures directly, with no second model of the protocol.

1. **Streamlit, scoped to the shadow.** Streamlit is a sanctioned dependency for the shadow tool only. No code outside the shadow tool imports it.
2. **A dashboard, not a report.** The page presents a case's standing as a scoreboard: icons, colors and short labels an analyst reads at a glance.
3. **One Compose service.** The shadow ships as a `shadow` service, so a clone plus `docker compose up shadow` starts it.
4. **Closed by packaging.** The service mounts no persistent volume, so a long-lived copy has nowhere to go. It listens on the loopback interface only. The credential is entered in the page or passed in the environment when the service starts, and never written into an image or a compose file.
5. **`ui/` is not decided here.** The React app is unchanged. Whether its Log Replay mode moves to Python is a later decision, made once the shadow's Python timeline exists to compare with it.

### Consequences

- Good, because the shadow's every part is Python its maintainers can read.
- Good, because the dashboard calls the real projection and measures, so it cannot disagree with them.
- Bad, because the project now has two interface stacks until the later decision on `ui/`.
- Bad, because Streamlit's timeline views are less polished than the React app's animated swim lanes.

## Validation

`specs/case-shadow.yaml` states the packaging rules (no volume, loopback only, credential at runtime), each citing this record.

## Pros and Cons of the Options

### A mode in the React app, backed by a local Python service

- Good, because Log Replay's timeline would show a translated case unchanged.
- Bad, because every change to the interface is TypeScript.
- Bad, because the TypeScript state model would grow a new consumer.

### A Streamlit app in Python

- Good, because the analysis and its display are one Python program.
- Bad, because it adds a framework beside the React toolchain.

### Streamlit now, and Log Replay moved to Python now

- Good, because the project would end with one interface stack.
- Bad, because it decides the React app's future before there is a Python timeline to compare it with.

## More Information

Planned in #6336, with the maintainer, on 2026-11-12. The maintainer approved Streamlit as a new framework in that interview.

Generated spec requirements: `case-shadow.yaml` SHD-02.
