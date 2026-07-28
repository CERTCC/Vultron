---
title: "BT Fuzzer Nodes: RM Publication"
status: active
description: >
  Catalog of fuzzer (stub) BT nodes for the Publication sub-workflow
  (`PublicationBt`): publication readiness, disclosure decisions,
  content preparation, and advisory-publishing nodes used in simulation.
related_specs:
  - specs/behavior-tree-integration.yaml
related_notes:
  - notes/bt-fuzzer-nodes-report-management.md
  - notes/bt-integration.md
  - notes/bt-canonical-reference.md
  - notes/bt-fuzzer-nodes.md
relevant_packages:
  - vultron/bt/report_management
---

## Publication

These nodes belong to the `Publication` fallback tree
(`vultron/bt/report_management/_behaviors/publication.py`), which models
the process of deciding what vulnerability-related artifacts to publish,
preparing them, and executing publication.

### `AllPublished`

- **Node name**: `AllPublished`
- **btz type**: `AlmostAlwaysFail` (p=0.10)
- **Source file**: `report_management/fuzzer/publication.py`
- **Parent tree**: `Publication`
- **Semantic function**: Condition — check whether all intended publication
  artifacts (report, fix, exploit) have been published
- **Input dependency**: Case/publication status metadata query; automatable
  against a publication tracking field
- **Notes**: Fails most of the time in simulation because publication
  is an active goal being worked toward
