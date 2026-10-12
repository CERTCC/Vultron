---
stakeholder_type: [project-contributor]
---

# Publication fuzzer nodes

These stub nodes belong to the `Publication` fallback tree (`vultron/bt/report_management/_behaviors/publication.py`), which models deciding which artifacts to publish, preparing them, and publishing them.

In production, `create_publication_tree` (`vultron/core/behaviors/report/publication_tree.py`) collapses the simulator's flag checks and bypass leaves into one intent Evaluator and three per-artifact arms (ADR-0028, BT-20-002).

See the [fuzzer node index](index.md) for the entry format, the automation-potential and call-out shape values, and the base-type probabilities.

## `AllPublished`

- **Node name**: `AllPublished`
- **btz type**: `AlmostAlwaysFail` (p=0.10)
- **Source file**: `report_management/fuzzer/publication.py`
- **Parent tree**: `Publication`
- **Semantic function**: Condition — check whether all intended publication artifacts (report, fix, exploit) have been published
- **Input dependency**: Case/publication status metadata query; automatable against a publication tracking field
- **Notes**: Fails most of the time in simulation because publication is an active goal being worked toward
- **Automation potential**: **High** — publication status flag on the case record; fully automatable as a metadata check.
- **New-arch cross-ref**: `vultron.demo.fuzzer.report_management.publication.AllPublished`
- **Call-out point shape**: ProtocolInternal — reads a publication-completion flag maintained in the local DataLayer / BT blackboard by the protocol's own BT execution (written by `Publish` nodes).
  No external agent seam — the flag is local and actor-scoped.
- **Factory-fn placement**: Not placed: `create_publication_tree` has no top-level early exit once all artifacts are published; adding one would wrap the `PublicationBT` Sequence in a `Selector(AllPublished, …)`.

## `PublicationIntentsSet`

- **Node name**: `PublicationIntentsSet`
- **btz type**: `UsuallyFail` (p=0.25)
- **Source file**: `report_management/fuzzer/publication.py`
- **Parent tree**: `Publication`
- **Semantic function**: Condition — check whether publication intentions (what to publish, when, and in what format) have been established for this case
- **Input dependency**: Case metadata check; publication plan document or structured publication intent flags
- **Notes**: Fails most of the time in simulation because setting intents is an early workflow step being modeled
- **Automation potential**: **High** — publication intent flags on the case record; fully automatable as a metadata check.
- **New-arch cross-ref**: `vultron.demo.fuzzer.report_management.publication.PublicationIntentsSet`
- **Call-out point shape**: ProtocolInternal — reads a flag written by `PrioritizePublicationIntents` during the same BT execution cycle; the flag lives on the local DataLayer / BT blackboard.
  No external agent seam — the flag is local and actor-scoped.
- **Factory-fn placement**: Eliminated in production: the BT reads the `PublicationIntentDecision` record directly through `ShouldPublishX` gate nodes (ADR-0028).

## `PrioritizePublicationIntents`

- **Node name**: `PrioritizePublicationIntents`
- **btz type**: `AlwaysSucceed` (p=1.00)
- **Source file**: `report_management/fuzzer/publication.py`
- **Parent tree**: `Publication`
- **Semantic function**: Action — establish and record publication intentions: what artifacts to publish, their priority order, timing, and format
- **Input dependency**: Human analyst decision, publication policy, or automated policy engine; may depend on case context (embargo status, fix availability, threat level)
- **Notes**: Always succeeds in simulation; in production this involves structured editorial/policy decisions
- **Automation potential**: **Medium** — standard policy-driven publication priorities (e.g., always publish report and fix) can be automated; editorial or legal exceptions require human judgment.
- **New-arch cross-ref**: `vultron.demo.fuzzer.report_management.publication.PrioritizePublicationIntents`
- **Call-out point shape**: Evaluator
- **Factory-fn placement**: `vultron.core.behaviors.report.publication_tree.create_publication_tree` (`prioritize_publication_intents_factory` param) — runs first and writes the `PublicationIntentDecision` record that gates the three per-artifact arms (BT-20-002)

