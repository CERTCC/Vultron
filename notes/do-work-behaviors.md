# Do-Work Behaviors: Scope and Implementation Notes

This note documents the scope boundaries for "do work" behaviors in the
Vultron prototype and identifies which behaviors are automatable, partially
automatable, or entirely out of scope for the system.

**Cross-references**: `specs/case-management.md` (CM-05-*),
`docs/topics/behavior_logic/`, `plan/IDEATION.md`

---

## Out of Scope: Vulnerability Discovery

Vulnerability-discovery behavior (see `vuldisco_bt.md`) is **out of scope**
for the Vultron prototype. The system does not discover vulnerabilities or
model that process. The effective starting point for Vultron interactions
is when a finder or reporter submits a `VulnerabilityReport` to a
coordinator or vendor inbox. The discovery behavior tree remains as
explanatory material only and does not require implementation.

---

## Not Implementable Inside Vultron

The following "do work" branches in Vultron behavior trees describe external,
human-driven processes. Vultron can record the outcomes of these activities
(via state transitions and notes) but cannot automate them. Documentation
pages for these behaviors SHOULD include a callout (e.g., an MkDocs
`!!! note` admonition) stating that the process is notional and not intended
to be fully automated inside Vultron.

| Behavior | Reference | Notes |
|---|---|---|
| Acquire exploit | `docs/topics/behavior_logic/acquire_exploit_bt.md` | Human-driven; system may record the result as a state transition only |
| Monitor threats | `docs/topics/behavior_logic/monitor_threats_bt.md` | Ongoing human/external monitoring; system may accept injected notes |
| Develop fix | `docs/topics/behavior_logic/fix_dev_bt.md` | Out of scope — Vultron coordinates but does not develop fixes |
| Deploy fix | `docs/topics/behavior_logic/deployment_bt.md` | Out of scope for the same reasons as fix development |

Some primitives within these behaviors — such as emitting a message or
updating case/participant status — can be exposed as API actions that a human
or external system invokes. The system acts as a state recorder and
coordinator, not an automation engine for these activities.

---

## Partially Implementable Behaviors

The following behaviors can be partially supported by the application:

### ID Assignment

Assigning identifiers to vulnerabilities (e.g., CVE numbers) could be
implemented as a stub behavior that:

1. Calls an external numbering API (e.g., CVE Services API) if available
2. Composes an identifier record in the case

See `docs/topics/behavior_logic/id_assignment_bt.md`. For the prototype, a
stub that records a locally-generated placeholder ID is sufficient.

### Publication

Publication typically occurs outside Vultron (e.g., a vendor advisory or
NVD database entry), but publication events SHOULD be represented as an
application-level action that:

1. Triggers state transitions (e.g., adds a `PUBLIC` PXA case status)
2. Accepts publication metadata (publisher, URL, date) as a linked reference
3. Stores a note on the case with the metadata

See `docs/topics/behavior_logic/publication_bt.md` and
`specs/case-management.md` CM-05-004 and CM-05-005.

---

## Reporting Behavior as Central Coordination

Reporting — sending case information to other actors, inviting them to
participate, and negotiating embargo terms — is the central coordination
activity in CVD and the primary use case for Vultron's protocol messaging.
It is not fully automatable but is well-supported by flows such as:

- Inviting actors to cases (`invite_actor_to_case`)
- Negotiating embargo duration (`invite_to_embargo_on_case`)
- Asking actors to confirm agreement before receiving sensitive details

A key underspecified area is **embargo policy compatibility evaluation**:
before inviting an actor to an embargo, the system should evaluate whether
the actor's declared policy (minimum/maximum duration, preferences) is
compatible with the proposed embargo terms. See `specs/embargo-policy.md`
for the specification of the embargo policy record format, and the "Prior Art"
section below for external references.

---

## Prior Art and References (Embargo Policy)

The following prior work is relevant to a standardized embargo policy record:

- **RFC 9116** (security.txt): <https://www.rfc-editor.org/rfc/rfc9116>
  — defines a machine-readable file for security disclosure contact info;
  a natural companion to an embargo policy declaration
- **disclose.io DIOSTS**: <https://github.com/disclose/diosts/>
  — disclosure terms schema (vendor disclosure policies)
- **disclose.io DIOTerms**: <https://github.com/disclose/dioterms/>
  — core disclosure terms vocabulary
- **SSVC** (Stakeholder-Specific Vulnerability Categorization): used for
  prioritization decisions (`specs/prototype-shortcuts.md` PROTO-05-001);
  relevant to engage/defer decisions that precede embargo negotiation

---

## Relationship to Specifications

| Topic | Specification |
|---|---|
| Object model (Reports, Cases, Publications, Vulnerability records) | `specs/case-management.md` CM-05-* |
| Embargo policy format | `specs/embargo-policy.md` |
| Do-work BT node guide | `specs/behavior-tree-integration.md` BT-* |
| Case prioritization stub | `specs/prototype-shortcuts.md` PROTO-05-001 |
