---
source: NOTES-spec-authoring-rules--naming-and-population-examples
timestamp: '2026-10-14T14:33:13.322877+00:00'
title: 'spec-authoring-rules: CASE_MANAGER naming, population and all-members write-ups
  (original text)'
type: note
---

Archived from `notes/spec-authoring-rules.md` by #4498: the original long-form write-ups, trimmed to rule, reason and one citation. Code identifiers they named (`CheckIsOwnCaseActorNode`, `VultronCaseActor`) no longer exist, and the `outbox.yaml` self-delivery requirements they cited are gone. The rules stay in § "Name the Authority \"CASE_MANAGER\", Not \"CaseActor\"", § "Name Which Member of a Population a Requirement Constrains" and § "Verify an \"All-Members\" Group Claim Against Each Member".

---

## Removed text

### Sub-Agent Spec Splits: Re-Run the Violation Detection Script After the Parallel Pass

After parallel sub-agents split compound spec requirements, re-run the
compound-statement detection script. Agents frequently add new child entries but
leave the original parent statement text unchanged (with all semicolons intact).
The spec-lint failure surfaces the symptom; the detection script identifies which
parent was not trimmed. Do not trust agent completion reports for this class of
task.

Source: ISSUE-2393

### Name the Authority "CASE_MANAGER", Not "CaseActor" (CaseActor Is the Prototype Identity)

The authority for a case is a **role** — the participant holding
`CVDRole.CASE_MANAGER` — not a dedicated component and not a fixed identity.
Protocol-normative prose MUST name that authority **the CASE_MANAGER** (the role
holder). Reserve **"CaseActor"** for the concrete prototype/demo actor that
enacts the role, and **"case actor service"** for the provisioning endpoint that
spawns `case-actor` identities (glossary; ADR-0088). Anything per-case in a
CaseActor's *identity* (e.g., a per-case service URL derived from the case slug)
is a category error: no container has registered that identity, so any call to
it answers 404.

When a spec says "CaseActor MUST create X" or "CaseActor MUST send Y", rewrite it
to "the CASE_MANAGER MUST …" unless the requirement is genuinely about the
prototype actor (a demo/scenario spec such as `multi-actor-demo.yaml`). A spec
that mints an object to satisfy a role requirement — or that invites a reader to
compare `actor_id` against a computed `case_actor_id` — will be faithfully
implemented and faithfully wrong. Grep the spec corpus for MUST requirements
whose subject is `CaseActor` to catch these before they hide defects.

**Applied naively, the rewrite over-reaches.** The same actor is both the
authority (a role) and a concrete node with a URI, an inbox, an outbox, a
DataLayer and a container. A role has no URI or inbox, so renaming an
*infrastructure* reference to `CASE_MANAGER` is the same category error as leaving
an *authority* reference as `CaseActor`. The discriminator:

- **Write "the CASE_MANAGER"** when the subject performs a single-writer authority
  action or holds an authority property: commits or authors canonical ledger
  entries, writes shared EM/CS state, sets participant state at bootstrap, is the
  sole authorized writer, authorizes a commit.
- **Keep "CaseActor"** for infrastructure and identity: its URI or
  `case_actor_id`, its inbox and outbox, HTTP-loopback self-delivery to its own
  inbox, its DataLayer, its container or co-location, delegated-emit store
  scoping (ADR-0073), a code identifier (`CheckIsOwnCaseActorNode`,
  `VultronCaseActor`), the `CaseActor` domain type, or the `case-actor` URL-shape
  anti-pattern a ratchet forbids.
- **Write "the actor enacting `CVDRole.CASE_MANAGER`"** when the text needs an
  actor grounded in the role — for example one that can fail a hosting test,
  which a bare role cannot.

The trap is a requirement that reads like authority but is delivery. The
canonical-ledger self-delivery requirements in `outbox.yaml` sound like an
authority obligation, yet every noun in them (own URI, own inbox, HTTP loopback)
is the concrete actor's plumbing: the commit *authorization* is the role, the
*delivery* of the self-copy is the actor. When in doubt on an
infrastructure-flavoured line, keep `CaseActor`.

