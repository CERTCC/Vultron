---
title: Epic Themes — The Theme Catalog and How to Classify an Issue
status: active
kind: guidance
description: >
  The single source for `theme:` labels: a marked YAML block lists every theme
  (label, outcome, in-bounds, out-of-bounds, color, status), and the
  `theme-labels` script syncs GitHub from it. The rules for applying a theme:
  classify by outcome, one theme per leaf, an Epic's second theme only when its
  body names the split, the theme contains the grain, the `Theme:` reason line;
  borderline examples; how to act on a theme-fit finding; and triage-label rules
  (`needs-info`, `ready-for-human`, and retired labels).
related_specs:
  - specs/parallel-development.yaml
related_notes:
  - notes/parallel-development.md
relevant_packages:
  - vultron.metadata.planning
---

# Epic Themes — The Theme Catalog and How to Classify an Issue

A `theme:` label names the outcome an Issue delivers. Themes sit above Epics:
an Epic is one design idea, and every Epic sits inside one theme. The rules are
PAD-02-014 to PAD-02-021 in `specs/parallel-development.yaml`.

## The Catalog Is the Only Definition

The block below is the theme set. Edit it here, then run the sync; never create
or edit a `theme:` label on GitHub by hand.

- **Reason**: a label created by hand has no in-bounds or out-of-bounds text, so
  the next classifier has only its name to go on (PAD-02-019).
- **Sync**: `uv run theme-labels` reports what differs between the block and
  GitHub; `uv run theme-labels --apply` creates and updates labels to match.
  Neither deletes a label: a `theme:` label on GitHub that the block does not
  list is reported for a human to retire (PAD-02-020, PAD-02-021).
- **Readers**: tools load the block through
  `vultron.metadata.planning.themes.load_theme_catalog()`. Keep the two marker
  comments and the single `yaml` fence between them; the loader refuses the
  note if either is missing or doubled.
- **Retiring a theme**: set `status: retiring` and `replaced_by:`. The label
  stays on GitHub, with a description pointing at its replacements, until no
  open Issue carries it. Then remove the entry and delete the label by hand.

