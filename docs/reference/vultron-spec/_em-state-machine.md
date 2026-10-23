## 7. Embargo Management (EM) State Machine [N]

An embargo is an agreement among the participants of a case not to disclose the vulnerability publicly before an agreed point.
Embargo Management tracks the progress of that agreement for the case as a whole: whether one has been proposed, whether it is in force, whether it is being renegotiated, and whether it has ended.

There is exactly one embargo state per case.
It is shared case state, so only the CASE_MANAGER writes it ([§5.4.1 Single-Writer Authority](layers.md#541-single-writer-authority)).
The CASE_MANAGER does not set it directly either: it changes the case's **embargo register**, and the EM state is computed from the register ([§7.1.2 Deriving EM from the Register](tracking-models.md#712-deriving-em-from-the-register)).
Whether each individual participant has agreed to the current terms is a separate question, tracked per participant and per embargo by embargo consent ([§9 Participant Embargo Consent (PEC) State Machine](tracking-models.md#9-participant-embargo-consent-pec-state-machine-n)).

### 7.1 States

The five states below describe the case's collective position, not any one participant's, and not any one embargo's.

{% include-markdown "./includes/_em-states-table.md" %}

*None* here means no embargo is in effect **for the case**.
A participant's consent row for an embargo has a separate start state, `UNINVITED`, meaning the participant has not been asked about that embargo ([§9.1 States](tracking-models.md#91-states)).
The two can legitimately disagree: a case at Active may hold a participant whose row for the embargo in force is `INVITED`, because it has been invited to the case and has not yet accepted, or `DECLINED`.

#### 7.1.1 The Embargo Register

A case keeps one **embargo register entry** for every embargo ever proposed on it (ADR-0122).
An entry names the embargo, holds its status, and, for an activated revision, names the embargo it replaced.
Entries are appended and never removed, so the register is the case's whole embargo history, rejected and canceled proposals included.

| Status | Meaning |
|---|---|
| `PROPOSED` | An open proposal, awaiting the case owner's decision |
| `ACTIVE` | In force |
| `REJECTED` | The case owner declined the proposal |
| `SUPERSEDED` | Was in force; a revision replaced it |
| `CANCELLED` | Closed with no owner decision, because the embargo question became moot |
| `TERMINATED` | Was in force when the case's embargo ended |

`REJECTED`, `SUPERSEDED`, `CANCELLED` and `TERMINATED` are final.
Six triggers move an entry:

| Trigger | Change |
|---|---|
| `PROPOSE` | new entry → `PROPOSED` |
| `ACTIVATE` | `PROPOSED` → `ACTIVE` |
| `REJECT` | `PROPOSED` → `REJECTED` |
| `SUPERSEDE` | `ACTIVE` → `SUPERSEDED`, in the step that activates another entry |
| `TERMINATE` | `ACTIVE` → `TERMINATED`, recording what ended the embargo and, when known, why |
| `CANCEL` | `PROPOSED` → `CANCELLED`, in the step that terminates the embargo in force, or on a threat signal while no entry is `ACTIVE` |

A **register step** is the whole change one act causes, so a termination and the cancellation of every open proposal happen in one step and are checked together (EP-08-004).
Every step keeps these invariants, and a step that would break one is refused:

1. At most one entry is `ACTIVE` and at most one is `TERMINATED`, and never one of each.
2. A `SUPERSEDED` entry exists only alongside exactly one `ACTIVE` or `TERMINATED` entry.
3. No entry is `PROPOSED` while an entry is `TERMINATED`.
4. Once a step has left an entry `TERMINATED`, no later step adds or changes an entry.

A termination records two things.
What ended the embargo is `END_TIME_REACHED` or `EARLY`.
Why, when known, is a structured cause whose `kind` is `THREAT_SIGNAL` (with the signals `P`, `X` or `A`), `FIX_READY` (with the vendors whose readiness made the quorum), `FIX_DEPLOYED` or `OTHER` (EMB-13-004).
Every cause is `EARLY`, and an `END_TIME_REACHED` termination has none.
The termination message carries the what as `content` and the why as `terminationCause` (EMB-13-005).

!!! note "Register status is not EM state"
    The register statuses and the EM states share the words *proposed* and *active*, but they name different things.
    Register status `ACTIVE` is one embargo in force; EM `ACTIVE` is the case with an embargo in force and **no** revision open.
    A case whose register holds one `ACTIVE` entry and one `PROPOSED` entry is at EM *Revised*, not EM *Active*.

#### 7.1.2 Deriving EM from the Register

The case's EM state is a read of its register's statuses, never set directly (EMB-18-001):

| `ACTIVE` entries | `PROPOSED` entries | `TERMINATED` entries | EM |
|---|---|---|---|
| 0 | 0 | 0 | None |
| 0 | ≥1 | 0 | Proposed |
| 1 | 0 | 0 | Active |
| 1 | ≥1 | 0 | Revised |
| 0 | 0 | 1 | Exited |

`REJECTED`, `SUPERSEDED` and `CANCELLED` entries do not move EM.
A register that breaks an invariant matches no row, and the derivation refuses it.
The case's status carries a copy of the derived EM, stamped from the register, and a received status can report EM but never move it: an asserted EM that differs from the derived one is refused.

Because EM aggregates over every entry, the case leaves Proposed or Revised only when no proposal remains open.
Rejecting one of several open proposals leaves the others open, so EM stays where it was.
Activating one of several open proposals leaves the rest open as revisions of the embargo now in force, so EM moves to Revised rather than Active.
An `ACTIVE` entry leaves that status only when another entry supersedes it or when it is terminated, so a case that has had an embargo in force never returns to None or Proposed.

### 7.2 Transitions and Guards

Four triggers drive the machine: **propose**, **accept**, **reject** and **terminate**.
The register computes EM, and this table constrains how it may move: every register step names its EM trigger, and a step whose EM move is not in the table is refused, with nothing written (EMB-18-005, EMB-18-006, ADR-0130).
A proposal is propose, an activation is accept, a rejection, or the cancellation of open proposals with no embargo in force, is reject, and a termination is terminate.
Every transition is a change to shared case state, so the CASE_MANAGER applies it, and every replica applies the same check when it copies the step from the case ledger; a participant causes a transition by sending the corresponding message, not by writing the state itself.

{% include-markdown "../../topics/process_models/em/em_dfa_diagram.md" %}

| From | Trigger | To | Notes |
|---|---|---|---|
| None | propose | Proposed | |
| Proposed | propose | Proposed | A further proposal is added beside the open ones |
| Proposed | reject | None | The last open proposal is rejected; no terms were ever in force |
| Proposed | reject | Proposed | Another proposal is still open |
| Proposed | accept | Active | No other proposal is open |
| Proposed | accept | Revised | The other open proposals become revisions of the embargo now in force |
| Active | propose | Revised | Proposing against an active embargo opens a revision |
| Revised | propose | Revised | |
| Revised | reject | Active | The last open revision is rejected; the prior terms stand |
| Revised | reject | Revised | Another revision is still open |
| Revised | accept | Active | The revised terms replace the prior ones; no other revision is open |
| Revised | accept | Revised | The revised terms replace the prior ones; another revision is still open |
| Active | terminate | Exited | |
| Revised | terminate | Exited | Every open revision is canceled in the same step |

!!! warning "Rejecting a revision does not end the embargo"
    Reject behaves differently depending on where it arrives, and the difference is easy to get backwards.

    From **Proposed**, rejecting the last open proposal returns the case to None: no terms were ever in force, so refusing them leaves the case with no embargo.

    From **Revised**, rejecting the last open revision returns the case to **Active**, not to None.
    The case owner is refusing the *proposed change*, not the embargo.
    The previously agreed terms remain in force.
    An implementation that returns to None here silently drops an embargo that everyone still expects to hold.

**Reaching Exited.**
Exited means the embargo has been torn down at the case level.
A participant does not put the case into Exited by deciding to stop observing the embargo.
What a participant may do is withdraw its own consent, report that it intends to exit, propose a shorter embargo, or propose an earlier end date; the CASE_MANAGER then terminates the embargo and records the termination ([§11.2 Embargo Revision and Termination Cascades](interactions.md#112-embargo-revision-and-termination-cascades)).
Terminating an embargo requires Case Owner authorization by default, on the same terms as any other change to canonical case state ([§11.3 Status Adoption: The Two-Seam Model](interactions.md#113-status-adoption-the-two-seam-model)).
An embargo whose end time has passed is terminated by the CASE_MANAGER itself, with the reason `END_TIME_REACHED` (EMB-13-003).

{% include-markdown "./_oq-embargo-termination-authority.md" %}

**Embargo duration selection.**
Where several proposals are outstanding, participants SHOULD accept the shortest and propose the remainder as a revision (EP-08-001).
Other policies are also admissible: an implementation MAY defer the choice to the Case Owner, or apply its own organizational policy.
This specification does not mandate shortest-wins.

**Tacit acceptance.**
A receiver MAY publish a default embargo policy.
Where it has, a sender that submits a report without proposing terms accepts that default.

**A protocol default applies when nobody proposes anything.**
Where neither party proposes terms and the receiver has published no default, an embargo-eligible case MUST still begin with an active embargo, at a short duration fixed by the protocol rather than by either party.
The duration MUST be configurable, and MUST be no less than 72 hours and no more than 5 days.
Where the case is not embargo-eligible (the vulnerability is public, an exploit is public, or attacks are observed), no embargo is established and the case remains in *None*.

The protocol default is not a proposal: it MUST NOT take part in the shortest-wins comparison above, because a default short enough to be useful would otherwise win against every longer proposal and cap every embargo at its own length.
Nor is it a minimum: a party that proposes a shorter duration MUST get the duration it proposed.

Outside these two default paths, embargo agreement and rejection SHOULD be explicit.

### 7.3 Relationship to Embargo Consent

The two machines answer different questions.
Embargo Management says whether the *case* has an embargo.
Embargo consent ([§9 Participant Embargo Consent (PEC) State Machine](tracking-models.md#9-participant-embargo-consent-pec-state-machine-n)) says whether a given *participant* has agreed to a given embargo.
Neither determines the other, which is why both are needed.

Both read the same register.
A participant's consent rows are one per register entry, and whether it is a signatory or has lapsed is read from its rows and the register, not stored ([§9.3 Signatory and Lapsed](tracking-models.md#93-signatory-and-lapsed)).
Two register steps change who is bound; only one of them writes rows:

- **Activating a revision that ends later than the terms it replaces** binds only participants that agreed to the revision.
  A signatory to the replaced terms that has not agreed to the revision has lapsed: its agreement covered the previous, shorter terms.
  A revision that ends no later than the terms it replaces carries every signatory over, by a written `CARRY_OVER` on each of their rows for the revision.
  Proposing a revision changes no one's consent to the embargo in force.
- **Terminating the embargo** leaves no entry `ACTIVE`, so nobody is a signatory and nobody has lapsed.
  The termination writes no consent row, and every row for a final entry is frozen as it stood (CM-18-003, CM-18-016).

[§11.2 Embargo Revision and Termination Cascades](interactions.md#112-embargo-revision-and-termination-cascades) specifies both cascades.

!!! info "See also"
    - [Embargo Management Process Model](../../topics/process_models/em/index.md)
    - [Negotiating Embargoes](../../topics/process_models/em/negotiating.md)
    - [Early Termination](../../topics/process_models/em/early_termination.md)

---
