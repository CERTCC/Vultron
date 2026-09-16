### 12.3 Role Taxonomy

#### 12.3.1 Process Roles

Process roles define what an actor *does* within a case and which protocol
transitions it is authorized to drive. An actor may hold multiple process roles.

| Role | Protocol capability |
|---|---|
| Reporter | Initiates cases; drives `RS`; authoritative source of the original report |
| Vendor | Drives its own VFD transition `f→F` (fix ready, `CF`) |
| Deployer | Drives its own VFD transition `d→D` (fix deployed, `CD`) |
| Coordinator | Drives case participant management; coordinates multi-party disclosure |
| CNA | May directly assign CVE IDs; a non-CNA delegates to an external CNA service. Orthogonal to other roles — typically co-held with Coordinator or Vendor |
| Observer | Holds no drive obligations for VFD; may report PXA observations ([§12.4.2](../index.md#1242-participant-agnostic-cs-transitions-pxa)) |

**Capability prerequisites.** Every case Participant — whatever its roles — MUST
implement the Observer capability set ([§12.2](../index.md#122-capability-sets), [§12.3.3](../index.md#1233-roles-and-capability-sets-are-independent)). Role extension sets add
obligations on top of that floor; they do not substitute for it. An implementation
SHOULD verify that an actor has the capability prerequisites for a role before
completing a role assignment ([§11.1](../index.md#111-role-assignment-n)). The full capability prerequisites per
role are under active specification; see `docs/reference/vultron-taxonomy.md`
§"Open Ideas."

!!! note "Note on Reporter"
    Reporters are most often also the discoverer of the vulnerability, but
    the protocol is concerned with who reported it, not who found it. The
    identity of the original discoverer may be recorded in the report itself
    or in case Notes, but nothing in the technical protocol hinges on that
    distinction. Reporter is the protocol-salient role from first contact.

#### 12.3.2 Protocol Coordination Roles (protocol authority)

These roles confer specific protocol-layer authority and are distinct from
process roles. They describe what an actor *controls* within the protocol
machinery, not what it does in the world.

| Role | Protocol authority |
|---|---|
| Case Owner | Authoritative decision-maker for a case; status updates are treated as authoritative without requiring approval; drives shared EM transitions |
| Case Manager | AS actor performing case replica synchronization and case management on behalf of the case owner; always co-held with Coordinator |

**Delegation scenarios**: Protocol responsibilities may transfer during a case
lifecycle. For example, a Reporter who initially creates a case may delegate
coordination to a Coordinator (reporter → coordinator hand-off), or a primary
Vendor may bring in additional Vendors as the case grows. When a Case Owner
transfers ownership (via `Offer(VulnerabilityCase)` / `Accept` handshake routed
through the CASE_MANAGER), the receiving actor acquires Case Owner authority and
the associated protocol responsibilities.

!!! note "Open architectural question: key handover"
    Moving the `CASE_MANAGER` role to a different actor raises an unresolved
    key-handover question for future case-encryption designs. The question is
    stated once, at [§11.3](../index.md#113-case-ownership-transfer-n).

#### 12.3.3 Roles and Capability Sets Are Independent

A role is a position within a case. A capability set is a property of software.
Mixing them produces contradictions, so the relationship is stated explicitly:

- Every case Participant — whatever its roles — MUST implement the **Observer**
  capability set. Holding a role means having a `CaseParticipant` record, an RM
  state, and therefore tracking obligations.
- A parse-only actor is not a case Participant: it holds no role and no case owes
  it delivery.
- An implementation holding the Hosting capability set additionally hosts the
  CASE_MANAGER role. Hosting is commonly co-held with the Coordinator role, but it
  is the Hosting capability set that obliges ledger authority, not the role name.

!!! note "Observer is a participant role, not a passive state"
    An Observer role holder that is *in a case* implements the full Observer
    capability set: it has an RM state, it is subject to embargo consent, and it
    may report PXA observations. The Observer role is distinguished by holding no
    VFD drive obligations — not by being exempt from state tracking.

    Observer role admission follows the standard `Invite` / `Accept(Invite)` path.
    Role semantics are normative per ADR-0057; see the note at [§12.3.1](../index.md#1231-process-roles).
