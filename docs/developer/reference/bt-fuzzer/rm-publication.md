---
stakeholder_type: [project-contributor]
---

# Publication fuzzer nodes

These stub nodes belong to the `Publication` fallback tree (`vultron/bt/report_management/_behaviors/publication.py`).
This tree models how a participant decides which artifacts to publish, prepares them, and publishes them.

The production tree is `create_publication_tree` (`vultron/core/behaviors/report/publication_tree.py`).
It replaces the flag checks and bypass leaves of the simulator with one intent Evaluator and three per-artifact arms (ADR-0028, BT-20-002).

See the [fuzzer node index](index.md) for the entry format, the automation-potential and call-out shape values, and the base-type probabilities.

## `AllPublished`

- **Node name**: `AllPublished`
- **btz type**: `AlmostAlwaysFail` (p=0.10)
- **Source file**: `report_management/fuzzer/publication.py`
- **Parent tree**: `Publication`
- **Semantic function**: Condition — check whether the participant has published all intended publication artifacts (report, fix, exploit)
- **Input dependency**: Case/publication status metadata query.
  A check against a publication tracking field can automate it
- **Notes**: Fails most of the time in simulation because publication is an active goal that is not yet complete
- **Automation potential**: **High** — a publication status flag on the case record.
  A metadata check can fully automate it.
- **New-arch cross-ref**: `vultron.demo.fuzzer.report_management.publication.AllPublished`
- **Call-out point shape**: ProtocolInternal — reads a publication-completion flag in the local DataLayer / behavior tree (BT) blackboard.
  The BT execution of the protocol keeps this flag, and the `Publish` nodes write it.
  No external agent seam: the flag is local and actor-scoped.
- **Factory-fn placement**: Not placed: `create_publication_tree` has no top-level early exit for the case where all artifacts are published.
  An early exit would wrap the `PublicationBT` Sequence in a `Selector(AllPublished, …)`.

## `PublicationIntentsSet`

- **Node name**: `PublicationIntentsSet`
- **btz type**: `UsuallyFail` (p=0.25)
- **Source file**: `report_management/fuzzer/publication.py`
- **Parent tree**: `Publication`
- **Semantic function**: Condition — check whether this case has publication intentions: what to publish, when, and in what format
- **Input dependency**: Case metadata check.
  The source is a publication plan document or structured publication intent flags
- **Notes**: Fails most of the time in simulation because the simulation models the early workflow step that sets the intents
- **Automation potential**: **High** — publication intent flags on the case record.
  A metadata check can fully automate it.
- **New-arch cross-ref**: `vultron.demo.fuzzer.report_management.publication.PublicationIntentsSet`
- **Call-out point shape**: ProtocolInternal — reads a flag that `PrioritizePublicationIntents` writes during the same BT execution cycle.
  The flag is on the local DataLayer / BT blackboard.
  No external agent seam: the flag is local and actor-scoped.
- **Factory-fn placement**: Eliminated in production: the BT reads the `PublicationIntentDecision` record directly through `ShouldPublishX` gate nodes (ADR-0028).

## `PrioritizePublicationIntents`

- **Node name**: `PrioritizePublicationIntents`
- **btz type**: `AlwaysSucceed` (p=1.00)
- **Source file**: `report_management/fuzzer/publication.py`
- **Parent tree**: `Publication`
- **Semantic function**: Action — establish and record publication intentions: what artifacts to publish, their priority order, timing, and format
- **Input dependency**: Human analyst decision, publication policy, or automated policy engine.
  The input can depend on case context (embargo status, fix availability, threat level)
- **Notes**: Always succeeds in simulation.
  In production, this node makes structured editorial and policy decisions
- **Automation potential**: **Medium** — automation can apply standard policy-driven publication priorities, such as "always publish the report and the fix".
  Editorial or legal exceptions need human judgment.
- **New-arch cross-ref**: `vultron.demo.fuzzer.report_management.publication.PrioritizePublicationIntents`
- **Call-out point shape**: Evaluator
- **Factory-fn placement**: `vultron.core.behaviors.report.publication_tree.create_publication_tree` (`prioritize_publication_intents_factory` param) — runs first.
  It writes the `PublicationIntentDecision` record that gates the three per-artifact arms (BT-20-002)

