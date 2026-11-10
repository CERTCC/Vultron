---
title: Role Taxonomy Split — Position, Case Authority, Actor Standing
status: active
kind: plan
tracks:
  - "#5619"
  - "#5620"
  - "#5411"
description: >
  Migration design for ADR-0169: splitting `CVDRole` into three enums by scope,
  giving `CaseParticipant` a separate authority field, moving actor standing off
  the participant record, and making both case-creation doors claim a position.
  Records the enum membership, what moves where, which guard clause retires and
  which only gets a name, the stored- and wire-shape change, and the order the
  two issues land in.
related_specs:
  - specs/participant-role-management.yaml
  - specs/case-proposal.yaml
  - specs/case-management.yaml
  - specs/configuration.yaml
related_notes:
  - notes/participant-role-management.md
  - notes/case-joining.md
  - notes/demo-scenario-registry.md
relevant_packages:
  - vultron.enums
  - vultron.core.models
  - vultron.core.behaviors.case
  - vultron.core.use_cases.triggers
  - vultron.core.predicates
  - vultron.wire.as2.vocab.objects
---

# Role Taxonomy Split — Position, Case Authority, Actor Standing

ADR-0169 decides the split and why. This note holds the migration design that
does not fit either issue body: the membership of each set, what moves off the
participant record, which existing checks lose their reason to exist, and the
order the work lands in.

---

## Membership, and the question that decides it

Each value answers one question: is this fact about a position in a case, about
authority over a case, or about the organization?

| Set | Scope | Members |
|---|---|---|
| Case position | one case; assigned by an act in it | Reporter, Vendor, Deployer, Coordinator, Observer |
| Case authority | one case; conferred by case creation and ownership transfer | Case Owner, Case Manager |
| Actor standing | the actor, across every case | CVE Numbering Authority |

Observer is the position floor (CM-25-001), so a participant that fits no other
position holds it rather than none.

Do **not** name the third set a *capability*. The glossary already uses
`capability set` for a property of software (Case Observer, Case Decision, Case
Hosting) and `capability shape` for a behavior-tree call-out kind, and both are
deliberately kept clear of role names (ADR-0088).

The Exploit Publisher is the standing set's expected second member: the protocol
specification already constrains one in a pre-public case, with no enum value
and nowhere on a record to hold it. It is tracked separately and does not ride
along.

---

## What moves, and what stays

- **`CaseParticipant` carries positions and authority in separate fields.** Its
  stored shape and its wire form both gain a key, and the loader refuses the old
  single-list shape with a reset note. There is no compatibility read: the
  project breaks stored shapes rather than carrying both.
- **Actor standing never reaches a participant record.** It lives on the actor,
  because a copy on the participant would be a stale copy of a fact the actor
  owns (AKM-05-005). Its one reader, `has_cna_role` by way of
  `assign_cve_id_tree`, already asks the question of the executing actor's own
  roles, so it keeps asking the same question against the new type.
- **The role-read API keeps its shape.** `roles`, `has_role`, `add_role` and
  `remove_role` continue to mean positions (PRM-01, PRM-02); authority gets its
  own accessors rather than widening theirs, so no caller silently starts
  reading both.

---

## One check retires; the others stay

The authority pair has one home, `AUTHORITY_ROLES` in `vultron/enums/roles.py`.
Three checks read it: `RoleOfferAdmissibleNode` (through its `UNOFFERABLE_ROLES`
alias), the suggest-actor guards that refuse a suggestion or Accept naming
either role (CM-20-008), and the trigger bodies that refuse to build one
(CM-20-009). `PROTECTED_ROLES` still hard-codes the pair under its own name.
Only one of these checks is a guard the split makes pointless. Do not read them
as a matched set.

**Stays: the CM-20-008 and CM-20-009 checks.** `suggestedRoles` is a wire
string list, so a suggestion can still name an authority role after the split,
and the edge must still refuse it. When the split lands, point them at the new
authority enum. Retiring `UNOFFERABLE_ROLES` must not delete `AUTHORITY_ROLES`.

**Retires: `RoleOfferAdmissibleNode`'s refusal of an Offer naming Case Owner
or Case Manager**, with the `UNOFFERABLE_ROLES` alias behind it. A role
Offer is typed to positions, so it cannot name authority (CM-33-003). Retire
that clause, not the node: its other clauses stay (CM-33-003), including the
one that refuses an Offer carrying no readable role and never reads a missing
role as a default. That clause survives precisely because the wire
form still carries a string, so an unparseable value still has to be refused
at the edge.

**Stays: `PROTECTED_ROLES` and `RemovalTargetIsRemovableNode`.** The earlier
reading of this one was wrong, and the constant's own comment — "Roles a
removal may not take away" — is where the error came from. CM-31-004 refuses
the *removal of a participant* that holds `CASE_MANAGER` or `CASE_OWNER`,
because a case always has a CASE_MANAGER (CM-02-014) and ownership is
transferred before its holder leaves (CM-21-001). A removal edits no roles at
all; it sets `removed` on the record. So the check is a protocol rule, not a
patch on the enum: point it at the new authority field and keep it. The split
gives it the name it lacked, and the implementation should fix that misleading
comment while it is there.

---

## Both creation doors claim a position

A participant with no position has no place in the protocol, because every
permission and obligation attaches to one (CM-26-001). Two doors create a
participant that holds only authority today, and both close in the same change
as the invariant, so the tree is never red in between.

- **The report receiver's proposal.** `ProposeReportCaseToActorNode` stops
  reading `get_config()`. Its caller, the received-report tree, passes the claim
  in, reading the value from `ActorConfig.default_case_roles`. A claim naming no
  position refuses the proposal, and the wire model drops its "empty means owner
  only" reading.
- **Direct case creation.** `_RegisterCreatorParticipantNode`, in
  `vultron/core/behaviors/case/create_case_trigger_tree.py`, takes its
  position the same way instead of naming only authority. CM-02-015 asks for
  exactly the pair it hard-codes, so that requirement is amended in the same
  change.

The configuration field is a **hint** — the value a caller reads when it has
nothing more specific to claim — and never the authority for what a participant
holds. A later change may let a caller claim a different position per case
without undoing anything here; that is why the claim is the node's input rather
than its own configuration read.

---

## Why the demo needed none of this stated as a cast rule

The concern #5586 read the symptom as a seating rule: a decision point's actor
must run in one of the three containers that carry a role setting. It is not. A decision
point's actor holds the role it needs because an act gave it — submitting the
report, claiming a position when proposing the case, or being assigned one
through the suggest-actor flow (CM-16-003, CM-17-003). Once every door hands
over a position, no container setting can be the reason a decision is refused,
and the static check #5586 asked for has nothing left to catch.

One consequence does belong in the demo's own rules: a container that carries no
configured position cannot be the actor that receives the original report,
because it has nothing to claim. The character-actor slots carry none by
DEMOCI-11-026, so the original report goes to a fixed-role slot.

The leftover want — catching a scenario that lets the *wrong* actor decide, a
Vendor answering a Coordinator decision — is a different and weaker check. Its
precondition is met: every scenario is written as composition, so each decision
names its deciding cast member in a `choose(..., by=...)` item and the
decider-to-container mapping it needs exists.

---

## Order

1. The three-way split, with the participant record, wire form and stored shape
   following, the role-Offer clause retired, and the removal check repointed at
   the authority field. Large and mostly mechanical.
2. The position invariant and both creation doors, in one change so no state
   lands where the invariant holds and a door violates it.
