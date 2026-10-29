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
  borderline examples; the `theme-fit` structural check, its untriaged list,
  the split line and the auto-calved marker it reads; the `theme-gate` check
  that refuses a new Issue breaking these rules; how to act on a theme-fit finding; and
  triage-label rules (`needs-info`, `ready-for-human`, and retired labels).
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
PAD-02-014 to PAD-02-025 in `specs/parallel-development.yaml`.

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
      - requirement rationales, stories, and links (requirements-traceability)
    color: 1D76DB
  - label: theme:requirements-traceability
    outcome: >-
      Every requirement says why it exists and who it serves, and agrees with
      the code and other specs
    in_bounds:
      - rationales, user stories, ADR and spec links, verification criteria
      - splitting, rewording, retiring, and reconciling requirements
    out_of_bounds:
      - code that lints, loads, or renders the specs (dev-workflow)
      - checks an outside implementer runs (verifiable-conformance)
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
      - the content of the requirements themselves (requirements-traceability)
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
- **Name the split on one line that names both labels**, for example
  `Theme split: theme:a covers the parser; theme:b covers the CLI.` The
  structural check accepts any body line that names both, so keep both on one
  line.

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
| A spec rationale backfill, or reconciling a spec statement with the code | `theme:requirements-traceability` | It changes what the requirements say, not the tools that read them |
| A production bug found while working a test-suite Epic | `theme:protocol-correctness` | The outcome is correct protocol behavior; the test only found it |
| Lint rules and exception-hygiene sweeps | `theme:dev-workflow` | They change how contributors work, not whether a green run is trustworthy |
| A flaky test or a CI gate that passes when it should fail | `theme:test-and-ci` | The outcome is a green run that means the code works |
| A conformance report an outside implementer runs | `theme:verifiable-conformance` | Its user is outside the project |

## The Structural Check

`uv run theme-fit` reads every open Issue with one GraphQL query and prints a
Markdown report: coherence per `Schedule` tier, each finding grouped by kind,
then the untriaged Issues. It changes nothing on GitHub. It exits 0 with no
findings, 1 with any, and 2 when the catalog or `gh` fails.

- **No parent is listed, not a finding.** PAD-01-007 calls a non-Epic Issue
  with no Epic ancestor untriaged. One with no parent at all appears under
  "Untriaged: no parent, needs routing" with its themes, so the report can
  still come back clean; one whose parent chain reaches no open Epic was wired
  wrongly and stays an `unparented` finding (PAD-02-028). Reason: workflows
  file their issues with a theme and no parent (PAD-02-027), and routing them
  is triage, not a repair. An untriaged Issue with no theme still gets a
  leaf-theme-count finding.

- **Coherence** is the share of children that match their Epic: a child is an
  open non-Epic Issue in its nearest Epic's tier (PAD-02-001), and it matches
  when it carries exactly one theme and its Epic carries that theme. Use
  `--coherence` for the table alone, `--json` for the whole report, and
  `--max-chars 65536` to cut the finding lists so the report fits an Issue
  body.
- **Finding kinds**: a leaf without exactly one theme, an Epic without one
  theme or a named split, a missing `Theme:` line, a child theme its Epic does
  not carry, a non-Epic whose parent chain reaches no open Epic (a parent in
  another repository ends the walk, since its number means nothing here), an Epic
  nested under an Epic, an auto-calved Epic still single-child, and a label
  the catalog does not list or lists as retiring.
- **A `Theme:` line counts** only when a dash with a space on each side
  follows the label and some outcome text follows the dash. The check does
  not judge whether the outcome is right; a reviewer does (PAD-02-016).
- **Auto-calved Epics carry `<!-- auto-calved -->`** as a line of their body.
  `create-issue` writes it when it calves an Epic with no user present; the
  check reports a marked Epic with fewer than two open sub-issues. Remove the
  marker once a person has reviewed the Epic. Reason: an unattended calve
  cannot judge whether the theme gathers more work, so a person must decide
  whether a lone child stays or moves.

## The Create-Time Gate

`theme-fit` finds breaches after the fact; `theme-gate` stops them at creation.
`manage_github_issue.sh` and `create_epic.sh` run it before they create
anything (PAD-02-023, PAD-02-025). Agents reach the first only through the
`create-issue` skill and the second only through `create-epic` (PAD-02-022,
PAD-02-013, PAD-02-024).

- **Rule**: a new Issue needs exactly one active theme, a `Theme:` line naming
  it, and an open parent carrying that theme; a new Epic needs one theme, or
  two with a named split, and a `Theme:` line.
- **Reason**: the label rules are the same ones `theme-fit` applies
  (`label_findings` in `vultron/metadata/planning/theme_fit/analyze.py`), so a
  created Issue never shows up in the report for a rule the gate could check.
  Only the blind content audit (`calve-epics` Mode 3) can tell whether a
  well-formed theme is the right one.

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
- **`ready-for-human`** — reserves an Issue for a human: an agent MUST NOT
  auto-select or claim it. The label does not change the Issue's `Status`
  (PAD-16-007).

The labels `needs-triage`, `ready-for-agent`, and `wontfix` are not used, because
each duplicates a fact the tracker already holds: untriaged means "no Epic
ancestor", `Ready` is computed, and "will not be actioned" is GitHub's "not
planned" close reason (PAD-16-010). Their retirement is tracked in #3717.