<!-- theme-catalog:begin -->
```yaml
themes:
  - label: theme:protocol-correctness
    outcome: >-
      Every message type and state transition handled correctly — no silent
      loss, no wrong-state moves
    in_bounds:
      - received and trigger use cases, behavior trees, state machines
      - a production defect, whatever work found it
    out_of_bounds:
      - transport and delivery mechanics (wire-delivery)
      - a defect in a test or the CI gate (test-and-ci)
    color: 1D76DB
  - label: theme:shared-case-history
    outcome: >-
      All participants see the same events in the same order; ledger is
      trustworthy and tamper-evident
    in_bounds:
      - case ledger, hash chain, replica sync
    out_of_bounds:
      - who receives a message (complete-participant-lifecycle)
    color: 1D76DB
  - label: theme:complete-participant-lifecycle
    outcome: >-
      Parties can join, change roles, negotiate pre-open, and exit cleanly
      across the full case arc
    in_bounds:
      - invite, join, role change, exit, recipient selection
    out_of_bounds:
      - one vul spread across several cases (multi-case-operations)
    color: 1D76DB
  - label: theme:multi-case-operations
    outcome: >-
      One vul can span several cases: cases split, merge, are re-offered, or
      are bridged
    in_bounds:
      - case split, merge, re-offer, bridge
      - links between cases that share a vul
    out_of_bounds:
      - ownership transfer of a single case (complete-participant-lifecycle)
    color: 1D76DB
  - label: theme:wire-delivery
    outcome: >-
      Messages reach their destination over HTTP: inbox/outbox, drain,
      ActivityPub/AS2 conformance
    in_bounds:
      - inbox and outbox adapters, delivery retry, AS2 parsing
    out_of_bounds:
      - what a receiver does with a message (protocol-correctness)
      - signing and transport authentication (authenticated-actor-communication)
    color: 1D76DB
  - label: theme:authenticated-actor-communication
    outcome: >-
      Every message signed, no actor impersonation, transport authenticated
      end-to-end
    in_bounds:
      - HTTP signatures, key handling, sender verification
    out_of_bounds:
      - role-based entitlement inside a case (complete-participant-lifecycle)
    color: 1D76DB
  - label: theme:vocabulary-extensions
    outcome: >-
      New message types beyond base spec: TLP, bug bounty, trust/reputation,
      Undo, extension policy
    in_bounds:
      - new activity and object types and the policy for adding them
    out_of_bounds:
      - fixing an existing message type (protocol-correctness)
    color: 1D76DB
  - label: theme:automated-case-monitoring
    outcome: >-
      Watch for embargo expiry, fix readiness, and exploitation, then trigger
      protocol actions
    in_bounds:
      - timers, watchers, and the actions they trigger
    out_of_bounds:
      - the embargo state machine itself (protocol-correctness)
    color: 1D76DB
  - label: theme:capability-architecture
    outcome: >-
      Capabilities and adapters have one shape, so a new capability plugs into
      the core without new glue
    in_bounds:
      - capability shapes, ports, adapter-layer structure
    out_of_bounds:
      - one adapter's delivery defect (wire-delivery)
      - production storage and secrets (deployable-in-production)
    color: 1D76DB
  - label: theme:deployable-in-production
    outcome: >-
      One org can run a Vultron actor on real infra: production store, secrets,
      observability
    in_bounds:
      - persistence backends, configuration, logging, metrics, containers
    out_of_bounds:
      - several organizations' nodes together (federated-multi-org-deployment)
    color: 1D76DB
  - label: theme:federated-multi-org-deployment
    outcome: >-
      Independent orgs run interconnected nodes: federation architecture, HA,
      IaC, runbooks
    in_bounds:
      - federation, high availability, infrastructure as code, runbooks
    out_of_bounds:
      - a single node's deployment (deployable-in-production)
    color: 1D76DB
  - label: theme:full-cvd-scenario-coverage
    outcome: >-
      Every documented CVD recipe is runnable and demonstrable in a browser
    in_bounds:
      - demo scenarios, the demo UI, scenario CI
    out_of_bounds:
      - a protocol defect a scenario exposes (protocol-correctness)
    color: 1D76DB
  - label: theme:verifiable-conformance
    outcome: >-
      Outside implementers can check their implementation against the spec's
      MUST requirements
    in_bounds:
      - conformance tests, profiles, and reports an outside implementer runs
    out_of_bounds:
      - spec-corpus tooling, loaders, and lint used only here (dev-workflow)
    color: 1D76DB
  - label: theme:standards-engagement
    outcome: >-
      External standards integration (CSAF, CVSSv4, FIRST, JSON-LD) and protocol
      versioning
    in_bounds:
      - crosswalks to external standards, versioning policy
    out_of_bounds:
      - new Vultron message types (vocabulary-extensions)
    color: 1D76DB
  - label: theme:cvd-measurement
    outcome: >-
      Research measures of CVD performance derived from case data: desiderata,
      timing metrics, baselines
    in_bounds:
      - metrics, desiderata, measurement studies
    out_of_bounds:
      - operational logging and metrics (deployable-in-production)
    color: 1D76DB
  - label: theme:adoption-documentation
    outcome: >-
      Public-facing docs: tutorials, how-tos, reference, explanation, and RFC
      prose
    in_bounds:
      - pages under docs/ written for adopters and implementers
    out_of_bounds:
      - docs for contributors to this codebase (contributor-onboarding)
    color: 1D76DB
  - label: theme:contributor-onboarding
    outcome: >-
      Contributors get from clone to merged PR and learn the internal design
      they build against
    in_bounds:
      - developer docs, setup, contribution guides
    out_of_bounds:
      - agent skills and issue process (dev-workflow)
    color: 1D76DB
  - label: theme:dev-workflow
    outcome: >-
      Internal dev workflow: agent skills, issue and board process, spec-corpus
      tooling, loaders
    in_bounds:
      - agent skills, issue and board process, Project #24
      - spec, notes, ADR, and history tooling and their loaders
      - lint and exception-hygiene work
    out_of_bounds:
      - CI gate reliability and test correctness (test-and-ci)
      - conformance checks for outside implementers (verifiable-conformance)
    color: 5319E7
  - label: theme:test-and-ci
    outcome: >-
      CI gates are reliable and tests are correct and efficient, so a green run
      means the code works
    in_bounds:
      - CI gate reliability, flaky tests, test correctness, suite efficiency
    out_of_bounds:
      - a production defect a test finds (protocol-correctness)
      - lint and exception hygiene (dev-workflow)
    color: 1D76DB
  - label: theme:project-health
    outcome: >-
      Codebase well tested, CI reliable, internal development friction-free
    in_bounds:
      - nothing new; relabel what remains
    out_of_bounds:
      - every new Issue
    color: 1D76DB
    status: retiring
    replaced_by:
      - theme:dev-workflow
      - theme:test-and-ci
```
<!-- theme-catalog:end -->