## `Publish`

- **Node name**: `Publish`
- **btz type**: `AlmostAlwaysSucceed` (p=0.90)
- **Source file**: `report_management/fuzzer/publication.py`
- **Parent tree**: `Publication`
- **Semantic function**: Action — publish a prepared artifact, such as an advisory, patch, or bulletin, to the intended audience
- **Input dependency**: Publication platform application programming interface (API).
  Examples are a content management system (CMS), an advisory database, a package repository, or a National Vulnerability Database (NVD) / Common Vulnerabilities and Exposures (CVE) submission.
  Full automation is possible
- **Notes**: Succeeds almost always in simulation.
  In production, the node can make API calls to advisory publishing platforms
- **Automation potential**: **High** — advisory platform APIs (NVD, CVE.org, CMS, package repository) enable fully automated artifact publication.
- **New-arch cross-ref**: `vultron.demo.fuzzer.report_management.publication.Publish`
- **Call-out point shape**: Actuator — sends an already-prepared artifact to an external advisory platform (NVD, CVE.org, CMS, package repository, or equivalent) through an API call.
  The side effect is the externally visible published entry at the target platform.
  The node puts no new content artifact on the blackboard.
  The Prepare* nodes before it make the content.
- **Factory-fn placement**: In production, the draft-review-submit pipeline `vultron.core.behaviors.report.publish_artifact_tree.create_publish_artifact_tree` replaces this node.
  `create_publication_tree` builds this pipeline once per artifact arm, after the Prepare* Composer of the arm (ADR-0030, BT-20-004).

## `NoPublishExploit`

- **Node name**: `NoPublishExploit`
- **btz type**: `UsuallySucceed` (p=0.75)
- **Source file**: `report_management/fuzzer/publication.py`
- **Parent tree**: `Publication`
- **Semantic function**: Condition — check the publication intent flag for the exploit artifact.
  `SUCCESS` means "do not publish exploit"
- **Input dependency**: Publication intent record that `PrioritizePublicationIntents` sets.
  Case policy
- **Notes**: Succeeds (no exploit publication) in most cases.
  This result shows that exploit publication is not always necessary or wanted
- **Automation potential**: **TerminalPlaceholder** — BT bypass fallback leaf.
  The node needs no decision logic.
- **New-arch cross-ref**: `vultron.demo.fuzzer.report_management.publication.NoPublishExploit`
- **Call-out point shape**: ProtocolInternal — bypass fallback leaf that succeeds when the exploit is not intended for publication.
  It exists only so that the BT succeeds gracefully on the no-op path.
  It has no external input, output, or monitoring seam.
  Analogous to `NoThreatsFound`.
- **Factory-fn placement**: Eliminated in production: the positively named `ShouldPublishExploit` gate and the arm's `Inverter(ShouldPublishExploit)` skip branch replace it (ADR-0028).

## `ExploitReady`

- **Node name**: `ExploitReady`
- **btz type**: `OftenSucceed` (p=0.70)
- **Source file**: `report_management/fuzzer/publication.py`
- **Parent tree**: `Publication`
- **Semantic function**: Condition — check whether the exploit artifact is ready for publication: prepared, reviewed, and staged
- **Input dependency**: Artifact status metadata and a staging system check
- **Notes**: Ready more often than not after preparation starts
- **Automation potential**: **High** — artifact staging-status check in the publishing pipeline.
  Full automation is possible.
- **New-arch cross-ref**: `vultron.demo.fuzzer.report_management.publication.ExploitReady`
- **Call-out point shape**: ProtocolInternal — reads a staging-readiness flag that `PrepareExploit` writes during the same BT execution cycle.
  The flag is on the local DataLayer / BT blackboard.
  No external agent seam: the flag is local and actor-scoped.
- **Factory-fn placement**: Eliminated in production: the exploit arm is `ShouldPublishExploit → PrepareExploit → publish pipeline`, with no separate staging-readiness check (ADR-0028).

