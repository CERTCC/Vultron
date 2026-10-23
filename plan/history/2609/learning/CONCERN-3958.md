---
source: CONCERN-3958
timestamp: '2026-09-30T19:19:49.497842+00:00'
title: MV-11-002 refuses JSON-LD @id/@type as near misses of id/type by design
type: learning
---

## Concern

MV-11-002 defines a near miss as "exactly" lowercasing plus stripping every
non-alphanumeric character. Under that rule, the JSON-LD keywords `@id` and
`@type` normalise to `id` and `type`. The parse edge built in #3921 (PR #3951)
therefore refuses an inbound object that carries `@id` or `@type` beside or
instead of `id`/`type`.

On `main` before MV-11, the same keys were dropped silently. A JSON-LD
processor that emits expanded keywords, which is legal JSON-LD, would now have
its whole activity refused with a 422.

This behaviour is what the spec requires, and the PR does not change it. The
open question is whether JSON-LD keywords should be:

- **(a) refused**, as the spec now says. This keeps the rule exact, and a peer
  learns immediately that Vultron reads only compact AS2.
- **(b) exempt from the near-miss test and set aside** like any foreign key.
- **(c) read as the aliases they are**, `@id` → `id` and `@type` → `type`.
  This is the most permissive option, but it goes beyond what MV-11 scopes.

`@context` is already a declared spelling on every class, so it is not
affected.

## Evidence

Found by the code review in triage of PR #3951 (finding
`phase8-jsonld-keyword-near-miss-0`). A probe put `"@id"` and `"@type"` on an
inline Note, and both were refused as resembling `'id'`/`'type'`.

Governing specs: MV-11-002, MV-11-001

## Resolution

Option (a), recorded as a decision. `@id` and `@type` are JSON-LD keywords, not
AS2 fields: the normative AS2 context aliases them to `id` and `type`, and AS2
Core § 2.1 requires the serialized form to be consistent with compaction under
that context, so a conforming AS2 document never carries the `@`-prefixed forms.
A message that does is legal JSON-LD but not conforming AS2, which MV-01-001
already owes a refusal, and the peer meant the `id`/`type` Vultron reads.
Setting the keywords aside would strip the object's identity and type; declaring
them as aliases would make Vultron a partial JSON-LD processor with no
principled stopping point. MV-11-002 now names the keywords as near misses by
design and forbids aliasing or exempting them; `@context` stays the only
declared JSON-LD keyword. No ADR: ADR-0099 detail 7 already states the rule.

**Resolved**: 2026-09-30 — implementation tracked in #3969 (matrix rows
pinning the refusal, after PR #3951 lands).
Docs PR: <https://github.com/CERTCC/Vultron/pull/3968>.
Spec: `specs/message-validation.yaml` (MV-11-002).
Notes: `notes/wire-core-boundary.md`.
