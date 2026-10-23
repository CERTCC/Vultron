Vultron Spec Review Report

1. Metadata

This report represents a rigorous distillation of the specification review
session held on March 27, 2026. The primary objective of this review was to
harmonize technical requirements across the expanding documentation suite,
normalize project terminology—specifically ensuring the "Vultron" name is used
consistently—and prepare all findings for direct ingestion into the development
backlog. Traceability from these findings back to the original specification
files is maintained through the VSR identification system to ensure
accountability throughout the Vultron development lifecycle.

Field Value
Report Title Vultron Spec Review Report
Generated Timestamp 2026-03-27T15:10:00Z
Source Inputs 20260327 093825.m4a, 20260327 101738.m4a, 20260327 120756.m4a,
Pasted Text Transcript

Traceability remains a core requirement; every finding below is mapped to its
source specification to provide a clear audit trail for implementation.

1. Technical Specification Findings

The following findings are categorized by specification file. To ensure unique
tracking within the Vultron development lifecycle, each entry follows the
VSR-XX-YYY identification format. This structured approach facilitates direct
backlog ingestion and ensures that every technical directive is tied to a
specific architectural origin.

CI Security (CIsecurity.md)

* ID: VSR-01-001
  * Spec Reference: CI-SEC-01-001 / CI-SEC-01-002
  * Issue: Requirement for SHA-1 hashes and version comments is clear but
      requires automated verification.
  * Required Action: Implement a Python-based test that parses GitHub Workflow
      YAML files to ensure all uses: lines utilize SHA-1 hashes instead of
      version pins, and verify the presence of version number comments.
  * Context: To ensure cryptographic traceability of workflows and prevent the
      use of mutable version tags.
* ID: VSR-01-002
  * Spec Reference: CI-SEC-03-001
  * Issue: Signatures and checksums for third-party artifacts must be
      verified, but implementation responsibility is currently ambiguous.
  * Required Action: Explicitly mandate that the CI runner or installation
      scripts verify signatures and checksums before execution.
  * Context: To prevent supply-chain attacks via unverified third-party tools.

This concludes the findings for CI security; the focus now shifts to deployment
and isolation requirements for multi-actor environments.

Multi-Actor Demo (multiactor_demo.md)

* ID: VSR-02-001
  * Spec Reference: DEMO-MA-01-001
  * Issue: Isolation requirements for actor data layers are over-restrictive
      regarding shared storage.
  * Required Action: Amend DEMO-MA-01-001 to permit shared storage volumes
      provided that logical isolation and separate data layer instances are
      strictly maintained.
  * Context: To ensure the demo proves system independence while remaining
      technically feasible in containerized environments.
* ID: VSR-02-002
  * Spec Reference: DEMO-MA-01-001
  * Issue: Cross-actor communication requirements are currently nested
      sub-bullets.
  * Required Action: Promote "Cross-actor communication must occur exclusively
      via HTTP and the activity streams inbox endpoint" to a standalone,
      high-level requirement.
  * Context: This is a fundamental architectural constraint governing all
      actor interactions and must be visible at the top level.
* ID: VSR-02-003
  * Spec Reference: DEMO-MA-01-003
  * Issue: Manual reset of containers is inefficient for repeatable demos.
  * Required Action: Implement an automatic state reset mechanism upon demo
      startup to ensure a clean environment without user intervention.
  * Context: To provide a turnkey, reproducible experience for users running
      multi-actor scenarios.

With the demo environment parameters established, we move to the internal logic
governing participant transitions.

State Machine (statemachine.mmd)

* ID: VSR-03-001
  * Spec Reference: Preamble
  * Issue: Incorrect description of state sharing across participants.
  * Required Action: Update the preamble to clarify that while Embargo
      Management (EM) and Participant Exchange Architecture (PXA) states are
      shared across all participants via the Case Actor, the Vultron
      Forwarding (VFD) portion of the Case State is maintained strictly
      per-participant.
  * Context: To accurately reflect the distributed nature of Case State and
      avoid architectural confusion regarding state ownership.
* ID: VSR-03-002
  * Spec Reference: SM-04-002
  * Issue: Error naming is insufficiently descriptive for transition failures.
  * Required Action: Rename VultronConflictError to
      VultronInvalidStateTransitionError. Mandate that the system generates
      warning or error logs for invalid transitions rather than failing
      silently.
  * Context: To provide clearer diagnostic information and ensure protocol
      violations are captured in system logs.