## `Publish`

- **Node name**: `Publish`
- **btz type**: `AlmostAlwaysSucceed` (p=0.90)
- **Source file**: `report_management/fuzzer/publication.py`
- **Parent tree**: `Publication`
- **Semantic function**: Action — execute the publication of a prepared artifact to the intended audience (advisory, patch, bulletin, etc.)
- **Input dependency**: Publication platform API (CMS, advisory database, package repository, NVD/CVE submission); could be fully automated
- **Notes**: Succeeds almost always in simulation; in production may involve API calls to advisory publishing platforms
- **Automation potential**: **High** — advisory platform APIs (NVD, CVE.org, CMS, package repository) enable fully automated artifact publication.
- **New-arch cross-ref**: `vultron.demo.fuzzer.report_management.publication.Publish`
- **Call-out point shape**: Actuator — submits an already-prepared artifact to an external advisory platform (NVD, CVE.org, CMS, package repository, or equivalent) via an API call; the side effect is the externally visible published entry at the target platform.
  There is no new content artifact placed on the blackboard; the preceding Prepare* nodes produce the content.
- **Factory-fn placement**: Replaced in production by the draft-review-submit pipeline `vultron.core.behaviors.report.publish_artifact_tree.create_publish_artifact_tree`, which `create_publication_tree` builds once per artifact arm after its Prepare* Composer (ADR-0030, BT-20-004).

## `NoPublishExploit`

- **Node name**: `NoPublishExploit`
- **btz type**: `UsuallySucceed` (p=0.75)
- **Source file**: `report_management/fuzzer/publication.py`
- **Parent tree**: `Publication`
- **Semantic function**: Condition — check the publication intent flag for the exploit artifact; `SUCCESS` means "do not publish exploit"
- **Input dependency**: Publication intent record set by `PrioritizePublicationIntents`; case policy
- **Notes**: Succeeds (no exploit publication) in most cases, reflecting that exploit publication is not always required or desired
- **Automation potential**: **TerminalPlaceholder** — BT bypass fallback leaf; no decision logic required.
- **New-arch cross-ref**: `vultron.demo.fuzzer.report_management.publication.NoPublishExploit`
- **Call-out point shape**: ProtocolInternal — bypass fallback leaf that succeeds when the exploit is not intended for publication; exists purely so the BT succeeds gracefully on the no-op path; no external input, output, or monitoring seam.
  Analogous to `NoThreatsFound`.
- **Factory-fn placement**: Eliminated in production: the positively named `ShouldPublishExploit` gate and the arm's `Inverter(ShouldPublishExploit)` skip branch replace it (ADR-0028).

## `ExploitReady`

- **Node name**: `ExploitReady`
- **btz type**: `OftenSucceed` (p=0.70)
- **Source file**: `report_management/fuzzer/publication.py`
- **Parent tree**: `Publication`
- **Semantic function**: Condition — check whether the exploit artifact is ready for publication (prepared, reviewed, and staged)
- **Input dependency**: Artifact status metadata; staging system check
- **Notes**: Ready more often than not once preparation has started
- **Automation potential**: **High** — artifact staging-status check in the publishing pipeline; fully automatable.
- **New-arch cross-ref**: `vultron.demo.fuzzer.report_management.publication.ExploitReady`
- **Call-out point shape**: ProtocolInternal — reads a staging-readiness flag written by `PrepareExploit` during the same BT execution cycle; the flag lives on the local DataLayer / BT blackboard.
  No external agent seam — the flag is local and actor-scoped.
- **Factory-fn placement**: Eliminated in production: the exploit arm is `ShouldPublishExploit → PrepareExploit → publish pipeline`, with no separate staging-readiness check (ADR-0028).

## `PrepareExploit`