A naming sweep is also a cheap way to surface stale premises, because it forces
you to read the rationale the term sits in. Check a rewrite candidate's
`refines:` and `adr:` parents for agreement, not only its wording: CM-20-001/004/
005 claimed to refine CBT-01-003 while their rationale asserted its opposite.
When two entries describe the same fact, make the laggard match the one that
already applied the decision.

Source: ISSUE-1872, ISSUE-3260, ISSUE-3342

### Name Which Member of a Population a Requirement Constrains

When a requirement constrains one member of a set of similar things — one of
several timestamps on an object, one of several registries consulted on the same
value, one of several *kinds* of entry in a list — it MUST name **which one**.
An RFC 2119 verb applied to an unnamed member is not merely vague; it is often
*wrong under the plainer reading a new implementer will take*, producing a check
that is either vacuous or falsely rejecting:

- **Timestamps (ISSUE-2824).** A `CaseLedgerEntry` carries both an envelope
  `published` (the CASE_MANAGER's commit stamp) and a `payloadSnapshot.published`
  (the asserting participant's claimed time). CLP-14/CLP-15 constrained "the
  published timestamp" without saying which; applied to the claimed field,
  CLP-14-003's monotonicity check compares two participants' unsynchronised
  clocks — the wall-clock ordering ADR-0079 rejected — and rejects well-formed
  assertions. The fix names the field in every entry.
- **Registries (ISSUE-3217).** Two lookups act on an activity's `type`: the AS2
  vocabulary (`parse_activity` → reject with HTTP 422) and the semantic pattern
  registry (`find_matching_semantics` → route to `UNKNOWN`). MV-01-006 said
  "unrecognized activity types" without naming the registry, so "reject" and
  "route to UNKNOWN" both looked correct. The fix names the semantic pattern
  registry and points the parse-time behaviour at MV-01-001.
- **List kinds (ISSUE-3207).** ADR-0089's ratchet exclusion list holds two
  *writer* exclusions plus a permanent non-writer over-catch. An AC that says
  the list "ends at exactly two entries" (dropping *writer*) contradicts the
  design that made the gate deliberately over-broad. Count the kind, not the
  whole population.

**Corollary — name the enforcing side of a participant obligation.** A
requirement written as a participant duty ("a participant MUST emit … in causal
order") MUST also say what the *receiver* does about it: enforce, flag, or
nothing. A group heading is not a substitute — CLP-15's *Participant Assertion
Timestamp Obligations* heading did not stop four entries from being read as
CASE_MANAGER duties, and seven `xfail(strict=True)` stubs were written against a
per-assertion enforcement that CLP-15-005 forbids and a stateless commit boundary
cannot perform. Give such a requirement a `note` naming the enforcing side and a
`verification` pointing at the vantage point (e.g. a whole-scenario
`check_causal_edges`) from which the obligation is actually observable.

Source: ISSUE-2824, ISSUE-3217, ISSUE-3207

### Verify an "All-Members" Group Claim Against Each Member

The verification-side companion to the rule above. When a spec **group
description** asserts a property of *all* its members ("All CS shorthands share
the `ADD_CASE_STATUS_TO_CASE` semantic"), check each member against the code
before relying on the generalization. Group descriptions are written once and
rarely revisited when one member's behaviour later diverges, so a stale "all"
claim silently mis-specifies the members that changed. MSM-03-001/002/003
inherited exactly this: the group generalized a `CaseStatus` semantic onto `CV`/
`CF`/`CD`, which actually carry participant-scoped VF/D state
(`as_ParticipantStatus`, ADR-0075) — so the group asserted, normatively, the
opposite of an invariant the domain model enforces. An implementer following it
faithfully would have dropped the vendor identity.

Source: MSM-03-001/002/003 (promoted from notes/message-type-reference.md)