* ID: VSR-03-003
  * Spec Reference: SM-03-001 / SM-03-002
  * Issue: Strict base-class requirements are unnecessarily rigid for simple
      state machines.
  * Required Action: Downgrade the requirement for the explicit
      transition-base subclass and module-level list storage from "MUST" to "
      SHOULD."
  * Context: The transition-base class is a convenience data class for
      internal use and should not rise to the level of a system-wide "MUST"
      requirement for all state machine implementations.

Following the internal state logic, the replication of these states across the
network requires similar rigor.

Sync Log Replication (sync_log_replication.md)

* ID: VSR-04-001
  * Spec Reference: SYNC-01-003
  * Issue: Log immutability lacks cryptographic proof in the current
      specification.
  * Required Action: Add a "Production Only" requirement for the Case Actor to
      cryptographically sign each log entry, incorporating the previous entry's
      hash into the current hash to create a chain of custody.
  * Context: To create a verifiably immutable chain of traceability for the
      entire case history.
* ID: VSR-04-002
  * Spec Reference: SYNC-03-001 / SYNC-04-001
  * Issue: Conflict handling and state synchronization need explicit
      transport-level mechanisms.
  * Required Action: Mandate that rejected out-of-sequence log entries trigger
      a response with the highest accepted index or hash corresponding to
      that index Implement a "read receipt"
      mechanism for transport confirmations. Additionally, update the Case URL
      to include a parameter or hash (e.g., Git log style prefix) communicating
      the participant's current log state.
  * Context: To ensure the log remains synchronized even after transient
      failures and to allow the Case Actor to identify and replay missing
      entries efficiently.

Decision: Prefer responses using hashes rather than indices for log
synchronization state reporting. This implies the need for a new spec to
capture the requirement for the Case Actor to include a hash of the update
it's sending in the replication message. Forward-linked merkle chain is the
model.

Further consideration: it is preferable for receivers to reply
with the hash of the last accepted entry rather than the index since both sides
will have access to the hashes they will be able to look that up, and the
Case Actor can just replay the hashes following the last hash that the
participant reports having received.

In fact, we should consider updating anything using the case ID as context
to also append the hash of the last accepted log entry as a parameter in the
context when sending ANYTHING to the Case Actor. That way the Case Actor
always knows the state of the participant's log and can make synchronization
decisions based on that. (E.g., if participant sends a response whose
context indicates they're behind, the Case Actor can immediately replay
announcements for the missing entries without waiting for an explicit
request for them.)

The accuracy of these replicated logs depends heavily on the underlying
traceability matrix.

Traceability (traceability.md)

* ID: VSR-05-001
  * Spec Reference: TRACE-02-002
  * Issue: Requirements for flagging insufficient coverage are too passive.
  * Required Action: Update the spec to require that implementation notes for
      uncovered user stories must include specific technical details on the gaps
      and concrete steps for remediation.
  * Context: To ensure that "lack of coverage" notes are actionable
      engineering tasks rather than just descriptive labels.

Once traceability is secured, the definitions within the vocabulary model must
be audited for stability.

Vocabulary Model (vocabulary_model.md)

* ID: VSR-06-001
  * Spec Reference: VM-01-001
  * Issue: The Registry is fragile and dependent on explicit side-effect
      imports to populate.
  * Required Action: Audit the VocabularyRegistry and transition from the
      current decorator-based model to a parent-class auto-registration model.
  * Context: To prevent runtime failures caused by unimported vocabulary
      modules and eliminate the need for manual **init**.py updates.
* ID: VSR-06-002
  * Spec Reference: VM-07-001
  * Issue: JSON dumps contain unnecessary noise from empty strings.
  * Required Action: Update serialization requirements to exclude both
      null/None values and empty strings from all model dumps.
  * Context: Many JSON processing mechanisms handle empty strings poorly;
      exclusion reduces payload noise and improves compatibility across external
      tools.

The vocabulary and logic findings necessitate a standard for how this code is
written and maintained.

Code Style & Tech Stack (codestyle.md, techstack.md)

* ID: VSR-07-001
  * Spec Reference: CS-07-003
  * Issue: Use of as_ prefixes in wire objects is being deprecated.
  * Required Action: Standardize on underscore suffixes (e.g., type_, id_) for
      wire-layer objects to avoid collisions with Python keywords.
  * Context: This aligns with modern Python standards and ensures clean,
      keyword-safe output in the wire layer.