## Classify by Outcome

- **Rule**: pick the theme whose outcome the Issue delivers, never the theme of
  the mechanism it uses or the work that found it (PAD-02-016).
- **Reason**: a mechanism theme turns into a catch-all. Every change touches
  tests or tooling, so a mechanism theme absorbs work that belongs elsewhere.
- **Judge each Issue on its own content.** Do not copy the parent Epic's theme
  onto a child; read the child and classify it. When they differ, the child is
  in the wrong Epic, not the wrong theme.

## How Many Themes

- **A leaf has exactly one theme** (PAD-02-014). If two fit, the leaf does two
  things: split it, or pick the outcome its acceptance criteria test.
- **An Epic has one theme**, plus a second only when its body names the split
  between them (PAD-02-015). An unexplained second theme is a sign the Epic
  holds two design ideas.

## The Theme Contains the Grain

- **Rule**: every child of an Epic carries a theme the Epic carries
  (PAD-02-017). Epics are still cut by design idea (`calve-epics`), but each
  design idea sits inside one theme.
- **Reason**: an Epic whose children span themes cannot be ranked as one body of
  work, because its children serve different outcomes.
- **A child in another theme** gets moved to an Epic with its theme, gets
  relabeled if its label was wrong, or makes the Epic split along the theme
  boundary.

## The `Theme:` Reason Line

Every Issue body that carries a theme starts with one line naming the label and
the outcome this Issue delivers toward it (PAD-02-018):

```text
Theme: theme:dev-workflow — gives every skill one shared definition of the theme set.
```

- **Reason**: the line makes the classification checkable. A reviewer compares
  the line with the body; a label alone gives nothing to compare.
- **The outcome is this Issue's**, not the theme's outcome copied from the
  catalog.

## Borderline Examples

| Issue | Theme | Why |
|---|---|---|
| Spec-corpus tooling (spec-lint, loaders, spec-dump) | `theme:dev-workflow` | Only this project uses it; outside implementers do not run it |
| A production bug found while working a test-suite Epic | `theme:protocol-correctness` | The outcome is correct protocol behavior; the test only found it |
| Lint rules and exception-hygiene sweeps | `theme:dev-workflow` | They change how contributors work, not whether a green run is trustworthy |
| A flaky test or a CI gate that passes when it should fail | `theme:test-and-ci` | The outcome is a green run that means the code works |
| A conformance report an outside implementer runs | `theme:verifiable-conformance` | Its user is outside the project |

## Acting on a Theme-Fit Finding

A theme-fit report lists Issues that break a rule above. It applies no labels
and moves nothing; a person or an agent decides each finding:

1. **Read the Issue**, not its label, and classify it by outcome.
2. **If the label is wrong**, relabel it and rewrite the `Theme:` line.
3. **If the label is right but the Epic's theme differs**, move the Issue to an
   Epic with its theme. If none fits, calve one with `calve-epics`.
4. **If many children of one Epic share another theme**, split the Epic along
   that boundary rather than moving them one at a time.
5. **If an Epic has a second theme with no split named**, either name the split
   in its body or split the Epic.

## Triage Labels

Two triage labels exist alongside `theme:` and the workflow labels in
`notes/parallel-development.md` § "Label Taxonomy":

- **`needs-info`** — the only hold; keeps an Issue out of `Ready` while waiting
  on a person or a decision (PAD-16-004/005).
- **`ready-for-human`** — marks an Issue `Ready` that an agent must skip;
  a human implements it (PAD-16-007).

The labels `needs-triage`, `ready-for-agent`, and `wontfix` are not used;
their retirement is tracked in #3717.
