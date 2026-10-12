---
description: >
  The terms this documentation uses for the Vultron Coordinated Vulnerability
  Disclosure (CVD) protocol and its reference implementation, with the aliases
  to avoid and the ambiguities to watch for.
stakeholder_type: ALL
level: 100
---

# Glossary — Vultron

This glossary is the registry of the names this documentation uses: each term, the aliases to avoid for it, and the ambiguities that recur around it.
It is not the authority for what a protocol term means.
[§2 Terminology in the Vultron Protocol Specification](vultron-spec/introduction.md#2-terminology-ni) is the normative definition of every protocol term, and the rows below that carry one link to it instead of restating it.
The [Concept Taxonomy](vultron-taxonomy.md) is the authority for the names of the Vultron concepts themselves — `vultron-core`, `vultron-wire`, capability sets, capability shapes.

The glossary has two parts.
The first covers the Coordinated Vulnerability Disclosure (CVD) process and the protocol, and is for every reader.
The second, [Reference Implementation Vocabulary](#reference-implementation-vocabulary), names the classes, ports, and patterns of the Python reference implementation, and is for the people who build against it or work on it.

---

## Core CVD Concepts

| Term | Definition | Aliases to avoid |
|------|-----------|-----------------|
| **Vulnerability** | Defined in [§2.1 Actors, Participants and Cases](vultron-spec/introduction.md#21-actors-participants-and-cases): a set of conditions or behaviors that allows the violation of a security policy. The definition is taken unchanged from the [CERT Guide to CVD](https://certcc.github.io/CERT-Guide-to-CVD/tutorials/terms/vulnerability/). | Bug, issue, flaw, weakness |
| **Coordinated Vulnerability Disclosure (CVD)** | The process by which the parties affected by a vulnerability work together to manage its remediation and public disclosure. | Responsible disclosure, coordinated release |
| **Multi-Party CVD (MPCVD)** | CVD with more than one Vendor or Coordinator in the case. This documentation uses *CVD* and *MPCVD* interchangeably: the protocol is built for the multi-party case, of which single-Vendor CVD is the special case with one Vendor. See [CVD is MPCVD, and MPCVD is CVD](../topics/background/cvd-coordination-problem.md#cvd-is-mpcvd-and-mpcvd-is-cvd). | Multiparty coordination |
| **Report** | Defined in [§2.1 Actors, Participants and Cases](vultron-spec/introduction.md#21-actors-participants-and-cases): a document describing a specific vulnerability, submitted to initiate coordination. The unit of work of a Participant's [Report Management (RM) process](../topics/process_models/rm/index.md). | Submission, notice |
| **Case** | Defined in [§2.1 Actors, Participants and Cases](vultron-spec/introduction.md#21-actors-participants-and-cases): the coordination context around a specific vulnerability, and the unit of Vultron protocol activity. | Issue, coordination event |

---

## CVD Roles and Participants

The role names follow the [*CERT Guide to Coordinated Vulnerability Disclosure*](https://certcc.github.io/CERT-Guide-to-CVD){:target="_blank"}, and are consistent with the International Organization for Standardization (ISO) and International Electrotechnical Commission (IEC) standards [ISO/IEC 29147:2018](https://www.iso.org/standard/72311.html){:target="_blank"} and [ISO/IEC 30111:2019](https://www.iso.org/standard/69725.html){:target="_blank"} except where a row says otherwise.
Each role corresponds to a `CVDRole` value in the protocol, except where noted.
The normative role definitions are in [§2.2 Roles in the specification](vultron-spec/introduction.md#22-roles).
[Case Model](../topics/case_lifecycle/case_model.md) shows how Cases, Participants, and Reports relate.

| Term | Definition | Aliases to avoid |
|------|-----------|-----------------|
| **Actor** | Defined in [§2.1 Actors, Participants and Cases](vultron-spec/introduction.md#21-actors-participants-and-cases): an identity in the protocol, named by a Uniform Resource Identifier (URI), that exists independently of any case. | Agent, endpoint |
| **Participant** | Defined in [§2.1 Actors, Participants and Cases](vultron-spec/introduction.md#21-actors-participants-and-cases): an Actor that has joined a specific Case, holding one or more CVD roles in it. | "Stakeholder" *used as a synonym for Participant*, party. The bare word is permitted in its ecosystem-category sense — see **Stakeholder Type** |
| **Active Participant** | A **Participant** entitled to case content: one seated by case initialization (the **Case Owner**, the **Case Manager** and the **Reporter**) or one that has accepted its **Stub Invite**, that has not been removed, and, only while an **Embargo** is active, a signatory to it (CM-10-004, CM-31-002, ADR-0114, ADR-0116). Only active participants receive ledger entries, case announcements and status broadcasts; the case publishes them as its `activeParticipants` collection. | Joined participant (ambiguous: a joined participant whose embargo consent lapsed is inert) |
| **Inert Participant** | A **Participant** record that is not an **Active Participant**: an invitee that has not accepted its **Stub Invite**, one that rejected it, a joined participant not a signatory to the active **Embargo**, or one the **Case Owner** removed. It is tracked on the roster but receives no case content; it still receives the Invites that ask it to join or to consent, unless it was removed (CM-10-007, CM-31-013, ADR-0114, ADR-0116). | Pending participant, invited participant |
| **Reporter** | Defined in [§2.2 Roles](vultron-spec/introduction.md#22-roles): the Participant that submitted the Report. The protocol is concerned with who reported a vulnerability, not with who found it. | Submitter, notifier |
| **Finder** | The person or organization that discovers a vulnerability. Not a protocol role (ADR-0078): an actor that discovers and reports holds the **Reporter** role, and a discoverer who does not report is recorded in the **Report** content or a case **Note**, as metadata rather than as a role. | Researcher, discoverer |
| **Vendor** | Defined in [§2.2 Roles](vultron-spec/introduction.md#22-roles): the Participant that produces the vulnerable product and is responsible for developing a fix. [Stakeholder-Specific Vulnerability Categorization (SSVC)](https://github.com/CERTCC/SSVC){:target="_blank"} version 2 and later calls this role *Supplier*; this documentation does not. | Developer, supplier, maintainer |
| **Deployer** | Defined in [§2.2 Roles](vultron-spec/introduction.md#22-roles): the Participant that deploys a Vendor's fix to systems it operates. ISO/IEC 29147 and ISO/IEC 30111 call this role *User*; this documentation does not. | Operator, customer |
| **Coordinator** | Defined in [§2.2 Roles](vultron-spec/introduction.md#22-roles): the Participant that facilitates multi-party coordination without being responsible for developing a fix itself. | Mediator, facilitator |
| **Observer** | Defined in [§2.2 Roles](vultron-spec/introduction.md#22-roles): the Participant with no obligation to drive vendor, fix, or deploy transitions. The base role — the lowest non-null privilege set — admitted through the standard invitation and acceptance flow (ADR-0057, CM-25). Formerly `CVDRole.OTHER`. | Watcher, monitor, OTHER (deprecated) |
| **CVE Numbering Authority (CNA)** | Defined in [§2.2 Roles](vultron-spec/introduction.md#22-roles): the Participant authorized to assign Common Vulnerabilities and Exposures (CVE) IDs directly rather than delegating assignment to an external service; modeled as `CVDRole.CVE_NUMBERING_AUTHORITY`. | CVE authority |
| **Exploit Publisher** | A person or organization that publishes exploits. Not a `CVDRole` value: it names a behavior the protocol constrains rather than a role a Participant holds. An Exploit Publisher taking part in a pre-public case is expected to withhold exploit code while an embargo is active, and is often also a Reporter, Coordinator, or Vendor. The *CVD Guide* does not define this role; a future version is expected to. | — |
| **Case Owner** | Defined in [§2.2 Roles](vultron-spec/introduction.md#22-roles): the party whose disclosure decision the case exists to serve; it decides who is admitted, which roles they hold, and whether embargo terms are accepted. Modeled as `CVDRole.CASE_OWNER`. | Case creator |
| **Case Manager** | Defined in [§2.2 Roles](vultron-spec/introduction.md#22-roles): the Participant that writes the canonical case ledger and relays case-scoped messages on the Case Owner's behalf — the case's **single-writer authority**. Modeled as `CVDRole.CASE_MANAGER`; authority follows the role and nothing else (ADR-0088). Protocol-normative prose names the authority *the CASE_MANAGER* (the role holder), never *the CaseActor* (the prototype identity). | Admin role, management role |
| **Case Actor** | The concrete actor the **prototype/demo implements** to hold `CVDRole.CASE_MANAGER` — an automated software actor spawned to enact the role and automate its duties (emitting activities, maintaining the canonical ledger). It is a specific **identity/label** (`case-actor`, `.../actors/case-actor`) with **no protocol meaning**. It is **not** a synonym for the authority and **not** an identity to match on: authority, recognition, and routing derive from the **`CASE_MANAGER` role**, never from this actor's name or URL, and code MUST NOT compare `actor_id` against a computed `case_actor_id` to decide authority (ADR-0088, refining ADR-0041). Name the authority **Case Manager** (the role holder); use **Case Actor** only for the prototype actor that happens to hold it. | Case service actor, case coordinator, "the CaseActor authority" |
| **Case Actor Service** | The provisioning endpoint (configured as `case_actor_service_url`) that receives `CaseProposal`s and spawns the `case-actor` identities that enact `CASE_MANAGER`. A hosting/provisioning concern — distinct from the authority (the **role**) and from any one **Case Actor** identity it spawns. Hosting location and URL shape carry no authority signal (ADR-0088). | Case actor URL, provisioning service |

---

## Documentation Audience

| Term | Definition | Aliases to avoid |
|------|-----------|-----------------|
| **Stakeholder Type** | Why a reader is here reading about Vultron, declared as `stakeholder_type` in a `docs/` page's frontmatter and used to organize reader-facing documentation (ADR-0102). The permitted values are normative in DF-11-001 and are listed below. A stakeholder type is **not** a **CVDRole**, and the two vocabularies deliberately share no value: *a role is assumable, inhabitable, temporal; a type is ontological, identity-formed, and slow to change.* An organization's roles vary from case to case, while what brought its engineer to this documentation does not. No page shows its own type to readers (DF-11-009). | Role, audience track, reader level |
| **Prerequisite Level** | How much a reader must already know before a `docs/` page makes sense, declared as `level` (100–500) in its frontmatter. One ladder that sorts site-wide, though each subject area judges its own 300 by its own criteria. A property of a **page**, never of a reader — there is no "300-level reader". A page's own level is never rendered and never navigated by (DF-11-004). | Difficulty, reader level, track |

{% include-markdown "../includes/stakeholder_types.md" %}

---

## Case State Model (Six Dimensions)

The **Case State (CS)** tracks awareness and readiness across six binary dimensions:

| Abbreviation | Uppercase | Lowercase | Meaning |
|---|---|---|---|
| **V/v** | **V** | **v** | Vendor is aware / unaware |
| **F/f** | **F** | **f** | Fix is ready / not ready |
| **D/d** | **D** | **d** | Fix is deployed / not deployed |
| **P/p** | **P** | **p** | Public is aware / unaware |
| **X/x** | **X** | **x** | Exploit code is public / not public |
| **A/a** | **A** | **a** | Active attacks have been observed / not observed |

Each transition from lowercase to uppercase represents an event; once uppercase, it cannot revert.
The first three dimensions form the Participant-specific **Vendor Fix Path** (VFD) and the last three the case-wide **Public State** (PXA).
The 2^6 letter combinations give a 64-state lattice, of which only 32 are compound states: `vF*` (fix ready, vendor unaware) and `*fD*` (fix deployed, fix not ready) are structurally impossible, so VFD has 4 states and PXA has 8, and 4 × 8 = 32 ([§8.3 Case State as a Compound Tuple](vultron-spec/tracking-models.md#83-case-state-as-a-compound-tuple), SM-09-002, CSB-17-001).

---

## State Machines and Status

The specification defines five state machines — Report Management (RM), Embargo Management (EM), Participant Embargo Consent (PEC), VFD, and PXA — and every Participant tracks all five ([§12.2 Capability Sets](vultron-spec/conformance.md#122-capability-sets)).
The Case State is the compound of VFD and PXA ([§8.3 Case State as a Compound Tuple](vultron-spec/tracking-models.md#83-case-state-as-a-compound-tuple)), which is why the formal protocol pages count three machines (RM, EM, CS) where the specification counts five.

| Term | Definition | Aliases to avoid |
|------|-----------|-----------------|
| **Report Management (RM)** | Per-participant state machine tracking a Report's lifecycle: Start → Received → {Invalid \| Valid} → {Accepted \| Deferred} → Closed; independent for each participant ([§6 Report Management (RM) State Machine](vultron-spec/tracking-models.md#6-report-management-rm-state-machine-n)) | Report workflow, report state |
| **Embargo Management (EM)** | Global (per-case) state machine tracking embargo coordination: None → Proposed ↔ Active ↔ Revise → eXited; exactly one active embargo per case ([§7 Embargo Management (EM) State Machine](vultron-spec/tracking-models.md#7-embargo-management-em-state-machine-n)) | Embargo workflow, embargo state |
| **Participant Embargo Consent (PEC)** | Per-participant, per-embargo tracking of one Participant's **Embargo Consent**: one row per embargo it was asked about, Invited, Accepted, Declined or Expired (ADR-0122). The formal specification's seven-state PEC machine ([§9 Participant Embargo Consent (PEC) State Machine](vultron-spec/tracking-models.md#9-participant-embargo-consent-pec-state-machine-n)) is the protocol-level view that these rows and the active embargo together derive | — |
| **Case State (CS)** | The compound of the participant-specific **Vendor Fix Path** (VFD: vfd → Vfd → VFd → VFD) and the participant-agnostic **Public State** (PXA); 32 compound states ([§8.3 Case State as a Compound Tuple](vultron-spec/tracking-models.md#83-case-state-as-a-compound-tuple)) | Vulnerability state, case lattice, 40-state model |
| **Case Status** | Defined in [§2.3 Protocol Objects and Messages](vultron-spec/introduction.md#23-protocol-objects-and-messages): the case's shared state — its embargo state and what is publicly known. Canonical: only the CASE_MANAGER writes it. | State record |
| **Participant Status** | Defined in [§2.3 Protocol Objects and Messages](vultron-spec/introduction.md#23-protocol-objects-and-messages): a Participant's report about its own state, or its observation about the world. A claim, not a state change. | Status record |
| **State Transition** | Defined in [§2.4 State, Embargo and Disclosure](vultron-spec/introduction.md#24-state-embargo-and-disclosure): a change from one state to another in any of the five state machines; always forward, because events cannot be undone | State change, event |
| **Communicating Hierarchical State Machine** | The formal protocol architecture: N independent processes (Participants) coordinating state transitions through message passing | Protocol model, message-driven coordination |
| **Composite State** | A Participant's complete state in the formal protocol, represented as the 3-tuple (q^rm, q^em, q^cs) | Participant state, actor state |

---

## Embargo and Timing

| Term | Definition | Aliases to avoid |
|------|-----------|-----------------|
| **Embargo** | Defined in [§2.4 State, Embargo and Disclosure](vultron-spec/introduction.md#24-state-embargo-and-disclosure): a time-bounded agreement among the Participants of a Case not to disclose the vulnerability publicly before an agreed point. | NDA, disclosure delay, embargo period |
| **Embargo Event** | A point-in-time record of an embargo's end date, context, and who initiated it; used to track embargo history | Embargo record |
| **Embargo Consent** | A **Participant**'s individual agreement to or rejection of an **Embargo** (a personal commitment, distinct from the **Embargo** itself); recorded per embargo as one row per (**Participant**, **Embargo**) holding INVITED, ACCEPTED, DECLINED or EXPIRED (ADR-0122, ADR-0118). A **Participant** is a *signatory* when its row for the **Active Embargo** is ACCEPTED, and has *lapsed* when it accepted an earlier embargo but has no accepting row for the active one; neither is stored. A revision that is merely proposed, or that ends no later than the accepted terms, changes no one's consent to the embargo in force (ADR-0093). A **Participant** with no row for an embargo is not bound by it — not "has not consented yet" — so ACCEPT and DECLINE are valid directly from no row, without an intervening invitation (ADR-0048, CM-18-003) | Embargo acceptance, embargo stance |
| **Active Embargo** | The currently in-force **Embargo** for a **Case**; there is at most one | Current embargo, ongoing embargo |
| **Proposed Embargo** | An **Embargo** that has been offered but not yet accepted by all parties | Embargo offer, pending embargo |
| **Pocket Veto** | A timer-based transition in the **Embargo Consent** state machine where a **Participant** in INVITED state automatically transitions to EXPIRED if they do not respond within a configurable timeout window; inaction is recorded as an expiry, never as an explicit DECLINED (ADR-0118). The window is the *implicit* form of the **RSVP Deadline**: when an invitation carries an explicit `Invite.end_time` that value supersedes it (CM-28-002); the policy default (7 days, EP-07-001) applies only when it is absent. The two are one mechanism, not two (ADR-0065) | Embargo invitation timeout, implicit rejection |
| **RSVP Deadline** | The activity-level `end_time` on an `Invite(EmbargoEvent)`, giving the invitee an explicit respond-by instant after which the invitation is no longer open. Distinct from the nested `Invite.object_.end_time`, which is when the **Embargo** itself ends — the same invitation carries both, one nesting level apart. Bounded at both ends: never earlier than the minimum window, which is the lesser of a configured window (72h by default) and the time remaining in the **Embargo** (EP-07-002/EP-07-003), and never later than the Embargo's own end, whether it came from an explicit `Invite.end_time` or the policy window (EP-07-006, CM-28-011). Enforced lazily by the **CASE_MANAGER** (CM-28-003); a late **Accept** is never refused outright (EMB-17). Introduced by ADR-0065, bounded by ADR-0096 | Invite expiry, respond-by deadline, invite end_time |
| **EmbargoPolicy** | An actor-level declaration of embargo preferences (preferred, minimum, and maximum duration); allows coordinators to evaluate compatibility before proposing an embargo. | Embargo preferences, embargo terms |
| **Actor Default** | The embargo duration carried by an Actor's published **EmbargoPolicy**. `em/defaults.md` calls it a *standing proposal*: a Reporter who submits without contrary terms has tacitly accepted it. An actor default **does** compete in the shortest-proposal-wins comparison (EP-04-003). | Default embargo (ambiguous — see **Protocol Default**) |
| **Protocol Default** | The **Embargo** duration applied when no proposal and no **Actor Default** applies, so that an embargo-eligible **Case** always begins with an **Active Embargo**. Configurable, but constrained to 72 hours–5 days (EP-04-005) — deliberately short so that publishing an **EmbargoPolicy** is the rewarded behavior. It is the value when the candidate set is empty and **never a candidate itself**: it does not compete under shortest-wins (EP-04-006), because a short default that did would cap every embargo in the system at its own length. It is also not a minimum — a Reporter may propose less and get it (EP-04-007). Does not apply once P/X/A is set (EP-04-008). Introduced by ADR-0096 | Default embargo, fallback embargo, minimum embargo |
| **Embargo Adherence** | Whether a **Participant** is currently bound by the active **Embargo**: it is a signatory to it, meaning its **Embargo Consent** row for the active embargo is `ACCEPTED` (`CaseParticipant.is_signatory`). Derived from the consent rows and the active embargo rather than stored, so the two cannot drift out of sync (ADR-0122). The earlier stored `embargo_adherence` field was retired. | Embargo acceptance, embargo compliance |
| **Publication** | Defined in [§2.4 State, Embargo and Disclosure](vultron-spec/introduction.md#24-state-embargo-and-disclosure): a deliberate act by a Participant that makes vulnerability information publicly available. Distinct from **Public Awareness**, which is a fact about the world no Participant controls. | Disclosure (unqualified), release |

---

## Messaging and Protocol

| Term | Definition | Aliases to avoid |
|------|-----------|-----------------|
| **Semantic Type** (or **MessageSemantics**) | What a receiver recognizes an incoming **Wire Activity** as, judged from its shape alone (e.g., `SUBMIT_REPORT`, `INVITE_TO_EMBARGO_ON_CASE`); determines how it is processed. One semantic type has one or more **Occasions**, and is not a **Message Type** ([ADR-0083](../adr/0083-formal-message-set-and-as2-vocabulary-are-different-shapes.md)) | Activity type, message type, meaning |
| **Wire Activity** | An ActivityStreams 2.0 (AS2) activity of a given shape as sent between Actors, written with its literal AS2 type names — `Offer(VulnerabilityReport)`, `Accept(Invite(Event))`. The literal type names are what a sender puts on the wire | Message type, message |
| **Occasion** | A situation in a case that a sender conveys by sending a particular **Wire Activity**, sometimes narrowed by a distinguishing field value or state context: "a fix is ready" is an occasion of `Add(ParticipantStatus)` with `vf_state` `VF`, and `Add(CaseStatus)` carries three occasions told apart by `pxa_state`. See [Message Types](messages/index.md) | Meaning, use, event (an occasion is the sender's situation, not a received event) |
| **Message Type** | Defined in [§2.3 Protocol Objects and Messages](vultron-spec/introduction.md#23-protocol-objects-and-messages): one of the operations the protocol defines, each named by a **Protocol Shorthand**. The [formal message set](formal_protocol/messages.md) has 28: RM messages (RS, RI, RV, RD, RA, RC, RK, RE), EM messages (EP, ER, EA, EV, EJ, EC, ET, EK, EE), CS messages (CV, CF, CD, CP, CX, CA, CK, CE), and General messages (GI, GK, GE) | Protocol message category |
| **Protocol Shorthand** | Defined in [§2.3 Protocol Objects and Messages](vultron-spec/introduction.md#23-protocol-objects-and-messages): the two-letter code naming a **Message Type** by its meaning rather than its wire form — `RS`, `EP`, `CV`, and so on | — |
| **State-Change Notification** | The core protocol principle: every participant state transition SHOULD generate a message to inform other participants; implements "Avoid Surprise" | Status announcement, state broadcast |
| **Inbox** | The protocol endpoint where an Actor receives incoming Activities from other parties | Receiver, endpoint |
| **Outbox** | The protocol channel through which an Actor broadcasts Activities to other known parties | Sender, distribution |
| **Precondition** | The required state(s) that must be true before a message can be sent or a state transition is valid (e.g., Participant must be in RM Accepted to send RS) | State requirement, prerequisite |
| **CaseProposal** | An ActivityStreams 2.0 (AS2) negotiation object sent by any actor (typically a Vendor or Coordinator) to a **case actor service** to request the creation and management of a new Case; the CASE_MANAGER, not the requesting actor, is the authoritative case creator. The CaseProposal is the mechanism by which an actor delegates case initialization to a case actor service (ADR-0023, ADR-0041). | Case request, case creation request |
| **Case Ownership Transfer** | The protocol sequence by which the `CASE_OWNER` role is transferred from one actor to another via an `Offer(VulnerabilityCase)` → `Accept` handshake routed through the CASE_MANAGER (ADR-0053, [§11.3 Case Ownership Transfer](vultron-spec/interactions.md#113-case-ownership-transfer-n)). | Case transfer, ownership handoff |
| **Suggest-Actor-to-Case** | The CASE_MANAGER-routed protocol flow for inviting a new actor to a case: a **Participant** sends `Offer(Actor, Case)` to the **Case Manager**, the Case Manager presents the recommendation to the **Case Owner**, and upon approval issues `Invite(CaseStub, embargo)` to the suggested actor (ADR-0026). | Add participant, inject participant |
| **Stub Invite** | `Invite(Actor, VulnerabilityCaseStub)`: the **Case Manager**'s invitation to join a case, carrying a **Stub Object** and a reply deadline. Sending it creates the invitee's **Inert Participant** record; `Accept` joins the case and `Reject` closes the record (CM-11-006, CM-11-007, ADR-0114). | Case invitation (ambiguous with **Full-Case Invite**) |
| **Full-Case Invite** | `Invite(Actor, VulnerabilityCase)`: the **Case Manager**'s request, sent after a participant joins and has been replayed the case ledger, for that participant's judgment of the case. It carries the Case Manager's ledger position as a floor, and its replies `Accept`, `TentativeReject` and `Reject` record RM `VALID`, `INVALID` and `CLOSED` (CM-11-010, CM-11-011, ADR-0121). | Case Invite (ambiguous with **Stub Invite**), validate-report request |
| **Liberal Accept** | The protocol robustness principle (Postel's Law applied): be conservative in what you send, liberal in what you accept; refuse the narrowest thing that must be refused. | — |
| **Per-Dimension Adjudication** | The pattern of evaluating each state-machine dimension of a received `ParticipantStatus` independently rather than accepting or refusing the entire snapshot as a unit; allows a valid `vfd` update to proceed even if `rm` is refused (ADR-0061). | All-or-nothing status update |
| **Stub Object** | A minimal ActivityStreams 2.0 object carrying at least `id` and `type` and no restricted content; used for selective disclosure. The protocol's one stub is the case stub sent with an invitation, defined in [§2.3 Protocol Objects and Messages](vultron-spec/introduction.md#23-protocol-objects-and-messages) and used in [§11.2 Invitation and Acceptance in the protocol specification](vultron-spec/interactions.md#112-invitation-and-acceptance-n) | Lazy-loaded object, header-only object, object reference |

---

## Data and Relationships

| Term | Definition | Aliases to avoid |
|------|-----------|-----------------|
| **Case Activity Log** | A list of Activity IDs associated with a Case, recording the protocol history without storing full Activity payloads | Activity history, message log |
| **Case Event** | A trusted-timestamp record of a protocol-relevant state change (V, F, D, P, X, A event), recorded when a handler processes an incoming Activity | Event, state change record |
| **Note** | Unstructured text attached to a Case by a Participant; used for comments, observations, and negotiation | Comment, annotation, memo |
| **Parent/Child/Sibling Cases** | Hierarchical relationships between Cases: a Case can split (children) or merge (parent); siblings share a common parent | Case relationships, case graph |

---

## Sync, Authority & Replication

| Term | Definition | Aliases to avoid |
|------|-----------|-----------------|
| **Log-Centric Architecture** | A system design where the **CASE_MANAGER** is the authoritative single writer of an append-only, hash-chained **canonical recorded log**, and all externally visible replicated state is a deterministic projection of that log | Log-based architecture, event sourcing |
| **Single-Writer Regime** | The design principle that the **CASE_MANAGER** (acting as de facto replication leader) is the only node that appends to the authoritative **canonical recorded log**; simplifies consistency guarantees and avoids concurrent-write conflicts ([§5.4.1 Single-Writer Authority](vultron-spec/layers.md#541-single-writer-authority)) | Single leader, master authority |
| **Canonical Recorded Log** | The case ledger as [§2.3 Protocol Objects and Messages](vultron-spec/introduction.md#23-protocol-objects-and-messages) defines it: the case's authoritative, append-only history, written only by the **CASE_MANAGER**, hash-chained for verification, and replicated to **Participants** via `Announce(CaseLedgerEntry)` messages | Authoritative log, master log |
| **Case Ledger Entry** | Defined in [§2.3 Protocol Objects and Messages](vultron-spec/introduction.md#23-protocol-objects-and-messages) as `CaseLedgerEntry`: one entry in the case ledger, recording one accepted change, timestamped by the **CASE_MANAGER** (never copied from inbound **Activities**), and hash-chained to its predecessor | Log item, journal entry |
| **Eventual Consistency** | The replication guarantee that **Participant** replicas converge to the **CASE_MANAGER**'s state as **Case Ledger Entries** are delivered and processed | Convergence property |
| **Participant Case Replica** | A local copy of **VulnerabilityCase** state maintained by a **Participant** node; must satisfy PCR safety rules (proper seeding, no out-of-order mutations) and convergence to the **CASE_MANAGER**'s authoritative state | Case replica, local case copy |
| **Case File** | The state of a case that replicates: report management, participant records and status, the embargo register and participant embargo consent, notes and reports. Every change the **CASE_MANAGER** makes to it is committed as its own **Case Ledger Entry**, and a **Participant Case Replica** applies the entries by copying, so two replicas at the same ledger position hold identical case files (CLP-07-013, CM-23-016, ADR-0124) | Case record, case snapshot |
| **Case Bookkeeping** | The records the **CASE_MANAGER** keeps alongside a case while it works it, such as who recommended whom, offer records and pending markers. Not part of the **Case File**: never ledgered, never replicated, and never read to compute a case-file value (CLP-07-014) | Scratchpad, ephemera, case metadata |
| **Trust Bootstrap** | The first-time establishment of trust between the **CASE_MANAGER** and a new **Participant** via an **Accept** activity in response to an **Offer**; includes sending a `Create(VulnerabilityCase)` activity to seed the **Participant Case Replica** | Trust handoff, initial trust |
| **Case Replica Seeding** | The process of initializing a **Participant Case Replica** by receiving an `Announce(VulnerabilityCase)` or `Create(VulnerabilityCase)` activity from the **CASE_MANAGER**; must occur before case-context activities can be processed | Replica initialization, case sync |
| **Append-Only Ledger** | The first ledger synchronization phase: establishes the local append-only case ledger with hash-chain indexing, providing the cryptographic integrity foundation for all subsequent replication phases. Each entry is immutable once committed and uniquely identified by its content hash. | SYNC-1, phase 1 |
| **Ledger Fanout** | The second ledger synchronization phase: one-way replication from the authoritative **CASE_MANAGER** to all **Participant Actors** via `Announce(CaseLedgerEntry)` messages. A participant's replica is considered synchronized when its log tail hash matches the **CASE_MANAGER**'s. | SYNC-2, phase 2 |
| **Ledger Reconciliation** | The third ledger synchronization phase: a full sync loop with retry and backoff that detects and repairs gaps in participant replicas, ensuring eventual convergence even after missed or delayed deliveries. | SYNC-3, phase 3 |
| **Peer Ledger Sync** | The fourth ledger synchronization phase: multi-peer synchronization enabling actors with equal standing to reconcile their ledgers with each other, supporting federated and ownership-transfer scenarios where no single actor is permanently authoritative. | SYNC-4, phase 4 |
| **Genesis Hash** | A per-case SHA-256 hash derived deterministically from the `VulnerabilityCase` object; serves as the hash-chain predecessor anchor for the first **Case Ledger Entry**, binding the ledger to its origin case. | Initial hash, seed hash |

---

## Conformance — Capability Sets

Conformance is two-dimensional: a **capability set** claim (what protocol machinery the software provides) and a **role** profile (which positions the actor holds in a case).
The two are different kinds of thing — a capability set is a property of *software*; a **CVDRole** is a position an actor holds — and are named so they never collide.
The three named sets carry a **`Case`** prefix precisely to keep them distinct from the similarly-named roles they serve (ADR-0088).
A conformance claim writes them together as `CapabilitySet [+ ...] / Role [+ ...]`, e.g. `Case Observer + Case Decision + Case Hosting / Coordinator + Case Owner`.
The obligations of each set are normative in [§12.2 Capability Sets in the specification](vultron-spec/conformance.md#122-capability-sets); the rows below carry the names and the distinctions, not the obligations.

| Term | Definition | Aliases to avoid |
|------|-----------|-----------------|
| **Capability set** | A named group of protocol obligations an implementation takes on — a property of *software*, distinct from a **CVDRole** (a position in a case). The three named sets are **Case Observer**, **Case Decision**, and **Case Hosting**; the `Case` prefix marks each as a capability set, not a role. Capability sets are orthogonal to both **capability shapes** and conformance test **layers** (L1–L4, [§12.5 Conformance Testing Approach](vultron-spec/conformance.md#125-conformance-testing-approach)). | Conformance tier, T0/T1/T2, capability level |
| **Case Observer capability set** | The participation floor every case **Participant** MUST implement ([§12.2 Case Observer capability set](vultron-spec/conformance.md#case-observer-capability-set)). Named to echo the **Observer** role, with the `Case` prefix keeping set and role distinct. There is no sub-Observer participation level. | Observer capability set (unprefixed), Observer tier, T1 |
| **Case Decision capability set** | The **Case Owner** governance obligations, separable from **Case Hosting** ([§12.2 Case Decision capability set](vultron-spec/conformance.md#case-decision-capability-set)). Formerly the "Authority capability set"; renamed because *authority* is reserved for the **CASE_MANAGER**'s single-writer control (ADR-0088). | Authority capability set, governance authority |
| **Case Hosting capability set** | The **Case Manager** infrastructure obligations, separable from **Case Decision** ([§12.2 Case Hosting capability set](vultron-spec/conformance.md#case-hosting-capability-set)). Ledger authority follows the **CASE_MANAGER** role the implementation holds — never its hosting location or actor name (ADR-0088). | Hosting capability set (unprefixed) |

---

## Formal Protocol Concepts

| Term | Definition | Aliases to avoid |
|------|-----------|-----------------|
| **Deterministic Finite Automaton (DFA)** | A mathematical model representing a state machine with finite states, an initial state, final states, input symbols (transitions), and transition functions; the formal foundation for RM, EM, and CS models | State machine, FSM |
| **Process** | In protocol formalism, an independent entity (Participant) maintaining its own state and communicating with other processes via messages | Actor, participant |
| **Global State** | The complete system state comprising all N participants' composite states plus all messages in flight between them | System state, protocol state |
| **Message Queue** (or **Channel**) | A FIFO buffer from Participant i to Participant j containing ordered messages; denoted C_ij in formal notation. [§2.3 Protocol Objects and Messages](vultron-spec/introduction.md#23-protocol-objects-and-messages) defines the channel as the path a message travels: inbox to inbox, routed through the CASE_MANAGER for case-scoped messages | Message buffer, transport channel |
| **Reachable State** | A state logically possible for a Participant given protocol constraints; [States](formal_protocol/states.md#unreachable-states) removes the impossible combinations, and [About the Size of the Protocol State Space](../topics/measuring_cvd/state_space_size.md) counts what remains for each role | Valid state, achievable state |
| **Unreachable State** | A state impossible due to protocol constraints (e.g., RM Start/Closed states make EM and CS irrelevant); enumerated in [States](formal_protocol/states.md#unreachable-states) | Invalid state, forbidden state |
| **Ordering Preference** | One of 12 formally-defined preferences for CVD outcomes (e.g., D ≺ P: Fix Deployed Before Public Awareness); guides protocol design | Success metric, outcome goal |
| **Avoid Surprise** | Core CVD principle embedded in protocol: participants whose state changes SHOULD send messages to other participants to minimize surprise | Transparency principle, communication imperative |

---

## RM Model Details

| Term | Definition | Aliases to avoid |
|------|-----------|-----------------|
| **Report Submission (RS)** | The only RM message that directly triggers a state change in receiver (from S → R); all other RM messages announce sender's state | Initial RM message |
| **Report Received (R)** | Initial RM state when a Report arrives; recipient must validate before transitioning to Invalid or Valid | Received state, intake state |
| **Report Valid (V)** | RM state indicating validation passed; next decision is whether to Accept or Defer | Validated state, prioritization state |
| **Report/Case Accepted (A)** | RM state indicating a Participant has committed to work on the report/case; a case-participation decision (`Join(VulnerabilityCase)`), prerequisite for sending RS to other parties | Report Accepted, in-progress state, active state |
| **Report/Case Deferred (D)** | RM state indicating a Participant has deferred further action on the report/case (parking lot); a case-participation decision (`Ignore(VulnerabilityCase)`); can transition back to Accepted if priorities change | Report Deferred, parked state, backlog state |
| **Report Closed (C)** | Final RM state; recipient may ignore all messages on closed reports (no further coordination) | Terminal state, archive state |

---

## EM Model Details

| Term | Definition | Aliases to avoid |
|------|-----------|-----------------|
| **Embargo None (N)** | EM initial state; no embargo currently in effect or agreed to | Initial state, no-embargo state |
| **Embargo Proposed (P)** | EM state indicating one or more embargo proposals under negotiation | Pending state, negotiation state |
| **Embargo Active (A)** | EM state indicating embargo is in effect across all participants; only one per case | Effective state, in-force state |
| **Embargo Revise (R)** | EM state indicating active embargo with revision proposal pending; active embargo remains in force until revision accepted. The Vultron Protocol Specification names this state *Revised* ([§7.1 States](vultron-spec/tracking-models.md#71-states)); the process-model pages keep *Revise* so that the capital gives the shorthand R | Renegotiation state, revision-pending state |
| **Embargo eXited (X)** | EM terminal state after embargo terminates (by expiration, early termination, or public disclosure). The Vultron Protocol Specification names this state *Exited* ([§7.1 States](vultron-spec/tracking-models.md#71-states)); the process-model pages keep *eXited* so that the capital gives the shorthand X | Expired state, terminated state |
| **Embargo Proposal (EP)** | EM message type proposing embargo terms (e.g., expiration date) | Embargo offer |
| **Embargo Termination (ET)** | EM message type terminating embargo immediately; has immediate effect regardless of other pending messages | Embargo end, embargo expiration |
| **Embargo Grammar** | Regular expression `(p*r)*(pa(p*r)*(pa)?t)?` describing all valid EM state transition sequences | DFA language, EM language |

---

## CS Model Details

| Term | Definition | Aliases to avoid |
|------|-----------|-----------------|
| **Vendor Fix Path** | Participant-specific CS submodel tracking vendor awareness (v/V), fix readiness (f/F), fix deployment (d/D); one path per Vendor | Vendor progression, fix progression |
| **Public State** | Participant-agnostic CS submodel tracking public awareness (p/P), exploit public (x/X), attacks observed (a/A); shared across all participants | Global state, pxa state |
| **Vendor Awareness (V)** | CS event: transition from vendor unaware (v) to vendor aware (V); typically triggered by Report Submission | V event, vendor notification |
| **Fix Readiness (F)** | CS event: transition from fix not ready (f) to fix ready (F); indicates vendor has completed fix development | F event, fix development complete |
| **Fix Deployed (D)** | CS event: transition from fix not deployed (d) to fix deployed (D); indicates vendor/deployer has applied fix | D event, fix application |
| **Public Awareness (P)** | CS event: transition from public unaware (p) to public aware (P); indicates vulnerability known outside immediate parties. [§2.4 State, Embargo and Disclosure](vultron-spec/introduction.md#24-state-embargo-and-disclosure) distinguishes it from **Publication**: awareness may arise with no Participant publishing anything | P event, disclosure |
| **Exploit Public (X)** | CS event: transition from exploit not public (x) to exploit public (X); indicates exploit code publicly available | X event, exploit disclosure |
| **Attacks Observed (A)** | CS event: transition from attacks not observed (a) to attacks observed (A); indicates active exploitation in the wild | A event, active attack |
| **vfd·· notation** | Compact notation for CS states where lowercase/uppercase in each position represents specific substate (v=vendor unaware, V=aware, f=fix not ready, F=ready, etc.) | State shorthand, state code |
| **pxa notation** | Public state substates abbreviated as p/P (public aware), x/X (exploit public), a/A (attacks observed) | Public substate |
| **Ephemeral State** | CS constraint: exploit public without vulnerability public (···pX·) cannot exist; immediately resolves to ···PX· | Transient state, immediate transition |

---

## Relationships

**Protocol Structure:**

- A **Communicating Hierarchical State Machine** consists of N independent **Processes** (Participants) coordinating via message passing.
- Each **Process** maintains a **Composite State** = (**RM State**, **EM State**, **Case State**), where the **Case State** is the compound of the VFD and PXA machines.
- The **Global State** includes all **Composite States** plus message queues (**Channels**) between processes.

**State Transitions:**

- RM transitions are mostly independent; only **Report Submission (RS)** directly changes receiver RM state.
- EM transitions are global; exactly one **EM State** per case affects all participants.
- CS transitions are hybrid: **Vendor Fix Path** is per-Vendor; **Public State** is global.
- **Embargo Consent** (PEC) transitions are per-Participant and follow the EM transitions of the case.

**Message Protocol:**

- **State-Change Notification**: each state transition SHOULD emit a **Message Type** to other participants.
- RM messages: RS is unique (triggers receiver state); others announce sender status (RI, RV, RD, RA, RC).
- EM messages: all trigger global EM state updates (EP, EA, ER, EV, EC, EJ, ET).
- CS messages: announce **CS Events** (CV, CF, CD, CP, CX, CA).
- All valid messages receive acknowledgments (RK, EK, CK, GK); errors generate (RE, EE, CE, GE).

**Constraints:**

- **Precondition**: Participant must be in RM Accepted (A) to send RS.
- **Single Embargo**: exactly one **Embargo Active (A)** per case.
- **Public Embargo Boundary**: no EM negotiation when **Public Awareness (P)** or **Exploit Public (X)** or **Attacks Observed (A)** occur.
- **Reachable States**: most theoretical **Composite States** are **Unreachable** due to constraints; [About the Size of the Protocol State Space](../topics/measuring_cvd/state_space_size.md) gives the counts.

**Success Metrics:**

- 12 **Ordering Preferences** define CVD success; **Embargo Active** is primary mechanism for achieving top preferences (D ≺ P, F ≺ P).

**Architecture Integration:**

- A **Port** is implemented by one or more **Adapters**.
- **Inbound Activities** are matched by **ActivityPatterns** to extract **MessageSemantics**, which is not a formal protocol **Message Type**: the two are many-to-many (ADR-0083).
- **Outbound Activities** are constructed by **Factory Functions** (not by core calling `from_core()`).
- **CasePersistence** and **CaseOutboxPersistence** replace the broad **DataLayer** interface for core use cases.
- **Rehydration** converts raw persisted dicts (from **DataLayer**) into typed domain objects.
- A **Participant** has zero or more **CVDRoles** (represented as `list[CVDRole]`).
- A Behavior Tree (**BT**) **Node** reads from and writes to the **Blackboard** and may emit **Outbound Activities**.

**Call-Out Points and Capability Shapes:**

- A **Fuzzer Node** in the simulator is the placeholder form of a **Call-Out Point**.
- A **Call-Out Point** is fulfilled in production by a **capability** of the appropriate **capability shape**.
- An **Evaluator** records a domain decision; a **Retriever** fetches external data; a **Composer** generates content; an **Actuator** fires a side effect in an external system. These four are the **capability shapes**.
- A **Sentinel** monitors a condition and fires a trigger when the condition is met. It answers no **Call-Out Point**, so it is a call-in pattern rather than a **capability shape**.
- An **Advisory Review Decision** is produced by a **Reviewer** (an Evaluator **capability**) and determines whether an **Advisory** draft requires revision before the BT submits it.

**Status and Dimensions:**

- A **CaseStatus** is composed of one or more **Dimension Objects** (one per state machine: RM, EM, VFD, PXA).
- A **ParticipantStatus** contains an RM **Dimension Object** and an **Embargo Consent** state.
- **Dimension Objects** are immutable; each state transition produces a new **Dimension Object** rather than mutating the existing one.

---

## Flagged Ambiguities

1. **"State" (multiple meanings)**:
    - The **Case State (CS)** — the six-dimensional VfDpxa lattice, 32 compound states ([§8.3 Case State as a Compound Tuple](vultron-spec/tracking-models.md#83-case-state-as-a-compound-tuple)).
    - An **EM State** — a single Embargo Management state (None, Proposed, Active, Revise, eXited).
    - An **RM State** — a single Report Management state (Start, Received, Invalid, Valid, Accepted, Deferred, Closed).
    - A **Composite State** — a participant's complete state tuple in the formal protocol, (q^rm, q^em, q^cs).
    - A **Case Status** — the case's shared, canonical state as [§2.3 Protocol Objects and Messages](vultron-spec/introduction.md#23-protocol-objects-and-messages) defines it.
    - **Recommendation**: Always qualify: "Case State lattice," "EM State," "RM State," "Composite State," or "Case Status."

2. **"Message" vs. "Activity" vs. "Message Type"**:
    - A **Message Type** is a formal protocol category (e.g., RS, EP, CV) from the 28-message set.
    - An **Activity** is the ActivityStreams 2.0 JavaScript Object Notation (JSON) wire format carrying a **Message Type**.
    - A **State-Change Notification** is the abstract principle that every transition should generate a message.
    - **Recommendation**: Use "Message Type" for protocol formalism; "Activity" for wire transport; "Semantic Type" for the extracted intent.

3. **"Participant" vs. "Actor" vs. "Process"**:
    - An **Actor** is any URI-identified federated peer (federation concept).
    - A **Participant** is an **Actor** actively engaged in a specific **Case**.
    - A **Process** is a formal state machine in the mathematical protocol specification.
    - **Recommendation**: Use "Actor" for federation; "Participant" for case-specific engagement; "Process" for formal protocol math.

4. **"Reachable" vs. "Valid"**:
    - **Reachable** = logically possible given protocol constraints (state might not occur in practice but conforms to rules).
    - **Valid** = permissible per protocol rules (state satisfies all constraints).
    - **Unreachable** = impossible due to hard constraints (violates protocol rules).
    - **Recommendation**: Use "Reachable State" for logical possibility; "Valid Transition" for rule compliance.

5. **"CS Event" vs. "Message Type"**:
    - A **CS Event** (V, F, D, P, X, A) is a formal state transition in the **Case State** lattice.
    - A **Message Type** (CV, CF, CD, CP, CX, CA) is the protocol message announcing that event.
    - Not all **CS Events** are announced (e.g., a Vendor may internally transition Vfd→VFd without sending CF).
    - **Recommendation**: Use "CS Event" for state transitions; "Message Type" for protocol announcements.

6. **"Activity" direction** — The term **Activity** is used for both **Inbound** and **Outbound**. Both follow the same ActivityStreams 2.0 format, but the context (inbox vs. outbox, received vs. constructed) determines meaning.
    - **Recommendation**: Always qualify as "inbound **Activity**" or "outbound **Activity**" when direction matters.

7. **"Factory" scope** — The term **Factory** can mean:
    - The set of **Factory Functions** in the `vultron/wire/as2/factories/` package (the public API)
    - A single **Factory Function** (e.g., `create_report()`)
    - Never use "factory" to mean "the place where activities are made" — always say **Factory Function** or **factories package**.

8. **"Port" (hexagonal vs. TCP)** — In this domain, **Port** always means a hexagonal architecture interface contract, never a TCP port. No TCP concepts are in scope.

9. **"Deprecated" methods** — `get()` and `by_type()` on **DataLayer** are called "deprecated" but still exist in the codebase. This means they are marked for removal and are being gradually replaced by **Narrow Ports** (**CasePersistence**, **CaseOutboxPersistence**) and **Rehydration**. "Deprecated" ≠ "removed yet."

10. **"Narrow" vs. "broad" ports** — A **Narrow Port** is small, typed, domain-specific (e.g., `CasePersistence` with `read_by_id()`, `list_by_status()`). A broad port is generic and untyped (e.g., `DataLayer` with `get(table, id)`, `by_type(type)`). The goal is to replace broad ports with **Narrow Ports** to improve type safety and reduce coupling.

11. **"Report" vs. "Case"**:
    - A **Report** is a one-time vulnerability notification from a **Reporter**.
    - A **Case** is the ongoing coordination container with state machines and participants.
    - Multiple **Reports** may consolidate into one **Case**; one **Report** may split into multiple **Cases**.
    - **Recommendation**: "Report" = inbound notification; "Case" = coordination entity with state machines.

12. **"Embargo" vs. "Embargo Consent"**:
    - An **Embargo** is a shared agreement (one per **Case**) that all parties will not disclose until a certain date.
    - **Embargo Consent** is each **Participant**'s individual acceptance or rejection of that embargo.
    - **Recommendation**: If discussing terms/dates, say "Embargo"; if discussing one party's stance, say "Embargo Consent".

13. **"Case Owner" vs. "Case Manager" (role) vs. "Case Actor" (prototype identity) vs. "case actor service"**:
    - A **Case Owner** is a human **Participant** (e.g., Reporter) with a **CVDRole.CASE_OWNER** value; the decision-maker and administrator of the **Case**.
    - **Case Manager** (`CVDRole.CASE_MANAGER`) is the **role** that carries single-writer authority over the canonical case ledger. It is the *only* protocol-salient signal of authority: an actor is the authority for a case **iff** it holds this role in the case roster.
    - A **Case Actor** is the *concrete actor the prototype/demo implements to hold `CASE_MANAGER`* — a specific identity labeled `case-actor`. It is **not** a synonym for the authority and **not** an identity to match on: its name and URL are cosmetic and carry no protocol meaning (ADR-0088).
    - A **case actor service** is the provisioning endpoint (`case_actor_service_url`) that spawns `case-actor` identities — a hosting concern, not the authority.
    - **Recommendation**: In protocol-normative prose, name the authority **"the CASE_MANAGER"** (the role holder), never "the CaseActor". Reserve **"CaseActor"** for the prototype/demo actor that enacts the role, and **"case actor service"** for the provisioning endpoint. Never determine authority, recognition, or routing from the `case-actor` name or URL shape, and never compare `actor_id` against a computed `case_actor_id` to decide authority — gate on the role (CM-24-004, CM-02-011).

14. **"Participant Case Replica" vs. "Case State"**:
    - A **Participant Case Replica** is a local copy of case state on a participant's node; must be seeded via **Trust Bootstrap** and maintain **Eventual Consistency** with the **CASE_MANAGER**'s authoritative state.
    - **Case State (CS)** is the formal six-dimensional state model (VfDpxa lattice) tracking vulnerability awareness and readiness.
    - **Recommendation**: Use "Participant Case Replica" for participant-local state copies; "Case State" for the formal model.

15. **"CVDRole" vs. "CVDRolesFlag"**:
    - **CVDRole** is a StrEnum (string enum) representing individual, atomic roles; participants hold zero or more roles as `list[CVDRole]`; this is the **preferred** representation for all new code.
    - **CVDRolesFlag** is a legacy Flag enum (bitmask) used only by the `vultron.bt` simulator layer; it existed before the migration to list-based roles and is retained for backward compatibility only.
    - **Recommendation**: Always use `list[CVDRole]` in new code; never use **CVDRolesFlag** outside the `vultron.bt` simulator. When discussing roles, say "CVDRole" or "role list," never "CVDRoles" (plural, deprecated name).

16. **"Call-Out Point" vs. "Fuzzer Node"**:
    - A **Call-Out Point** is the abstract concept — a BT location requiring external input.
    - A **Fuzzer Node** is the concrete simulator-layer stub that occupies that location until a real **capability** is wired in.
    - **Recommendation**: Use "**Call-Out Point**" when discussing design or integration seams; use "**Fuzzer Node**" only when discussing the simulator implementation.

17. **"Composer" vs. "Actuator"** (capability shape classification):
    - A **Composer** reads context, runs a generation process, and writes a content artifact to the blackboard (e.g., advisory draft text).
    - An **Actuator** receives a trigger, calls an external system, and confirms the side effect; no artifact is placed on the blackboard.
    - Misclassification risk: nodes that "do something" to an external system look like Composers if you only notice they dispatch outbound calls. The discriminator is whether a content artifact lands on the blackboard. If not, it is an **Actuator** capability shape.
    - **Recommendation**: Before classifying a node as Composer, verify it writes a content artifact to the blackboard. If the only output is a SUCCESS/FAILURE confirming an external side effect, it is an **Actuator** capability shape.

18. **"Coordination Agent" vs. "Capability shape"**:
    - A **Capability shape** is the current term for the abstract interface contract at a call-out point (Evaluator, Retriever, Composer, Actuator).
    - **Coordination Agent** was the previous term. It is deprecated because "agent" has acquired connotations of large language model (LLM)-based autonomous systems, which was not the original intent.
    - **Recommendation**: Use "capability shape" in all new text. When reading older code or docs, treat "Coordination Agent" as a synonym for "capability shape."

19. **"Dimension Object" vs. "status field"**:
    - A **Dimension Object** (per ADR-0036) is an immutable `BaseModel` containing the state of one machine; it is a first-class structured type, not a flat field.
    - "Status field" is informal language that may mean a flat scalar (`rmState: "ACCEPTED"`) or a **Dimension Object** (`rm: {"state": "ACCEPTED"}`); both appear in real ledger snapshots.
    - **Recommendation**: Say "**Dimension Object**" when referring to the structured sub-model; say "flat legacy field" when referring to the pre-ADR-0036 serialization. When extracting state from JSONL, probe both shapes (see 2026-07-22 learning on three nesting shapes).

20. **"Revise" / "eXited" vs. "Revised" / "Exited"** (EM state names):
    - The Vultron Protocol Specification names two EM states *Revised* and *Exited* ([§7.1 States](vultron-spec/tracking-models.md#71-states)).
    - The process-model pages and the `EM` enum name the same states *Revise* and *eXited*, so that the capital letter gives the shorthand R and X.
    - **Recommendation**: Both sets of names are correct and name the same states. Follow the convention of the page you are on; do not "correct" one to the other.

21. **"Vendor" vs. "Supplier", "Deployer" vs. "User"** (standards alignment):
    - SSVC version 2 and later calls the **Vendor** role *Supplier*; ISO/IEC 29147 and ISO/IEC 30111 call the **Deployer** role *User*.
    - This documentation follows the *CERT Guide to CVD* and uses **Vendor** and **Deployer**; the standards' names are recorded here so that a reader mapping one vocabulary onto the other knows they are the same roles.
    - **Recommendation**: Write **Vendor** and **Deployer** in Vultron prose; mention *Supplier* or *User* only when citing the standard that uses it.

---

## Reference Implementation Vocabulary

The sections below name the classes, ports, and patterns of the Python reference implementation in this repository.
They are for the people who build against the implementation or work on it; the protocol itself does not depend on any of them.
The [Concept Taxonomy](vultron-taxonomy.md) explains the boundary: `vultron/core/` implements `vultron-core`, and is not the same thing.

---

## Hexagonal Architecture & Abstraction

| Term | Definition | Aliases to avoid |
|------|-----------|-----------------|
| **Port** | An interface contract that abstracts a capability; core modules depend on ports, not concrete implementations | Interface, contract, API |
| **Adapter** | A concrete implementation of a port; lives in the adapter layer and translates between external systems and the core domain | Implementation, provider |
| **Narrow Port** | A port with a small, typed, domain-specific interface (e.g., `CasePersistence`, `CaseOutboxPersistence`, `ActivityTranslator`) designed for a single responsibility; replaces broad generic ports for improved type safety and testability | Constrained port, domain port, semantic port |
| **Broad Port** | A port with a large, generic, untyped interface (e.g., legacy `DataLayer` with `get(table, id)`, `by_type(type)`) that couples core to lower-level storage details; marked for replacement by **Narrow Ports** | Generic port, legacy port |
| **Driven Port** | A port that exposes an outbound dependency; core calls it to reach adapters (e.g., `DataLayer`, `ActivityTranslator`) | Dependency port, outbound port |
| **Driving Port** | A port that exposes an inbound boundary; adapters call it to reach core (e.g., use cases, handlers) | Inbound port, entry point |
| **Hexagonal Architecture** | Layered design where core business logic has no imports from wire format, adapter, or external framework layers | Ports and adapters, onion architecture |
| **Validate-at-Edge** | The architectural principle that loose wire-layer types are promoted to strict core types at system entry boundaries; core logic operates on guaranteed-field types rather than defensively guarding every field (ADR-0032). | Edge validation, boundary validation |
| **Two-Branch Hierarchy** | *Retired by ADR-0099.* The former pattern where domain objects existed in two structurally incompatible shapes sharing a common base class: the **core branch** (strict, required-field constraints) and the **wire branch** (lenient, permitting loose AS2 fields). ADR-0099 replaced it with **one object model**: the classes under `vultron/core/models/` are the model and AS2 is a serialization of them. The shared base is gone, core now has two roots of its own (`CoreRecord` and `CoreObject`), and a domain type's `as_*` name is an alias of its core class. The wire classes that remain (`as_Base` and its subclasses) inherit nothing from core. | Domain/wire split, core/wire hierarchy |

---

## Activity & Wire Format

| Term | Definition | Aliases to avoid |
|------|-----------|-----------------|
| **Activity** | Defined in [§2.3 Protocol Objects and Messages](vultron-spec/introduction.md#23-protocol-objects-and-messages): the wire form of a Vultron message, an ActivityStreams 2.0 Activity; represents a state change notification (Create, Accept, Reject, etc.) | Message, notification, AS2 object |
| **Inbound Activity** | An **Activity** received at the inbox from a remote actor; must be parsed, pattern-matched, and semantically extracted | Received message |
| **Outbound Activity** | An **Activity** constructed by a use case and queued in an outbox for delivery to remote actors; MUST include full inline objects and a non-empty `to:` field per **Actor Knowledge Model** | Sent message, outgoing activity |
| **ActivityPattern** | A template for matching an inbound **Activity** structure; used to extract semantic intent (e.g., a `CreateReport` vs an `AcceptInvite`) | Matcher, pattern, discriminator |
| **Semantic Extraction** | The process of mapping an inbound **Activity** structure to a domain-level **MessageSemantics** enum value | Pattern matching, dispatch, intent detection |
| **MessageSemantics** | A domain-level enum of message intents (e.g., `CREATE_REPORT`, `ACCEPT_INVITE_TO_EMBARGO_ON_CASE`) | Message type, semantic type, intent |
| **Factory Function** | A public, type-safe constructor function that builds outbound **Activities**; ensures validation and returns plain AS2 types; located in `vultron/wire/as2/factories/` | Activity constructor, builder |
| **from_core()** / **to_core()** | Projection methods that translate between a domain object and its wire counterpart. Historically defined on the wire vocabulary class and callable only from adapters, never from core use cases (ARCH-01-001). ADR-0082 was going to relocate projection off the wire classes into adapter-side translator modules driven by a core↔wire **Pairing Registry** (ARCH-12-005); **ADR-0099 cancels that relocation** — with one object model there is nothing to translate, so these methods are deleted along with the paired classes rather than moved. | Wire constructor, projection method |
| **Pairing Registry** | **Canceled by ADR-0099**; never built. ADR-0082 (#2937) proposed it as the single declarative statement of core↔wire type correspondence (ARCH-23-001). A pairing registry exists to reconcile two classes that mean the same thing, and ADR-0099 deletes the second class instead — so there is no pair to record. Do not revive #2937. It replaces four undeclared sources — the bare-*key* collision between `VOCABULARY` and `CORE_VOCABULARY`, `_WIRE_ACTOR_TO_CORE`, `_NORMALIZE_WIRE_TO_CORE`, and the three chained registries — after which resolving a wire counterpart by key coincidence is forbidden. | Core-wire pairing, translation registry |
| **Activity Translator** (port) | A narrow driven port that core use cases call to construct outbound **Activities** from domain objects; implemented by adapters with wire imports, preserving core layer isolation (inverse of `from_core()` anti-pattern) | Wire adapter port, activity constructor port |
| **WireParsePort** | **Rejected by ADR-0099**; never built. ADR-0082 (#2938) proposed it as the inbound counterpart to `WireRenderPort` — a driven port core calls to project a received wire object to its core form, replacing the `getattr(obj, "to_core", None)` duck-typing that lets core reach for a wire capability without an import the ratchet can see. ADR-0099 rejected it on three grounds: it does not exist, its own AC-2 requires the canceled **Pairing Registry**, and its single-method shape has no store access so it could only fabricate placeholders. `rehydrate()` owns ID-to-object materialization instead (VM-06-007). | Wire parse port, inbound translation port |

---

## Persistence & Data Access

| Term | Definition | Aliases to avoid |
|------|-----------|-----------------|
| **DataLayer** | A broad, generic persistence port that core modules use to store and retrieve case data; provides raw `dict` access | Persistence, storage, database |
| **CasePersistence** | A narrow, typed persistence port for case-specific queries; replaces broad `get()`/`by_type()` with domain-specific methods like `read_by_id()` and `list_by_status()` | Case DAO, case repository |
| **CaseOutboxPersistence** | A narrow, typed persistence port for outbox (outbound activity queue) queries; separate from case data | Outbox DAO, outbox repository |
| **Auto-Rehydration** | The design contract that `dl.read()` and `dl.list_objects()` MUST return fully typed, rehydrated domain objects (never raw storage records or dehydrated string references), eliminating the need for `model_validate()` coercion in use cases | Automatic deserialization, typed retrieval |
| **Rehydration** | The process of deserializing raw persisted records (dicts) into typed domain objects (Pydantic models) | Deserialization, model coercion, casting |
| **Compatibility Method** | A deprecated method (`get()`, `by_type()`) still present for backward compatibility but marked for removal | Escape hatch, legacy method |
| **Actor Knowledge Model** | The architectural invariant that an **Actor**'s knowledge of the world is bounded only by what it has **received** via AS2 **Activities**; recipients cannot access senders' DataLayers; therefore, all outbound **Activities** MUST include full inline objects, never bare URIs | Knowledge boundary, isolation invariant |
| **Bare Object URI** | An anti-pattern in outbound **Activities** where an object is referenced as a bare string URI (e.g., `object_="urn:uuid:abc123"`) instead of a full inline object; causes recipient pattern-matching failure because the recipient's DataLayer has no record of the referenced object | String reference, bare ID |
| **Dead Letter Record** | A persistence record created when an inbound activity's `object_` URI cannot be resolved after rehydration; stored for administrative review and retry rather than raising an error. | Dead letter queue entry, failed delivery record |
| **OfferRecord** | A core state record capturing domain facts from a received `Offer(VulnerabilityReport)` activity; stored so core can recover these facts without re-reading the wire Activity. | — |
| **ReportCaseLink** | A persisted mapping from a vulnerability report to its associated case replica. Stores the trust anchors established during **Trust Bootstrap** — specifically, which actor the report was originally submitted to and which actor holds `CASE_MANAGER` (is authoritative) for the resulting case — so that subsequent messages can be validated against those known-good identities. | — |
| **PendingCreateCaseActivity** | A durable marker written after `Accept(CaseProposal)` is sent but before `Create(VulnerabilityCase)` delivery; enables retry if the process crashes between the two sends. | — |
| **PendingCreationTimeRevisionRelay** | A durable marker the `CASE_MANAGER` writes when case creation registers an embargo revision it still owes the other party as an `Invite(EmbargoEvent)`; deleted once the relay is sent or no longer needed, and retried at startup if the relay failed (EP-04-011). | — |
| **Outbox Terminal State** | The condition reached when the delivery mechanism exhausts its retry budget for an outbound Activity; the Activity is moved to the dead-letter store and no further delivery is attempted. | Delivery failure, max retries exceeded |
| **LedgerGapBuffer** | A per-case in-memory buffer for out-of-order `Announce(CaseLedgerEntry)` activities; holds forward-gap entries until their hash-chain predecessor arrives, enabling order-independent convergence (SYNC-10-004). | Gap buffer, out-of-order buffer |
| **PendingAssertionStore** | An in-memory store tracking outbound log-entry assertions emitted but not yet confirmed by a canonical `Announce(CaseLedgerEntry)` round-trip; suppresses duplicate near-term re-emits within a configurable timeout window (SYNC-11). | — |
| **ProtocolPair** | A value type tracking whether a protocol request/reply handshake (e.g., `Offer` → `Accept/Reject`) is still open or closed; used by both durable ledger queries and ephemeral assertion suppression. | Handshake state, open request |

---

## Behavior Trees

| Term | Definition | Aliases to avoid |
|------|-----------|-----------------|
| **BT** | A Behavior Tree; a state machine implementation using py_trees that orchestrates domain logic and protocol events | State machine, tree, orchestrator |
| **Node** | A component in a **BT** that extends `Behavior` and implements a single domain action (e.g., create a participant, attach a note) | Action, task |
| **Blackboard** | Global shared state storage for **BT** nodes to read/write data during execution; keys use `{noun}_{id_segment}` format to avoid py_trees path parsing issues | Shared memory, context |
| **BTTestScenario** | A deep-module test harness that eliminates boilerplate setup; allows BT node tests to be written without repeating blackboard initialization | Test fixture, test helper |
| **Trunk-Removed Branches Model** | The prototype BT architecture that mirrors the canonical simulation BT structure by exposing individual subtrees as event-driven use cases triggered by incoming **Activities**, rather than a continuous-tick monolithic root tree | Branched event model, handler-first BTs |
| **Protocol-Significant Behavior** | Any action that affects protocol-observable state (emitting an **Activity**, transitioning RM/EM/CS, cascading consequences); MUST be implemented as BT nodes/subtrees, never as procedural code outside the tree | Domain logic, tree-resident behavior |
| **Cascading Consequences** | Automated downstream behaviors triggered by primary protocol events via BT subtrees; examples include submit-report → case creation → participant setup → embargo initialization → notifications (anti-pattern: post-BT procedural calls) | Event cascade, automation chain |
| **Call-Out Point** | A BT node location where automated protocol execution cannot proceed without external input from a human, skill, or LLM agent; implemented as a **Fuzzer Node** stub in the simulator layer | Decision point, human-in-the-loop seam |
| **Fuzzer Node** | A stub BT node in the legacy simulation (`vultron/bt/`) that stands in for unimplemented real-world decision logic by returning probabilistic SUCCESS/FAILURE; each represents a **Call-Out Point** awaiting a real **capability** | Stub node, random node |
| **Capability shape** | One of four abstract interface contracts that characterize how a **Call-Out Point** interacts with the protocol; describes the interaction pattern without prescribing the implementation. A concrete **capability** may be a function, a human workflow, or an LLM agent. The four shapes are **Evaluator**, **Retriever**, **Composer**, and **Actuator**, defined in [Annex G.1 The Four Capability Shapes in the specification](vultron-spec/annex-g-capability-shapes.md#g1-the-four-capability-shapes). The **Sentinel** pattern is not a capability shape — it is a call-in pattern (ADR-0097). See ADR-0024 and ADR-0097. | Coordination Agent (deprecated), "the five shapes" |
| **Capability** | A specific named call-out point with its own blackboard contract (input keys, output keys, and types); implements a **capability shape** for a particular domain context. Example: `EvaluateReportCredibility` is an Evaluator capability. | Call-out node, capability instance |
| **Capability implementation** | The factory backend fulfilling a **capability** at runtime; may be a Python function, a human workflow, a rules engine, or an LLM agent. The implementation choice is made at deployment time, not at design time. | Backend, factory backend |
| **Sentinel** | A **call-in integration pattern** (not a **capability shape**): a process that monitors a condition over time and, when it is met, acts on its own initiative. The protocol never consults it, so it has no **Call-Out Point**, no blackboard contract, and no backend factory — which is why it sits outside the capability-shape taxonomy (ADR-0097, BT-18-013). The discriminator is *who initiates*, not whether the information is external: a Sentinel may be a case **Participant** (typically holding **Observer**) that reads case state via `Announce(CaseLedgerEntry)` and acts by sending protocol messages, or operator-side machinery with no case identity that calls one actor's trigger endpoints. Its design questions belong to Agentic Participants (#2450); the issues themselves remain under the Capability Shapes epic (#1147). | Guard agent, check agent, "Sentinel capability", "Sentinel shape", "external-only monitor" |
| **Evaluator** | A **capability shape** that receives a situation and returns a structured recommendation or decision (e.g., `ReviewAdvisoryDraft`); its output gates downstream BT execution | Decision agent, reviewer agent |
| **Retriever** | A **capability shape** that receives a query and returns structured facts from an external source (e.g., CVE ID lookup, SSVC scoring); also used for binary yes/no external queries | Fetch agent, lookup agent |
| **Composer** | A **capability shape** that receives context and generates a new content artifact (e.g., drafting advisory text); output is written to the blackboard | Generator agent, authoring agent |
| **Actuator** | A **capability shape** that receives a trigger and invokes an external system to cause a side effect (notification dispatch, state write, queue mutation, API call); returns SUCCESS when the side effect is confirmed, FAILURE otherwise; produces no content artifact | Side-effect agent, executor |
| **StatusAdoptionGate** | A BT authorization gate that determines whether a received **CaseStatus** update should be adopted by the receiving actor; guards the `add_participant_status_tree` path for received-side status canonicalization (ADR-0046). | Seam 1, StatusUpdateGuard |
| **EmbargoTeardownAuthorizationGate** | A BT authorization gate that determines whether an incoming status update should trigger **Embargo** teardown; guards the `add_case_status_tree` path alongside `ThreatTerminationBranchNode` for received-side CaseStatus canonicalization (ADR-0046). | Seam 2, SideEffectsGuard |
| **GuardedCommit** | A Behavior Tree subtree pattern that gates case ledger entry persistence on a CASE_MANAGER role check, ensuring only the actor holding the CASE_MANAGER role commits entries to the canonical log. | — |
| **Intake** | The first stage of a received-side Behavior Tree: one shared node, supplied by `create_receive_activity_tree`, that idempotently archives the received **Activity** exactly as received, as a `ReceivedActivityRecord` keyed by an id the receiver derives (never the sender's id), before any guard, commit, or effect runs (ADR-0111, CLP-10-017). It decides nothing, ledgers nothing, and writes no core record: an object carried inline in the activity is a message shaped like that object, and the record core keeps is written by an effect node from the event's copy after the guards. Not the RM **Report Received (R)** state, for which "intake state" is an alias to avoid. | Intake stage, store-what-arrived step, receipt record |
| **Idempotency Guard** | A Behavior Tree precondition node that detects a duplicate inbound Activity and short-circuits processing silently, ensuring that receiving the same Activity more than once has no additional effect on case state. | Duplicate check, dedup guard |
| **Causal Gate** | A precondition that blocks a protocol step until a specific prior event has provably occurred; ensures steps execute in causal order rather than relying on timing assumptions. Commonly used in demo scenario checks but applicable wherever causal ordering must be enforced (ADR-0058). | Causal check, timing guard |

---

## Use-Case Layer

| Term | Definition | Aliases to avoid |
|------|-----------|-----------------|
| **VultronEvent** | The base domain event type for received-side use cases; carries extracted semantic information from an inbound wire Activity and drives the dispatcher into the appropriate Behavior Tree handler. Contrast with **TriggerRequest**, which represents local actor intent rather than a received remote notification. | Event, handler event |
| **TriggerRequest** | The base request type for trigger-side use cases, representing a local actor's intent to initiate a protocol action (e.g., propose an embargo, submit a report). Contrast with **VultronEvent**, which represents an inbound remote notification rather than local intent. | Trigger, use case request |
| **UseCaseResult** | The typed return envelope from a use-case execution; communicates outcome and any emitted Activities back to the driving adapter. Has two subtypes: **HandlerResult** (received-side) and **TriggerResult** (trigger-side) (ADR-0040). Defined in `vultron/core/models/use_case_result.py`; every received-side, query and trigger-side use case returns a subtype of it (ADR-0110, #3831). | Use case output, result envelope |
| **HandlerResult** | The **UseCaseResult** subtype returned by received-side use cases (processing an inbound Activity); carries a **HandlerDisposition** and a reason, which is required when refused, forbidden when applied, and optional when skipped or deferred. Its purpose is to route the handler's own verdict to **InboxOutcome**, which is otherwise assembled from behavior-tree bookkeeping and cannot see it (ADR-0095, #2255). Every received handler returns one, with the disposition its own verdict warrants; the dispatcher carries it to **InboxOutcome**, whose status the inbox pipeline derives from it (#3373). | Handler output, received-side result |
| **HandlerDisposition** | The closed `StrEnum` vocabulary on a **HandlerResult**: `APPLIED` (local state changed), `SKIPPED` (correct no-op — a duplicate or otherwise idempotent re-delivery of a message the receiver was entitled to act on), `DEFERRED` (parked for later replay, as the ledger-sync buffer nodes do for an out-of-order entry), `REFUSED` (inbound assertion rejected, including a message the receiver holds no role or addressing to act on, such as a **CASE_MANAGER**-addressed message at an actor that is not the case's CASE_MANAGER; HP-01-005). `APPLIED` and `SKIPPED` both map to `InboxOutcome.status == "processed"`; `DEFERRED` maps to `"deferred"` and `REFUSED` to `"rejected"`. `deferred` has two producers: `DeferCheckNode` before dispatch, for missing case context, and a handler after dispatch (ADR-0095). Defined in `vultron/core/models/use_case_result.py`. | Handler status, handler outcome |
| **TriggerResult** | The fieldless **UseCaseResult** subtype at the root of the trigger-side result hierarchy in `vultron/core/models/use_case_result.py` (ADR-0110). Each trigger use case returns the subtype whose fields are exactly its verb's response-body keys: `ActivityResult` (`activity`, `emitting_actor_id`) with `NoteResult` (`+ note`) and `CaseResult` (`+ case_id`) beneath it, `StatusResult` (`activity_id`, `status_id`), `OfferResult` (`offer`), `RoleOfferResult` (`activity_id`, `activity`) and `SyncLogEntryResult` (`log_entry_id`, `entry_hash`, `log_index`, `emitting_actor_id`); every subtype forbids unknown keys (UCORG-05-005). The captured JSON payloads stay `dict`s, and the demo layer's `WireActivityResult` is the wire-typed view of the same body (UCORG-05-014). | Trigger output, trigger-side result |
| **InboxOutcome** | The typed result of `process_payload()` for one inbound payload: an `InboxOutcomeStatus` of `processed` / `deferred` / `rejected`, plus an optional context ID, activity ID and failure reason (IO-01-001…004). Once dispatch runs, the status follows the handler's **HandlerDisposition**, and a dispatch where no handler ran is never `processed` (UCORG-05-011, UCORG-05-012). It reports the **processing** verdict, which is distinct from the **acceptance** verdict the inbox endpoint answers synchronously as Hypertext Transfer Protocol (HTTP) 400 or 202 — the 202 is sent before any handler runs, so it makes no claim about processing. | Inbox result, dispatch outcome |

---

## Domain Model — CVD Coordination

| Term | Definition | Aliases to avoid |
|------|-----------|-----------------|
| **CVDRole** | A StrEnum representing individual, atomic CVD roles (FINDER *(deprecated — ADR-0078)*, REPORTER, VENDOR, DEPLOYER, COORDINATOR, OBSERVER, CASE_OWNER, CASE_MANAGER, CVE_NUMBERING_AUTHORITY); participants hold zero or more roles represented as `list[CVDRole]`; preferred representation for new code (replaces legacy bitmask) | Role value, role enum |
| **Dimension Object** | A small immutable `BaseModel` capturing the state of exactly one state machine (RM, EM, VFD, or PXA) at a point in time; replaces flat fields in `CaseStatus`/`ParticipantStatus` per ADR-0036 | Status sub-object, state fragment |
| **Advisory** | A public disclosure document summarizing a vulnerability's details, remediation, and affected parties; produced by the publication pipeline via a Draft → Review → Submit sequence | Security advisory, disclosure document, bulletin |
| **Advisory Review Decision** | A record produced by a **Reviewer** (Evaluator **capability**) capturing whether an **Advisory** draft needs revision; the `needs_revision` flag gates the BT pipeline; to block submission for any reason, the Evaluator MUST return `Status.FAILURE` (BT-18-007) | Review result, review outcome |
| **Publication Intent** | A domain object recording a participant's decision about *how* and *when* to disclose a vulnerability (e.g., which advisory platform, embargo exit condition); gates the BT publish pipeline | Disclosure intent, publish intent |
| **CVDRolesFlag** | Legacy bitmask-based Flag enum using bitwise arithmetic to represent combined roles; retained for backward compatibility with the `vultron.bt` simulator layer only; **do not use in new code** — use `list[CVDRole]` instead | Bitmask roles, legacy roles |
| **CASE_OWNER** | The **CVDRole** value marking the **Case Owner** (BTND-05-001); distinct from the **CASE_MANAGER** role, which carries single-writer authority (see **Case Manager**) | Owner role |
| **CASE_MANAGER** | The **CVDRole** value marking the **Case Manager** — the **single-writer authority** over the canonical case ledger; whichever **Participant** holds it performs ongoing case replica synchronization and manages the case on behalf of the **Case Owner** (ADR-0088). Authority derives from the role and nothing else, never from the enacting actor's name or URL. Often held alongside the COORDINATOR role (CBT-01-003); the concrete actor enacting it (a **Case Actor**) may be any Actor type though demo uses Service | Case synchronizer, "the service actor", "the CaseActor authority" |
| **Embargo Initialization** | The automatic creation of a default **Embargo** with standard terms when a **Case** is first created; includes seeding the **Case Owner** as **Participant** with an `ACCEPTED` **Embargo Consent** row for the default embargo | Default embargo creation, embargo bootstrap |
| **Role Delegation** | The protocol sequence where a **Case Owner** can offer the **CASE_MANAGER** role to another **Participant** (via **Offer** activity) and receive acceptance (via **Accept** activity); enables distributed case administration | Role handoff, role transfer |
| **VulnerabilityCase** | The canonical core domain type for a vulnerability coordination case; stores participants, reports, statuses, ledger links, and embargo state; distinct from the lifecycle-staged subtypes. | Coordination case, case object |
| **CaseParticipant** | The canonical core domain type mapping a long-lived **Actor** to a specific **Case**; carries case roles, participant statuses, and embargo consent state. Because an Actor may participate in many Cases with different roles and statuses in each, `CaseParticipant` is the per-case binding that scopes an Actor's protocol obligations and state to a single coordination context. | Participant record, actor-case mapping |
| **VulnerabilityRecord** | A persistent identifier record for a confirmed vulnerability, carrying one or more namespace identifiers (e.g., CVE ID, CERT/CC VU#) and optional aliases. A **Case** may have multiple VulnerabilityRecords associated with it when coordination spans more than one distinct vulnerability. | Vuln record, CVE record |
| **CaseReference** | A typed external URL reference attached to a VulnerabilityCase, aligned with the CVE JSON schema reference format (e.g., `"patch"`, `"vendor-advisory"`, `"exploit"` tags). | External link, reference |

---

## Lifecycle-Staged Types

| Term | Definition | Aliases to avoid |
|------|-----------|-----------------|
| **Lifecycle-Staged Type** | A narrowed `VulnerabilityCase` subtype that enforces a specific lifecycle milestone's invariants at construction; promotes a general `VulnerabilityCase` to a more specific shape at a read boundary, making illegal field combinations unrepresentable (ADR-0033). Examples include **IncomingReport** and **EmbargoedCase**. | — |
| **IncomingReport** | A lifecycle-staged `VulnerabilityCase` subtype representing the pre-bootstrap stage: a case with at least one report but no participants assigned yet. | New report, pending case |
| **EmbargoedCase** | A lifecycle-staged `VulnerabilityCase` subtype representing the active-embargo stage: a case with a non-None active embargo and EM state ∈ {ACTIVE, REVISE}. | Active embargo case, embargo-locked case |

---

## Architecture Compliance & Violations

| Term | Definition | Aliases to avoid |
|------|-----------|-----------------|
| **ARCH-03-001** | Architectural rule: core modules MUST NOT import from the wire layer (AS2, activity constructors, wire vocab) | Architecture constraint, import rule |
| **Hexagonal Violation** | A break of the hexagonal architecture rule where core calls wire-layer constructors (e.g., `from_core()` called from use cases); must be fixed | Layer boundary break, import violation |

---

## Specification Taxonomy

| Term | Definition | Aliases to avoid |
|------|-----------|-----------------|
| **Four-Tier Spec Taxonomy** | The four-kind classification for Vultron specification files (ADR-0038): `protocol` (required for Vultron compliance in any language — wire behavior, state machine invariants, message semantics), `architecture` (implementation-independent structural guidance transferable across languages but not required for compliance — hexagonal boundaries, port/adapter patterns), `project` (specific to this codebase — Python paths, BT nodes, module organization), and `process` (how this project is run — CI config, GitHub workflow, agent conventions, spec authoring rules). Replaces a prior six-kind taxonomy. | Spec kinds, spec classification |

---

## Further Reading

- [Vultron Protocol Specification](vultron-spec/index.md) — the normative definitions of the protocol terms above, starting at [§2 Terminology](vultron-spec/introduction.md#2-terminology-ni)
- [Concept Taxonomy](vultron-taxonomy.md) — what each Vultron concept covers and excludes
- [Protocol Quick Reference](quick_reference.md) — the five state machines and the message set on one page
- [Documentation Conventions](conventions.md) — the call-out boxes and normative-page banners this documentation uses
- [Notation](notation.md) — the mathematical and diagram notation used in the formal treatment
- [Process Models](../topics/process_models/index.md) — the RM, EM, and CS models explained
- [Formal Protocol](formal_protocol/index.md) — the protocol as a communicating hierarchical state machine
- [*A State-Based Model for Multi-Party Coordinated Vulnerability Disclosure*](https://resources.sei.cmu.edu/library/asset-view.cfm?assetid=735513){:target="_blank"} (CMU/SEI-2021-SR-021) — the source of the Case State model
- [*Designing Vultron: A Protocol for Multi-Party Coordinated Vulnerability Disclosure*](https://resources.sei.cmu.edu/library/asset-view.cfm?assetid=887198){:target="_blank"} — the source of the formal protocol
- [*The CERT Guide to Coordinated Vulnerability Disclosure*](https://certcc.github.io/CERT-Guide-to-CVD){:target="_blank"} — the source of the CVD role names
