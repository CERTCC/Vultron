---
title: Demo Scenario Narratives
stakeholder_type: [platform-developer, project-contributor]
level: 300
---

# Demo Scenario Narratives

Each multi-actor demo scenario has a narrative page that describes one case's progress through the Coordinated Vulnerability Disclosure (CVD) process in domain terms: who acts, what they do, and why each step can only happen after the one before it.
The narratives name no container, endpoint, or helper function.
A narrative is the same case the demo runs, told from the participants' point of view.
The tutorials tell you how to run that case, and the protocol reference tells you which messages it produces.

## Scenarios

The table below is rendered at build time from the scenario registry.
Each scenario declares itself in its own demo module (ADR-0098, DEMOCI-11-009), so no copy of the table is committed here and it cannot drift.

These pages carry no status or maturity claim, because a page cannot know whether its scenario currently passes (DEMOCI-11-012).
The live answer is the [Demo Integration workflow](https://github.com/CERTCC/Vultron/actions/workflows/demo-integration.yml), which runs every registered scenario on each push to `main` and files an issue when one fails.

```python exec="true" idprefix=""
from vultron.metadata.demo_scenarios.render import render_page

print(render_page("narratives"))
```

## How to use these pages

- **To run a scenario**, follow [Running the Multi-Actor Container Demos](../../tutorials/container_demos.md), which selects any scenario by name.
  [Run the FV Demo](../../tutorials/fv-demo.md) walks the baseline scenario milestone by milestone.
- **To see the messages behind a step**, read the [FV Demo Protocol Reference](../../reference/fv-demo-protocol.md), which lists every activity the baseline scenario exchanges and the ledger entries it produces.
- **To understand the ledger entries each step names**, read [The CASE_MANAGER and the Case Ledger](../case_lifecycle/case_manager_and_ledger.md).
  Every narrative step names the entry it produces, and only the Case Actor writes them.

## The narratives are a conformance oracle

Each narrative's front matter declares the causal edges the protocol must produce: for every declared pair, the antecedent's ledger entry must appear before the consequent's.
Because the narratives are written independently of the code, they can contradict the implementation, which is what makes them useful for catching regressions ([ADR-0058](../../adr/0058-causal-gating-in-demo-scenarios.md), [ADR-0079](../../adr/0079-case-ledger-causal-ordering.md)).
The demo integration workflow's invariant harness checks every declared edge against the case ledger each scenario run produces (DEMOMA-22-005).
A step the ledger does not record, such as the initial report submission, is declared as unobservable and excluded from that check.
