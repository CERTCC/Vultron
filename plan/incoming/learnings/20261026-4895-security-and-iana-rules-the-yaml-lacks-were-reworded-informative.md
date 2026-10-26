---
title: "Two rules the Protocol Specification stated in §14 and §15 have no protocol requirement, so reconciling them left them informative"
type: learning
timestamp: "2026-10-26T18:00:00Z"
source: ISSUE-4895
signal: spec-gap
---

**Trigger.** You are reconciling a Protocol Specification fragment into
callouts (#4888), writing a requirement about the JSON-LD context or actor
identity, or reading §14 IANA and Namespace Considerations or §15.1 Trust
Model and wondering why neither shows a callout for these rules.

**Claim.** Two statements the specification used to make with RFC 2119
keywords have no `protocol` or `foundation` requirement behind them:

- A receiver processes a message without fetching the Vultron context URI,
  which does not dereference yet (`_iana.md`). VM-10-001 requires senders to
  name the URI but says nothing on the receiving side.
- Actor URI equality is identity equality: two messages with the same `actor`
  URI are from the same actor (`_security.md` §15.1). OID-01-001 requires full
  URI ids, and CLP-07-003 compares normalized actor ids for one field only.

Both are observable and matter for interoperability, so each looks like a
missing VM-10 and OID requirement rather than prose. PR #5173 reworded both as
informative, which is the other path `notes/rfc-spec-authoring.md` allows. If
`learn` adds the requirements, the fragments should show them as callouts.

**Evidence.** PR #5173 § "Rules reworded as informative"; pre-push finding
`phase8-normative-demotions-unrecorded-0`.