- **Automation potential**: **High** — publication status flag on the case record; fully automatable as a metadata check.
- **New-arch cross-ref**: `vultron.demo.fuzzer.report_management.publication.AllPublished`
- **Call-out point shape**: ProtocolInternal — reads a publication-completion flag maintained in the
  local DataLayer / BT blackboard by the protocol's own BT execution (written by `Publish` nodes).
  No external agent seam — the flag is local and actor-scoped.
  (Category 3 per issue #1199 triage — reads a flag written by the protocol's own BT execution.)
- **Factory-fn placement**: FUTURE (not part of the Production Collapse 2 lean
  shape, issue #1310) — a top-level early-exit ProtocolInternal condition check
  that short-circuits the whole subtree once all artifacts are published. The
  lean `create_publication_tree` omits this idempotency guard for now; if added,
  it would wrap the `PublicationBT` Sequence in a `Selector(AllPublished, …)`.
  Tracked with the broader publication workflow in issue #1251.

### `PublicationIntentsSet`

- **Node name**: `PublicationIntentsSet`
- **btz type**: `UsuallyFail` (p=0.25)
- **Source file**: `report_management/fuzzer/publication.py`
- **Parent tree**: `Publication`
- **Semantic function**: Condition — check whether publication intentions
  (what to publish, when, and in what format) have been established for
  this case
- **Input dependency**: Case metadata check; publication plan document or
  structured publication intent flags
- **Notes**: Fails most of the time in simulation because setting intents
  is an early workflow step being modeled
- **Automation potential**: **High** — publication intent flags on the case record; fully automatable as a metadata check.
- **New-arch cross-ref**: `vultron.demo.fuzzer.report_management.publication.PublicationIntentsSet`
- **Call-out point shape**: ProtocolInternal — reads a flag written by `PrioritizePublicationIntents`
  during the same BT execution cycle; the flag lives on the local DataLayer / BT blackboard.
  No external agent seam — the flag is local and actor-scoped.
  (Category 3 per issue #1199 triage — reads a flag written by the protocol's own BT execution.)
- **Factory-fn placement**: Eliminated (Production Collapse 2, issue #1310) —
  the flag check disappears in production; the BT reads the
  `PublicationIntentDecision` record directly via `ShouldPublishX` gate nodes.
  No longer a separate BT leaf or factory parameter.

### `PrioritizePublicationIntents`

- **Node name**: `PrioritizePublicationIntents`
- **btz type**: `AlwaysSucceed` (p=1.00)
- **Source file**: `report_management/fuzzer/publication.py`
- **Parent tree**: `Publication`
- **Semantic function**: Action — establish and record publication
  intentions: what artifacts to publish, their priority order, timing, and
  format
- **Input dependency**: Human analyst decision, publication policy, or
  automated policy engine; may depend on case context (embargo status,
  fix availability, threat level)
- **Notes**: Always succeeds in simulation; in production this involves
  structured editorial/policy decisions
- **Automation potential**: **Medium** — standard policy-driven publication priorities (e.g., always publish report and fix) can be automated; editorial or legal exceptions require human judgment.
- **New-arch cross-ref**: `vultron.demo.fuzzer.report_management.publication.PrioritizePublicationIntents`
- **Call-out point shape**: Evaluator
- **Factory-fn placement**: Implemented (Production Collapse 2, issue #1310) —
  `vultron.core.behaviors.report.publication_tree.create_publication_tree`
  (`prioritize_publication_intents_factory` param) — the surviving Evaluator;
  runs first and writes a structured `PublicationIntentDecision` record that
  gates the three per-artifact arms. See Production Collapse 2 below.

### `Publish`

- **Node name**: `Publish`
- **btz type**: `AlmostAlwaysSucceed` (p=0.90)
- **Source file**: `report_management/fuzzer/publication.py`
- **Parent tree**: `Publication`
- **Semantic function**: Action — execute the publication of a prepared
  artifact to the intended audience (advisory, patch, bulletin, etc.)
- **Input dependency**: Publication platform API (CMS, advisory database,
  package repository, NVD/CVE submission); could be fully automated
- **Notes**: Succeeds almost always in simulation; in production may involve
  API calls to advisory publishing platforms
- **Automation potential**: **High** — advisory platform APIs (NVD, CVE.org, CMS, package repository) enable fully automated artifact publication.
- **New-arch cross-ref**: `vultron.demo.fuzzer.report_management.publication.Publish`
- **Call-out point shape**: Actuator — submits an already-prepared artifact to an external advisory platform (NVD, CVE.org, CMS, package repository, or equivalent) via an API call; the side effect is the externally visible published entry at the target platform. There is no new content artifact placed on the blackboard; the preceding Prepare* nodes produce the content.
- **Factory-fn placement**: Wired (Production Collapse 2, issue #1310) —
  `vultron.core.behaviors.report.publication_tree.create_publication_tree`
  (`publish_factory` param, applied once per arm) — terminal Actuator node at
  the end of each per-artifact `Do…` Sequence (`PrepareExploit → PublishExploit`,
  `PrepareFix → PublishFix`, `PrepareReport → PublishReport`).
  See Production Collapse 4 below — this single leaf still expands into a
  draft-review-submit pipeline (ADR-0030 / BT-20-004), tracked separately.

### `NoPublishExploit`

- **Node name**: `NoPublishExploit`
- **btz type**: `UsuallySucceed` (p=0.75)
- **Source file**: `report_management/fuzzer/publication.py`
- **Parent tree**: `Publication`
- **Semantic function**: Condition — check the publication intent flag for
  the exploit artifact; `SUCCESS` means "do not publish exploit"
- **Input dependency**: Publication intent record set by
  `PrioritizePublicationIntents`; case policy
- **Notes**: Succeeds (no exploit publication) in most cases, reflecting
  that exploit publication is not always required or desired
- **Automation potential**: **TerminalPlaceholder** — BT bypass fallback leaf; no decision logic required.
- **New-arch cross-ref**: `vultron.demo.fuzzer.report_management.publication.NoPublishExploit`
- **Call-out point shape**: ProtocolInternal — bypass fallback leaf that succeeds when the exploit is not intended for publication; exists purely so the BT succeeds gracefully on the no-op path; no external input, output, or monitoring seam. Analogous to `NoThreatsFound`.
- **Factory-fn placement**: Eliminated (Production Collapse 2, issue #1310) —
  replaced by the positively-named `ShouldPublishExploit` gate node
  (reads `PublicationIntentDecision.publish_exploit`) plus the exploit arm's
  `Inverter(ShouldPublishExploit)` skip branch, which provides the graceful
  no-op this leaf used to. Not a call-out point.

### `ExploitReady`

- **Node name**: `ExploitReady`
- **btz type**: `OftenSucceed` (p=0.70)
- **Source file**: `report_management/fuzzer/publication.py`
- **Parent tree**: `Publication`
- **Semantic function**: Condition — check whether the exploit artifact is
  ready for publication (prepared, reviewed, and staged)
- **Input dependency**: Artifact status metadata; staging system check
- **Notes**: Ready more often than not once preparation has started
- **Automation potential**: **High** — artifact staging-status check in the publishing pipeline; fully automatable.
- **New-arch cross-ref**: `vultron.demo.fuzzer.report_management.publication.ExploitReady`
- **Call-out point shape**: ProtocolInternal — reads a staging-readiness flag written by
  `PrepareExploit` during the same BT execution cycle; the flag lives on the local DataLayer /
  BT blackboard. No external agent seam — the flag is local and actor-scoped.
  (Category 3 per issue #1199 triage — reads a flag written by the protocol's own BT execution.)
- **Factory-fn placement**: Eliminated (Production Collapse 2, issue #1310) —
  the lean per-artifact arm is `ShouldPublishExploit → PrepareExploit →
  Publish` with no separate staging-readiness early-exit. Not a call-out point.

### `PrepareExploit`

- **Node name**: `PrepareExploit`
- **btz type**: `AlmostAlwaysSucceed` (p=0.90)
- **Source file**: `report_management/fuzzer/publication.py`
- **Parent tree**: `Publication`
- **Semantic function**: Action — create, document, and stage the exploit
  artifact for publication (write-up, code packaging, filing in publishing
  system)
- **Input dependency**: Human security researcher; content authoring and
  artifact staging workflow
- **Notes**: Succeeds almost always in simulation
- **Automation potential**: **Low** — write-up and proof-of-concept packaging require human security researcher expertise; not automatable in the general case.
- **New-arch cross-ref**: `vultron.demo.fuzzer.report_management.publication.PrepareExploit`
- **Call-out point shape**: Composer
- **Factory-fn placement**: Implemented (Production Collapse 2, issue #1310) —
  `vultron.core.behaviors.report.publication_tree.create_publication_tree`
  (`prepare_exploit_factory` param) — Composer node in the exploit arm's
  `Do…` Sequence, between `ShouldPublishExploit` and `Publish`

### `ReprioritizeExploit`

- **Node name**: `ReprioritizeExploit`
- **btz type**: `AlwaysSucceed` (p=1.00)
- **Source file**: `report_management/fuzzer/publication.py`
- **Parent tree**: `Publication`
- **Semantic function**: Action — update the priority of the exploit artifact
  in the publication queue (e.g., in response to a changing threat
  landscape or embargo state change)
- **Input dependency**: Human analyst or automated policy trigger; priority
  queue management
- **Notes**: Always succeeds in simulation
- **Automation potential**: **Medium** — embargo state changes and threat-level updates can trigger automated reprioritization rules; human override may be needed for unusual cases.
- **New-arch cross-ref**: `vultron.demo.fuzzer.report_management.publication.ReprioritizeExploit`
- **Call-out point shape**: Evaluator
- **Factory-fn placement**: Eliminated (Production Collapse 2, issue #1310) —
  the single `PrioritizePublicationIntents` Evaluator now carries all
  publish/withhold intent in its `PublicationIntentDecision` record; per-arm
  reprioritization is not a separate call-out point in the lean shape.

### `NoPublishFix`

- **Node name**: `NoPublishFix`
- **btz type**: `AlmostAlwaysFail` (p=0.10)
- **Source file**: `report_management/fuzzer/publication.py`
- **Parent tree**: `Publication`
- **Semantic function**: Condition — check the publication intent flag for
  the fix artifact; `SUCCESS` means "do not publish fix"
- **Input dependency**: Publication intent record; case policy
- **Notes**: Fails most of the time because fix publication is the standard
  expected outcome of CVD
- **Automation potential**: **TerminalPlaceholder** — BT bypass fallback leaf; no decision logic required.
- **New-arch cross-ref**: `vultron.demo.fuzzer.report_management.publication.NoPublishFix`
- **Call-out point shape**: ProtocolInternal — bypass fallback leaf that succeeds when the fix is not intended for publication; exists purely so the BT succeeds gracefully on the no-op path; no external input, output, or monitoring seam. Analogous to `NoThreatsFound`.
- **Factory-fn placement**: Eliminated (Production Collapse 2, issue #1310) —
  replaced by the positively-named `ShouldPublishFix` gate node
  (reads `PublicationIntentDecision.publish_fix`) plus the fix arm's
  `Inverter(ShouldPublishFix)` skip branch, which provides the graceful
  no-op this leaf used to. Not a call-out point.

### `PrepareFix`

- **Node name**: `PrepareFix`
- **btz type**: `AlmostAlwaysSucceed` (p=0.90)
- **Source file**: `report_management/fuzzer/publication.py`
- **Parent tree**: `Publication`
- **Semantic function**: Action — create, document, and stage the fix
  artifact for publication (patch notes, release artifacts, advisory text)
- **Input dependency**: Engineering team output; patch release pipeline
  and content authoring workflow
- **Notes**: Succeeds almost always in simulation
- **Automation potential**: **Low–Medium** — CI/CD pipeline can automate patch build and packaging; advisory text and release notes typically require human authoring and review.
- **New-arch cross-ref**: `vultron.demo.fuzzer.report_management.publication.PrepareFix`
- **Call-out point shape**: Composer
- **Factory-fn placement**: Implemented (Production Collapse 2, issue #1310) —
  `vultron.core.behaviors.report.publication_tree.create_publication_tree`
  (`prepare_fix_factory` param) — Composer node in the fix arm's `Do…`
  Sequence, between `ShouldPublishFix` and `Publish`

### `ReprioritizeFix`

- **Node name**: `ReprioritizeFix`
- **btz type**: `AlwaysSucceed` (p=1.00)
- **Source file**: `report_management/fuzzer/publication.py`
- **Parent tree**: `Publication`
- **Semantic function**: Action — update the priority of the fix artifact
  in the publication queue
- **Input dependency**: Human analyst or automated policy trigger; priority
  queue management
- **Notes**: Always succeeds in simulation
- **Automation potential**: **Medium** — embargo state changes and threat-level updates can trigger automated reprioritization rules; human override may be needed.
- **New-arch cross-ref**: `vultron.demo.fuzzer.report_management.publication.ReprioritizeFix`
- **Call-out point shape**: Evaluator
- **Factory-fn placement**: Eliminated (Production Collapse 2, issue #1310) —
  the single `PrioritizePublicationIntents` Evaluator now carries all
  publish/withhold intent in its `PublicationIntentDecision` record; per-arm
  reprioritization is not a separate call-out point in the lean shape.

### `NoPublishReport`

- **Node name**: `NoPublishReport`
- **btz type**: `AlmostAlwaysFail` (p=0.10)
- **Source file**: `report_management/fuzzer/publication.py`
- **Parent tree**: `Publication`
- **Semantic function**: Condition — check the publication intent flag for
  the vulnerability report artifact; `SUCCESS` means "do not publish
  report"
- **Input dependency**: Publication intent record; case policy
- **Notes**: Fails most of the time because report publication is standard
  CVD outcome
- **Automation potential**: **TerminalPlaceholder** — BT bypass fallback leaf; no decision logic required.
- **New-arch cross-ref**: `vultron.demo.fuzzer.report_management.publication.NoPublishReport`
- **Call-out point shape**: ProtocolInternal — bypass fallback leaf that succeeds when the vulnerability report is not intended for publication; exists purely so the BT succeeds gracefully on the no-op path; no external input, output, or monitoring seam. Analogous to `NoThreatsFound`.
- **Factory-fn placement**: Eliminated (Production Collapse 2, issue #1310) —
  replaced by the positively-named `ShouldPublishReport` gate node
  (reads `PublicationIntentDecision.publish_report`) plus the report arm's
  `Inverter(ShouldPublishReport)` skip branch, which provides the graceful
  no-op this leaf used to. Not a call-out point.

### `PrepareReport`

- **Node name**: `PrepareReport`
- **btz type**: `AlmostAlwaysSucceed` (p=0.90)
- **Source file**: `report_management/fuzzer/publication.py`
- **Parent tree**: `Publication`
- **Semantic function**: Action — create, review, and stage the vulnerability
  advisory or report artifact for publication
- **Input dependency**: Human analyst; content authoring, review, and
  approval workflow; advisory publishing pipeline
- **Notes**: Succeeds almost always in simulation
- **Automation potential**: **Low** — advisory writing requires human expertise and editorial judgment; review and approval workflow also typically involves human stakeholders.
- **New-arch cross-ref**: `vultron.demo.fuzzer.report_management.publication.PrepareReport`
- **Call-out point shape**: Composer
- **Factory-fn placement**: Implemented (Production Collapse 2, issue #1310) —
  `vultron.core.behaviors.report.publication_tree.create_publication_tree`
  (`prepare_report_factory` param) — Composer node in the report arm's `Do…`
  Sequence, between `ShouldPublishReport` and `Publish`

### `ReprioritizeReport`

- **Node name**: `ReprioritizeReport`
- **btz type**: `AlwaysSucceed` (p=1.00)
- **Source file**: `report_management/fuzzer/publication.py`
- **Parent tree**: `Publication`
- **Semantic function**: Action — update the priority of the report artifact
  in the publication queue
- **Input dependency**: Human analyst or automated policy trigger; priority
  queue management
- **Notes**: Always succeeds in simulation
- **Automation potential**: **Medium** — policy-triggered reprioritization (e.g., on embargo exit or threat escalation) is automatable; complex editorial decisions require human oversight.
- **New-arch cross-ref**: `vultron.demo.fuzzer.report_management.publication.ReprioritizeReport`
- **Call-out point shape**: Evaluator
- **Factory-fn placement**: Eliminated (Production Collapse 2, issue #1310) —
  the single `PrioritizePublicationIntents` Evaluator now carries all
  publish/withhold intent in its `PublicationIntentDecision` record; per-arm
  reprioritization is not a separate call-out point in the lean shape.

---