## `PrepareExploit`

- **Node name**: `PrepareExploit`
- **btz type**: `AlmostAlwaysSucceed` (p=0.90)
- **Source file**: `report_management/fuzzer/publication.py`
- **Parent tree**: `Publication`
- **Semantic function**: Action — create, document, and stage the exploit artifact for publication: write-up, code packaging, and filing in the publishing system
- **Input dependency**: Human security researcher.
  Content authoring and artifact staging workflow
- **Notes**: Succeeds almost always in simulation
- **Automation potential**: **Low** — the write-up and proof-of-concept packaging need the expertise of a human security researcher.
  Automation is not possible in the general case.
- **New-arch cross-ref**: `vultron.demo.fuzzer.report_management.publication.PrepareExploit`
- **Call-out point shape**: Composer
- **Factory-fn placement**: `vultron.core.behaviors.report.publication_tree.create_publication_tree` (`prepare_exploit_factory` param) — Composer in the exploit arm, between `ShouldPublishExploit` and the publish pipeline

## `ReprioritizeExploit`

- **Node name**: `ReprioritizeExploit`
- **btz type**: `AlwaysSucceed` (p=1.00)
- **Source file**: `report_management/fuzzer/publication.py`
- **Parent tree**: `Publication`
- **Semantic function**: Action — update the priority of the exploit artifact in the publication queue.
  Causes include a change in the threat landscape or a change in the embargo state
- **Input dependency**: Human analyst or automated policy trigger.
  Priority queue management
- **Notes**: Always succeeds in simulation
- **Automation potential**: **Medium** — embargo state changes and threat-level updates can trigger automated reprioritization rules.
  Unusual cases can need a human override.
- **New-arch cross-ref**: `vultron.demo.fuzzer.report_management.publication.ReprioritizeExploit`
- **Call-out point shape**: Evaluator
- **Factory-fn placement**: Eliminated in production: `PrioritizePublicationIntents` carries all publish or withhold intent (ADR-0028).

## `NoPublishFix`

- **Node name**: `NoPublishFix`
- **btz type**: `AlmostAlwaysFail` (p=0.10)
- **Source file**: `report_management/fuzzer/publication.py`
- **Parent tree**: `Publication`
- **Semantic function**: Condition — check the publication intent flag for the fix artifact.
  `SUCCESS` means "do not publish fix"
- **Input dependency**: Publication intent record and case policy
- **Notes**: Fails most of the time because fix publication is the standard, expected outcome of Coordinated Vulnerability Disclosure (CVD)
- **Automation potential**: **TerminalPlaceholder** — BT bypass fallback leaf.
  The node needs no decision logic.
- **New-arch cross-ref**: `vultron.demo.fuzzer.report_management.publication.NoPublishFix`
- **Call-out point shape**: ProtocolInternal — bypass fallback leaf that succeeds when the fix is not intended for publication.
  It exists only so that the BT succeeds gracefully on the no-op path.
  It has no external input, output, or monitoring seam.
  Analogous to `NoThreatsFound`.
- **Factory-fn placement**: Eliminated in production: the positively named `ShouldPublishFix` gate and the arm's `Inverter(ShouldPublishFix)` skip branch replace it (ADR-0028).

## `PrepareFix`

- **Node name**: `PrepareFix`
- **btz type**: `AlmostAlwaysSucceed` (p=0.90)
- **Source file**: `report_management/fuzzer/publication.py`
- **Parent tree**: `Publication`
- **Semantic function**: Action — create, document, and stage the fix artifact for publication: patch notes, release artifacts, and advisory text
- **Input dependency**: Engineering team output.
  Patch release pipeline and content authoring workflow
- **Notes**: Succeeds almost always in simulation
- **Automation potential**: **Medium** — a build and release pipeline can automate patch build and packaging.
  Advisory text and release notes usually need human authoring and review.
- **New-arch cross-ref**: `vultron.demo.fuzzer.report_management.publication.PrepareFix`
- **Call-out point shape**: Composer
- **Factory-fn placement**: `vultron.core.behaviors.report.publication_tree.create_publication_tree` (`prepare_fix_factory` param) — Composer in the fix arm, between `ShouldPublishFix` and the publish pipeline