* ID: VSR-07-002
  * Spec Reference: CS-13-005
  * Issue: ISO8601 formatting needs a more precise technical reference.
  * Required Action: Update the specification to reference relevant RFCs for
      ISO8601 formatting to ensure consistent offsets (explicitly Z or +00:00).
  * Context: To ensure cross-platform compatibility and reliable parsing of
      time-sensitive case events.
* ID: VSR-07-003
  * Spec Reference: CS-13-003
  * Issue: Stripping microseconds is an unnecessary restriction.
  * Required Action: Remove the requirement to strip microseconds; higher
      resolution clocks must be supported for data handled by external systems.
  * Context: Microsecond resolution provides better precision for
      high-frequency events and does not negatively impact storage.

Standardizing style leads to the meta-level requirements for documentation and
specifications themselves.

Project Documentation & Meta-Specs (project_documentation.md,
metaspecifications.md)

* ID: VSR-08-001
  * Spec Reference: Meta-Spec / General
  * Issue: Greppability of requirements is hindered by missing strength
      keywords.
  * Required Action: Update the meta-specification to mandate that every
      individual requirement line MUST include a strength keyword (MUST, SHOULD,
      or MAY).
  * Context: To allow for automated extraction, filtering, and priority-based
      auditing of requirements.
* ID: VSR-08-002
  * Spec Reference: PD-02-002 / PD-03-003
  * Issue: Implementation history and current state authority are occasionally
      conflated.
  * Required Action: Enforce a "Tombstone" format for completed items.
      Explicitly state that implementation history is the authoritative record
      of when changes happened, but the source code is the authority of where
      components are located.
  * Context: To keep active documentation focused while preserving an accurate
      audit trail for historical decisions.

The final review category ensures that these requirements are verifiable without
introducing systemic instability.

Testability & Prototype Shortcuts (testability.md, prototype_shortcuts.md)

* ID: VSR-09-001
  * Spec Reference: TB-06-006
  * Issue: Permanent specification files contain transient
      implementation-level noise.
  * Required Action: Remove specific mentions of current flaky tests (
      specifically test_remove_embargo) from the .md specs and relocate them to
      implementation notes.
  * Context: Specifications must reflect the intended architectural design,
      not the temporary state of the bug tracker.
* ID: VSR-09-002
  * Spec Reference: Prototype Preamble
  * Issue: Handling of production-only requirements is insufficiently
      formalized.
  * Required Action: Formalize the handling of PROD_ONLY tags as a "SHOULD"
      requirement within the prototype shortcuts specification.
  * Context: To provide clear guidance on which high-security features can be
      safely deferred during the prototyping phase without violating the core
      spec.

The following items have been extracted from the March 27, 2026, transcripts and
formatted to match the structure and identifying conventions of the **Vultron
Spec Review Report**.

### State Machine Definitions (statemachine.mmd)

* ID: VSR-SM-004
  * Issue: Potential **data redundancy** and storage inefficiency between the
      case state log, status history, and the unified case history log,.
  * Required Action: (**MUST**) Refactor the case state log to be a **list of
      pointers (IDs)** referencing entries in the main case history log rather
      than duplicating full record content,. The system must **automatically
      refresh** this pointer list whenever a state event is recorded to the main
      history,.
  * Context: Utilizing pointers (or sequence numbers/indexes) allows for
      **monotonically increasing** lookups to find the most recent status (at
      the end of the list) without doubling storage for the same information,,,.

### Vocabulary Model (vocabulary_model.md)

* ID: VSR-VM-003
  * Issue: Risk of **unauthorized or accidental modification** of static data
      objects during runtime,.
  * Required Action: (**SHOULD**) Implement **frozen data objects** (immutability)
      using **Pydantic’s data class features** for all objects intended to be
      static once created,.
  * Context: Freezing these objects ensures that any attempt to modify them will
      **trigger an exception**, allowing the system to catch and handle integrity
      violations immediately,.
* ID: VSR-VM-004
  * Issue: Loss of critical state data when messages are **unparsable or
      contain unknown semantics**,.
  * Required Action: (**MAY**) Establish a mechanism where **unknown messages**
      are still passed to the case log, creating an “opening” for **human or
      agent intervention**,.
  * Context: This allows for a **manual override** where a user or an advanced
      agent can interpret the unparsable message and manually translate its
      content into the necessary state changes for the case,.

### Project Documentation (project_documentation.md)

