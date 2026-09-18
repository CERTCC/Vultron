---
title: "A CaseActor→CASE_MANAGER rename keeps the concrete-actor name for infrastructure (URI/inbox/outbox/store); only authority *actions* become the role"
type: learning
timestamp: "2026-09-17T00:00:00Z"
source: ISSUE-3342
signal: theme-candidate
---

ADR-0088 and `notes/spec-authoring-rules.md` say to rewrite "CaseActor" to
"the CASE_MANAGER" where the text means the authority. Applied naively, that
rule over-rewrites, because the same actor is *both* the authority (a role) and
a concrete node with a URI, an inbox, an outbox, a DataLayer, and a container.
The glossary is explicit: "authority, recognition, and routing derive from the
CASE_MANAGER role, **never from this actor's name or URL**" — which cuts both
ways. A role has no URI or inbox, so renaming an *infrastructure* reference to
`CASE_MANAGER` is as wrong as leaving an *authority* reference as `CaseActor`.

The discriminator that survived code review on #3342:

- **Rewrite to `CASE_MANAGER`** when the subject performs a single-writer
  **authority action or property**: commits/authors canonical ledger entries,
  maintains or writes shared EM/CS state, sets participant state at bootstrap,
  is the sole authorized writer, authorizes a commit, or fabricates
  protocol-visible state only the writer could.
- **Keep `CaseActor`** (the concrete actor) for **infrastructure and identity**:
  its URI / `case_actor_id`, its inbox/outbox, HTTP-loopback self-delivery to
  its own inbox, its DataLayer/store, its container/hosting, co-location,
  delegated-emit store-scoping (ADR-0073), a code identifier
  (`CheckIsOwnCaseActorNode`, `VultronCaseActor`, `_EmitCaseActorReportActivityBase`),
  the `CaseActor` *domain type*, or the `case-actor` URL-shape anti-pattern a
  ratchet forbids.

The trap is a requirement that reads like authority but is actually delivery.
`outbox.yaml`'s canonical-ledger self-delivery (OX-08/OX-12-004) *sounds* like
an authority obligation ("GuardedCommit fires"), but every noun in it —
own URI, own ID, own inbox, received-side use case, HTTP loopback — is the
concrete actor's plumbing. The commit *authorization* is the role; the *delivery
that carries the self-copy to the inbox* is the actor. An entire spec file can
be delivery-mechanics and correctly keep `CaseActor` throughout. Likewise a
store/DataLayer reference stays `CaseActor` even inside a file whose description
line legitimately became `CASE_MANAGER` (state-machine.yaml did both).

Two corroborating observations from the same sweep:

- **Sister specs are the tie-breaker.** ARCH-24-004's "the real CaseActor fails
  its own hosting test" had a twin, CM-02-012, that already said "the real
  CASE_MANAGER…". A bare role cannot "fail a hosting test", so the precise form
  both should share is **"the actor enacting `CVDRole.CASE_MANAGER`"** — an
  actor, grounded in the role. When two entries describe the same fact, make the
  laggard match the one that already applied the decision.
- **A `refines:` link is not proof of consistency.** CM-20-001/004/005 claimed
  to refine CBT-01-003 while their rationale asserted the opposite of it —
  CASE_MANAGER "reserved exclusively for the Case Actor … MUST NOT be held by
  any participant … not the case management service," where CBT-01-003 says the
  case creator "MUST be a participant with `CVDRole.CASE_MANAGER`, and SHOULD
  also carry `CVDRole.COORDINATOR`." A naming sweep is a cheap way to surface
  these stale-premise landmines, because it forces you to read the rationale
  the term sits in. Check a rewrite candidate's `refines:`/`adr:` parents for
  agreement, not just its wording.

**How to apply.** Before rewriting a "CaseActor" occurrence, ask: is the subject
*doing* an authority action, or is the text about *where/how* it is hosted,
addressed, stored, or delivered to? Only the first becomes `CASE_MANAGER`. When
in doubt on an infrastructure-flavoured line, keep `CaseActor` — over-rewriting
attributes a URI/inbox to a role, which is the exact category error the glossary
warns against. The next place this bites is the **docs/ arm** of the ADR-0088
prose sweep (`docs/topics/`, scenario pages; the `docs/adr/*` records stay).

Related: [[20260914-3217-measure-what-a-permissive-fallback-absorbs]] and
[[20260916-3207-ac7-exactly-two-vs-permanent-overcatch]] — the same shape as the
CM-20 finding: an entry that constrains/frames one member of a population (here,
"CASE_MANAGER") against a premise its governing decision already overturned.