- **Node name**: `PrepareExploit`
- **btz type**: `AlmostAlwaysSucceed` (p=0.90)
- **Source file**: `report_management/fuzzer/publication.py`
- **Parent tree**: `Publication`
- **Semantic function**: Action — create, document, and stage the exploit artifact for publication (write-up, code packaging, filing in publishing system)
- **Input dependency**: Human security researcher; content authoring and artifact staging workflow
- **Notes**: Succeeds almost always in simulation
- **Automation potential**: **Low** — write-up and proof-of-concept packaging require human security researcher expertise; not automatable in the general case.
- **New-arch cross-ref**: `vultron.demo.fuzzer.report_management.publication.PrepareExploit`
- **Call-out point shape**: Composer
- **Factory-fn placement**: `vultron.core.behaviors.report.publication_tree.create_publication_tree` (`prepare_exploit_factory` param) — Composer in the exploit arm, between `ShouldPublishExploit` and the publish pipeline

## `ReprioritizeExploit`

- **Node name**: `ReprioritizeExploit`
- **btz type**: `AlwaysSucceed` (p=1.00)
- **Source file**: `report_management/fuzzer/publication.py`
- **Parent tree**: `Publication`
- **Semantic function**: Action — update the priority of the exploit artifact in the publication queue (e.g., in response to a changing threat landscape or embargo state change)
- **Input dependency**: Human analyst or automated policy trigger; priority queue management
- **Notes**: Always succeeds in simulation
- **Automation potential**: **Medium** — embargo state changes and threat-level updates can trigger automated reprioritization rules; human override may be needed for unusual cases.
- **New-arch cross-ref**: `vultron.demo.fuzzer.report_management.publication.ReprioritizeExploit`
- **Call-out point shape**: Evaluator
- **Factory-fn placement**: Eliminated in production: `PrioritizePublicationIntents` carries all publish or withhold intent (ADR-0028).

## `NoPublishFix`

- **Node name**: `NoPublishFix`
- **btz type**: `AlmostAlwaysFail` (p=0.10)
- **Source file**: `report_management/fuzzer/publication.py`
- **Parent tree**: `Publication`
- **Semantic function**: Condition — check the publication intent flag for the fix artifact; `SUCCESS` means "do not publish fix"
- **Input dependency**: Publication intent record; case policy
- **Notes**: Fails most of the time because fix publication is the standard expected outcome of CVD
- **Automation potential**: **TerminalPlaceholder** — BT bypass fallback leaf; no decision logic required.
- **New-arch cross-ref**: `vultron.demo.fuzzer.report_management.publication.NoPublishFix`
- **Call-out point shape**: ProtocolInternal — bypass fallback leaf that succeeds when the fix is not intended for publication; exists purely so the BT succeeds gracefully on the no-op path; no external input, output, or monitoring seam.
  Analogous to `NoThreatsFound`.
- **Factory-fn placement**: Eliminated in production: the positively named `ShouldPublishFix` gate and the arm's `Inverter(ShouldPublishFix)` skip branch replace it (ADR-0028).

## `PrepareFix`

- **Node name**: `PrepareFix`
- **btz type**: `AlmostAlwaysSucceed` (p=0.90)
- **Source file**: `report_management/fuzzer/publication.py`
- **Parent tree**: `Publication`
- **Semantic function**: Action — create, document, and stage the fix artifact for publication (patch notes, release artifacts, advisory text)
- **Input dependency**: Engineering team output; patch release pipeline and content authoring workflow
- **Notes**: Succeeds almost always in simulation
- **Automation potential**: **Low–Medium** — CI/CD pipeline can automate patch build and packaging; advisory text and release notes typically require human authoring and review.
- **New-arch cross-ref**: `vultron.demo.fuzzer.report_management.publication.PrepareFix`
- **Call-out point shape**: Composer
- **Factory-fn placement**: `vultron.core.behaviors.report.publication_tree.create_publication_tree` (`prepare_fix_factory` param) — Composer in the fix arm, between `ShouldPublishFix` and the publish pipeline