* ID: VSR-PD-003
  * Issue: Conflation of authoritative sources regarding **component locations**
      vs. project history,.
  * Required Action: (**MUST**) Amend **PDO3-03** to clarify that while
      implementation history is the authoritative record of *when* changes
      occurred, the **active source code** is the only authoritative record of
      *where* components are currently located,.
  * Context: Maintenance notes should be updated to reflect current paths, but
      developers must be instructed to **confirm component locations via a code
      check** rather than relying solely on historical notes,.

### Dispatch Routing (dispatch_routing.md)

* ID: VSR-DR-001
  * Issue: Requirement **DR1-2** is outdated and conflicts with the move toward
      **preloaded dispatchable objects**,.
  * Required Action: (**MUST**) Update the dispatch routing specification to
      reflect that use case `execute` calls should be made **without arguments**,.
  * Context: The system is transitioning to a model where the dispatcher creates
      an object already **preloaded with the event and data layer**, making the
      passing of these elements during the `execute` call redundant,.

### CI Security (CIsecurity.md)

* ID: VSR-01-003
  * Spec Reference: CI-SEC-04-001 / CI-SEC-04-002
  * Issue: The requirement for periodic manual review and documentation of SHA
      pins may be redundant with automated project tooling.
  * Required Action: (**SHOULD**) Verify if the current Dependabot configuration
      adequately handles the periodic review and updating of SHA pins,. If
      confirmed, consolidate the requirement to designate Dependabot as the
      primary mechanism for ensuring pin currency.
  * Context: To avoid unnecessary manual overhead for tasks that are already
      automated by the project’s existing security tooling,.

---

### State Machine (statemachine.md)

* ID: VSR-03-004
  * Spec Reference: SM-01-003
  * Issue: Silent precedence of code enums over protocol documentation masks
      significant architectural discrepancies.
  * Required Action: (**MUST**) Amend SM-01-003 to require that any detected
      mismatch between the authoritative `Vultron` core state enums and the
      formal protocol documentation be recorded as a “noteworthy event” rather
      than being silently adjusted,.
  * Context: Such discrepancies are significant events indicating that the
      initial design may be flawed; they require explicit correction and attention
      rather than just a programmatic precedence rule,.

### Behavior Tree Integration (behaviortree_integration.md)

* ID: VSR-10-001
  * Spec Reference: Design Note (BT-General)
  * Issue: Excessive internal complexity within individual behavior nodes hinders
      process auditability and log analysis.
  * Required Action: (**SHOULD**) Enforce a design directive where behavior nodes
      must remain simple, focused primarily on exception handling or boolean
      checks,. Any node performing complicated business logic is a candidate for
      its own sub-behavior tree.
  * Context: Surfacing business logic into the tree structure rather than hiding
      it within node code makes the process auditable, loggable, and visible for
      analysis to ensure the process is functioning as intended,,,.

1. Cross-Cutting Notes & Systemic Observations

Systemic issues require holistic attention beyond individual spec updates to
maintain the long-term health of the Vultron architecture. Addressing these
patterns is essential for reducing technical debt and ensuring the scalability
of the system.

Observations

* Registry Fragility: The side-effect registration pattern for vocabularies is a
  primary source of runtime failures. If a module is not explicitly imported, it
  does not exist in the registry, leading to silent failures during dynamic
  deserialization.
* Redundancy and Duplication: There is significant overlap between
  dispatch_routing.md and handler_protocol.md, as well as between the Tech Stack
  and Code Style specs. This redundancy increases maintenance overhead and the
  risk of requirement divergence. This is a significant issue that warrants
  a consolidation audit and review to merge or otherwise eliminate redundant
  requirements. The task is broader than just the dispatch/handler and tech
  stack/code style specs. A comprehensive audit of all .md files in the
  /specs directory is recommended to identify and resolve any additional
  instances of redundancy or overlap.
* Spec vs. Notes Distinction: Permanent specification files are currently being
  used to track transient code issues (like flaky tests). This pollutes the
  architectural intent with implementation noise and creates a maintenance
  burden. Specs should only periodically need to be refreshed when the state
  of the codebase changes, so it's not ideal for them to contain details
  like specific issues that are expected to be resolved soon. Those belong
  in notes, and should reference the spec requirements they relate to.
