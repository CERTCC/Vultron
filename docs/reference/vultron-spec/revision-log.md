---
title: "Protocol Specification: Revision Log"
description: >
  The drafts of the Vultron Protocol Specification, their version identifiers
  and dates, and what changed in each draft.
stakeholder_type: [platform-developer]
level: 400
page_type: reference
subject: protocol
---

# Protocol Specification Revision Log

This page records each draft of the [Vultron Protocol Specification](index.md), with its version identifier, its status, its date, and what changed in it.
Use it if you cite the specification, or if you must know which text your implementation was built against.
The newest draft is first.

## Version identifiers

Each draft of the specification has a version identifier of the form `draft-N`.
`N` is the number of the draft.
The first draft is `draft-1`, and each later draft adds one.

A draft is fixed when a release of the Vultron repository carries it.
The release tag has the `vYYYY.M.P` format that [Vultron Release Versioning](../versioning.md) describes, and the entry for the draft gives that tag in its status.
Until that release, the text of the draft can still change.
After that release, a change to the text goes into the next draft, with a new entry on this page.
Thus the version identifier of a released draft always names one text, and a reader can cite the text they read.

The version identifier names the text of the specification only.
The release tag names a snapshot of the whole repository.

The date of a draft is the day its entry was added to this page, in the `YYYY-MM-DD` format.

## Draft 1

| Property | Value |
|----------|-------|
| Version | `draft-1` |
| Status | Draft, not yet released |
| Date | 2026-11-06 |

Draft 1 is the first draft of the specification.
It has no earlier draft, so this entry lists what the draft holds, not what changed.

- The body sections and the annexes, as the [parts of the specification](index.md#parts) list them.
- The Requirements Catalog, which renders the `protocol` and `foundation` requirement tiers.
- The [Open Questions](open-questions.md) that this draft leaves unresolved.
