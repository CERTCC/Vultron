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
Until that release, the text of the draft can still change, so a citation of an unreleased draft also names the `publish-YYYY-MM-DD.N` tag in the page footer.
After that release, a change to the text goes into the next draft, with a new entry on this page.
Thus the version identifier of a released draft always names one text, and a reader can cite the text they read.

The version identifier names the text of the specification only.
The release tag names a snapshot of the whole repository.

The date of a draft is the day its entry was added to the drafts register, in the `YYYY-MM-DD` format.
The drafts register is the file in the Vultron repository that records each draft's version, status, date and release, and the status table of each entry on this page is generated from it.

## Draft 2

{% include-markdown "./_drafts/draft-2.md" rewrite-relative-urls=false %}

Draft 2 is the current draft, and its text can still change.
This entry lists what changed since [Draft 1](#draft-1).

- The [Requirements Catalog](requirements/messages.md#protocol-mv-12) adds the protocol requirements MV-12-001 to MV-12-005, on the `Redacted` marker that a preview uses for a withheld field.
- The [Known Gaps](known-gaps.md) page lists MV-12-001, MV-12-002, MV-12-003 and MV-12-005, which issue #6372 tracks.

## Draft 1

{% include-markdown "./_drafts/draft-1.md" rewrite-relative-urls=false %}

Draft 1 is the first draft of the specification.
It has no earlier draft, so this entry lists what the draft holds, not what changed.

- The body sections and the annexes, as the [parts of the specification](index.md#parts) list them.
- The [Requirements Catalog](requirements/index.md), which renders the `protocol` and `foundation` requirement tiers.
- The [Open Questions](open-questions.md) that this draft leaves unresolved.
- The [Known Gaps](known-gaps.md) page, which lists the requirements that the tests do not show the reference implementation fully meets.