* Grouping specs by keyword strength (MUST, SHOULD, MAY) is fine, but only
  having the keyword in the header and not in the individual requirement
  lines makes it difficult to audit and extract requirements based on
  strength. (e.g., supporting `grep -E "MUST|SHOULD|MAY" specs/*.md` to quickly
  find all requirements of a certain strength across the entire spec suite
  is not possible if the keyword is only in the header and not in the  
  individual lines). This is a significant issue that warrants a
  full-spectrum audit of all .md files in the /specs directory to ensure
  that every requirement line includes a mandatory strength keyword (MUST,
  SHOULD, MAY). It is not necessary to rewrite existing specs entirely,
  merely inserting the keyword between the ID and the requirement text on
  each line is sufficient (e.g., `XX-01-001 (MUST) Use SHA-256 hashes...`).

Action Items

* [ ] Consolidation Audit: Evaluate specs/ to eliminate redundant
  requirements.
* [ ] Strength Keyword Migration: Conduct a full-spectrum audit of all .md files
  in the /specs directory to ensure every requirement line includes a mandatory
  keyword (MUST, SHOULD, MAY).
* [ ] Documentation Refactor: Relocate all obsolete implementation notes and
  transient technical commentary to a top-level /archived_notes directory (
  outside the /docs navigation tree) to resolve MKDocs build warnings.
* [ ] Vocabulary Registration Revamp: Research and implement more robust way
  to populate the vocabulary registry on startup without having to rely on
  import side effects or developers remembering to add class decorators.
  Consider inserting a parent class or mixin that performs the registration
  automatically when subclassed. But the real goal is to avoid forcing
  developers to remember that they have to update something in two places in
  order for it to work. The vocabulary **init**.py might be able to
  dynamically discover and import all the other modules in the package, for
  example, rather than relying on explicit imports. The registry structure
  and registry population are actually two separate issues.
* [ ] RFC-3339 / ISO8601 Standardization: Update all datetime-related
  specifications to point specifically to RFC standards to ensure
  consistency in offsets and wire formats. To be clear we want
  `YYYY-mm-ddTHH:MM:SSZ` or `YYYY-mm-ddTHH:MM:SS+00:00` specified in the spec
  with references to RFC 3339.

Final thoughts:

Vultron is a log-centric architecture in which the Case Actor is the
authoritative single writer of an append-only, hash-chained log, and all
externally visible system state is a deterministic projection of that log.
Replication is eventually consistent, with participants synchronizing via log
position (hash) rather than independent state mutation. Current requirements
assume a single-writer regime (no concurrent writers), while deliberately
preserving forward compatibility with a Raft-like consensus model for leader
election and failover; however, failover semantics are out of scope for the
current phase and MUST NOT be implicitly assumed by other specifications. All
specs interacting with state, messaging, or storage MUST treat the log as the
sole source of truth, MUST define behavior in terms of log append, validation,
and replay, and MUST NOT introduce alternative state authorities or side-channel
synchronization mechanisms. This constraint is intended to prevent divergence
between components (state machine, dispatch, vocabulary, replication) and to
ensure that future consensus integration can be introduced without breaking
existing invariants.

All components MUST preserve a small set of system invariants under normal
operation and partial failure. At minimum: (1) append-only integrity — log
entries are immutable once committed and are uniquely identified by their
content hash; (2) deterministic projection — given an identical log prefix, all
compliant implementations MUST derive identical state; (3) idempotent replay —
reprocessing any log prefix (including duplicates) MUST not change the resulting
state; (4) monotonic visibility — participants MUST NOT regress their
acknowledged log position; and (5) reject-on-divergence — entries that do not
extend the current hash chain MUST be rejected and trigger resynchronization.
The spec SHOULD further define commit/ack semantics (e.g., when an entry is
considered accepted vs. durable), signature verification requirements, and
explicit behaviors for out-of-sequence delivery, duplicate delivery, and
transient network failure. This makes correctness properties testable,
constrains edge-case handling across specs, and provides a stable contract ahead
of future consensus integration.

As we approach more robust prototyping and early production work, we will
need to define the trust model and key management requirements that underpin log
integrity and actor identity. Each Case Actor and participating node MUST
possess a cryptographic identity, and all log entries MUST be signed by the
authoritative writer and verifiable by recipients. The specification MUST define
how keys are generated, distributed, rotated, and revoked, as well as how trust
anchors are established (e.g., pinned keys vs PKI). Verification of signatures
and hash-chain continuity MUST be mandatory prior to accepting or replaying log
entries. The system MUST also specify behavior for key compromise, including how
to invalidate prior trust, re-establish authority, and prevent malicious log
injection or fork attempts. Without an explicit trust model, the guarantees
provided by the hash-chained log and eventual replication semantics are
incomplete and potentially unenforceable.
