---
source: CONCERN-3260
timestamp: '2026-09-15T18:17:53.708429+00:00'
title: CASE_MANAGER role vs "CaseActor" identity — docs terminology migration
type: learning
---

## Concern

Docs and code conflated authority over a case — who may write a participant's
canonical case replica — with the **"CaseActor" identity**, rather than with
holding **`CVDRole.CASE_MANAGER`**. Authority-attributing "the CaseActor" prose
had leaked across ~30 doc/spec files, inviting `actor_id == case_actor_id`
identity checks instead of role gating (which breaks under ownership transfer /
re-homing / multi-container). The trigger was `notes/participant-case-replica.md`
stating *"Who may update a participant's local case replica? Only the CaseActor"*
while the same file's Architecture Overview already gated on the role (CM-24-004).

## Resolution

**Resolved**: 2026-09-15 — resolved directly by the documentation migration in
PR #3270; **no separate implementation issue** was filed (per maintainer
direction, the sweep was completed in-session). The code side (identity-comparison
removal, ratchets) remains owned by **Epic #2685** via ADR-0088's generated
requirements ARCH-24-001..005 and CM-02-011..013.

The concern was **narrowed and sharpened** during planning: rather than merely
retiring identity-framed prose, we replaced the ADR-0088 stance that kept
"CaseActor" as *shorthand for the authority* with a **three-way term split**
(maintainer decision, refining ADR-0088 in place):

- **CASE_MANAGER** (the role) = the single-writer authority; protocol-normative
  prose names it "the CASE_MANAGER".
- **CaseActor** = the concrete prototype/demo actor that enacts the role — an
  identity/label with no protocol meaning; never matched on.
- **case actor service** = the provisioning endpoint (`case_actor_service_url`).

Rationale for not using the maintainer's initial "case actor service" name for
the authority: "service" is itself a hosting signal ADR-0088 retired as fragile,
so the authority stays the role.

Migrated authority/duty/routing prose to CASE_MANAGER across specs/notes/docs;
kept "CaseActor" for concrete-actor key/hosting/cluster/service prose
(`encryption.yaml` unchanged — keypairs bind to the concrete actor). Reframed
recognition-side identity framing to gate on the role (CM-24-004). Code
identifiers unchanged. Also revised ADR-0088 (point 7, glossary-companion
paragraph, title), the glossary (Case Actor / Case Manager / Case Actor Service +
Flagged-Ambiguity #13), `notes/spec-authoring-rules.md`, and the AGENTS.md
spec-authoring cell.

Docs PR: <https://github.com/CERTCC/Vultron/pull/3270>.