## `ReprioritizeFix`

- **Node name**: `ReprioritizeFix`
- **btz type**: `AlwaysSucceed` (p=1.00)
- **Source file**: `report_management/fuzzer/publication.py`
- **Parent tree**: `Publication`
- **Semantic function**: Action — update the priority of the fix artifact in the publication queue
- **Input dependency**: Human analyst or automated policy trigger.
  Priority queue management
- **Notes**: Always succeeds in simulation
- **Automation potential**: **Medium** — embargo state changes and threat-level updates can trigger automated reprioritization rules.
  A human override can be necessary.
- **New-arch cross-ref**: `vultron.demo.fuzzer.report_management.publication.ReprioritizeFix`
- **Call-out point shape**: Evaluator
- **Factory-fn placement**: Eliminated in production: `PrioritizePublicationIntents` carries all publish or withhold intent (ADR-0028).

## `NoPublishReport`

- **Node name**: `NoPublishReport`
- **btz type**: `AlmostAlwaysFail` (p=0.10)
- **Source file**: `report_management/fuzzer/publication.py`
- **Parent tree**: `Publication`
- **Semantic function**: Condition — check the publication intent flag for the vulnerability report artifact.
  `SUCCESS` means "do not publish report"
- **Input dependency**: Publication intent record and case policy
- **Notes**: Fails most of the time because report publication is the standard CVD outcome
- **Automation potential**: **TerminalPlaceholder** — BT bypass fallback leaf.
  The node needs no decision logic.
- **New-arch cross-ref**: `vultron.demo.fuzzer.report_management.publication.NoPublishReport`
- **Call-out point shape**: ProtocolInternal — bypass fallback leaf that succeeds when the vulnerability report is not intended for publication.
  It exists only so that the BT succeeds gracefully on the no-op path.
  It has no external input, output, or monitoring seam.
  Analogous to `NoThreatsFound`.
- **Factory-fn placement**: Eliminated in production: the positively named `ShouldPublishReport` gate and the arm's `Inverter(ShouldPublishReport)` skip branch replace it (ADR-0028).

## `PrepareReport`

- **Node name**: `PrepareReport`
- **btz type**: `AlmostAlwaysSucceed` (p=0.90)
- **Source file**: `report_management/fuzzer/publication.py`
- **Parent tree**: `Publication`
- **Semantic function**: Action — create, review, and stage the vulnerability advisory or report artifact for publication
- **Input dependency**: Human analyst.
  Content authoring, review, and approval workflow.
  Advisory publishing pipeline
- **Notes**: Succeeds almost always in simulation
- **Automation potential**: **Low** — advisory writing needs human expertise and editorial judgment.
  The review and approval workflow also usually involves human stakeholders.
- **New-arch cross-ref**: `vultron.demo.fuzzer.report_management.publication.PrepareReport`
- **Call-out point shape**: Composer
- **Factory-fn placement**: `vultron.core.behaviors.report.publication_tree.create_publication_tree` (`prepare_report_factory` param) — Composer in the report arm, between `ShouldPublishReport` and the publish pipeline

## `ReprioritizeReport`

- **Node name**: `ReprioritizeReport`
- **btz type**: `AlwaysSucceed` (p=1.00)
- **Source file**: `report_management/fuzzer/publication.py`
- **Parent tree**: `Publication`
- **Semantic function**: Action — update the priority of the report artifact in the publication queue
- **Input dependency**: Human analyst or automated policy trigger.
  Priority queue management
- **Notes**: Always succeeds in simulation
- **Automation potential**: **Medium** — automation can do policy-triggered reprioritization, for example on embargo exit or threat escalation.
  Complex editorial decisions need human oversight.
- **New-arch cross-ref**: `vultron.demo.fuzzer.report_management.publication.ReprioritizeReport`
- **Call-out point shape**: Evaluator
- **Factory-fn placement**: Eliminated in production: `PrioritizePublicationIntents` carries all publish or withhold intent (ADR-0028).