## `ReprioritizeFix`

- **Node name**: `ReprioritizeFix`
- **btz type**: `AlwaysSucceed` (p=1.00)
- **Source file**: `report_management/fuzzer/publication.py`
- **Parent tree**: `Publication`
- **Semantic function**: Action — update the priority of the fix artifact in the publication queue
- **Input dependency**: Human analyst or automated policy trigger; priority queue management
- **Notes**: Always succeeds in simulation
- **Automation potential**: **Medium** — embargo state changes and threat-level updates can trigger automated reprioritization rules; human override may be needed.
- **New-arch cross-ref**: `vultron.demo.fuzzer.report_management.publication.ReprioritizeFix`
- **Call-out point shape**: Evaluator
- **Factory-fn placement**: Eliminated in production: `PrioritizePublicationIntents` carries all publish or withhold intent (ADR-0028).

## `NoPublishReport`

- **Node name**: `NoPublishReport`
- **btz type**: `AlmostAlwaysFail` (p=0.10)
- **Source file**: `report_management/fuzzer/publication.py`
- **Parent tree**: `Publication`
- **Semantic function**: Condition — check the publication intent flag for the vulnerability report artifact; `SUCCESS` means "do not publish report"
- **Input dependency**: Publication intent record; case policy
- **Notes**: Fails most of the time because report publication is standard CVD outcome
- **Automation potential**: **TerminalPlaceholder** — BT bypass fallback leaf; no decision logic required.
- **New-arch cross-ref**: `vultron.demo.fuzzer.report_management.publication.NoPublishReport`
- **Call-out point shape**: ProtocolInternal — bypass fallback leaf that succeeds when the vulnerability report is not intended for publication; exists purely so the BT succeeds gracefully on the no-op path; no external input, output, or monitoring seam.
  Analogous to `NoThreatsFound`.
- **Factory-fn placement**: Eliminated in production: the positively named `ShouldPublishReport` gate and the arm's `Inverter(ShouldPublishReport)` skip branch replace it (ADR-0028).

## `PrepareReport`

- **Node name**: `PrepareReport`
- **btz type**: `AlmostAlwaysSucceed` (p=0.90)
- **Source file**: `report_management/fuzzer/publication.py`
- **Parent tree**: `Publication`
- **Semantic function**: Action — create, review, and stage the vulnerability advisory or report artifact for publication
- **Input dependency**: Human analyst; content authoring, review, and approval workflow; advisory publishing pipeline
- **Notes**: Succeeds almost always in simulation
- **Automation potential**: **Low** — advisory writing requires human expertise and editorial judgment; review and approval workflow also typically involves human stakeholders.
- **New-arch cross-ref**: `vultron.demo.fuzzer.report_management.publication.PrepareReport`
- **Call-out point shape**: Composer
- **Factory-fn placement**: `vultron.core.behaviors.report.publication_tree.create_publication_tree` (`prepare_report_factory` param) — Composer in the report arm, between `ShouldPublishReport` and the publish pipeline

## `ReprioritizeReport`

- **Node name**: `ReprioritizeReport`
- **btz type**: `AlwaysSucceed` (p=1.00)
- **Source file**: `report_management/fuzzer/publication.py`
- **Parent tree**: `Publication`
- **Semantic function**: Action — update the priority of the report artifact in the publication queue
- **Input dependency**: Human analyst or automated policy trigger; priority queue management
- **Notes**: Always succeeds in simulation
- **Automation potential**: **Medium** — policy-triggered reprioritization (e.g., on embargo exit or threat escalation) is automatable; complex editorial decisions require human oversight.
- **New-arch cross-ref**: `vultron.demo.fuzzer.report_management.publication.ReprioritizeReport`
- **Call-out point shape**: Evaluator
- **Factory-fn placement**: Eliminated in production: `PrioritizePublicationIntents` carries all publish or withhold intent (ADR-0028).
