---
status: proposed
date: 2026-11-12
created: 2026-11-12
updated: 2026-11-12
revision: 1
lint_suppress: [phantom_path_ref]
deciders: Allen D. Householder
consulted: >-
  Claude Opus 5.5; issues #6284, #6168, #3559, #6285, #6286, #6287; ADR-0006,
  ADR-0171
informed: []
stakeholder_type: [project-contributor]
---

# Each Released Protocol Specification Draft Is a Frozen Archive on Its Release, Served Beside the Current Draft

## Context and Problem Statement

The Protocol Specification is published as pages of the project site, and each draft is fixed when a release of the repository carries it.
A Pages deploy replaces the whole site, so the rendered text of a released draft is gone the moment the next publish ships a newer text.
The release tag keeps the source of that draft, but not the pages a reader saw.
An outside review of Draft 1 is planned for 2027Q1, while `main` moves on to Draft 2, so the reviewers need the rendered Draft 1 text at an address that stays the same.

How does each released draft stay readable, unchanged, at one permanent address beside the current draft, without a manual step and without a new credential?

## Decision Drivers

- A released draft is a text that people cite, so its rendered pages must never change after the release.
- Each released draft needs one permanent address on the site, and a reader must be able to tell it from the current draft, which still changes.
- A draft's number, status, date and release must be stated in one place, so the pages and the release automation never disagree.
- Immutable releases are enabled on the repository: once a GitHub Release is published, nothing can add, change or remove its assets.
  A published release therefore holds an asset that never changes, and an asset can be attached only while the release is still a draft.
- A workflow that pushes a commit or opens a pull request with the default token starts no other workflow, so the change it makes would merge with no CI run, or would need a new credential.
- The site tooling changes over time, and a later toolchain can render the same source differently.
- Frozen per-release documentation on Zensical's native versioning (#3559) waits on a Zensical release that is not expected before the review.

## Considered Options

1. **Archive attached at promote, unpacked at every deploy.** The promote that releases a draft builds that draft's specification pages and attaches them to the release as an archive with a hash manifest; every deploy unpacks each released draft's archive into the site.
2. **A folder of frozen pages committed to `main`.** At release, the rendered pages are committed under a fixed folder, and every build copies the folder into the site.
3. **Rebuild each released draft from its tag at every deploy.** The deploy checks out each release tag that carries a draft and builds its specification pages again.
4. **A frozen copy of the whole site for each release.** Each release keeps its own copy of the entire site, under a versioned path, as #3559 proposes.

## Decision Outcome

Chosen option: "Archive attached at promote, unpacked at every deploy", because it is the only option that renders each draft once, keeps the result where nothing can change it, and needs no new credential.

The decision has these parts:

- **One register.** A drafts register in the repository is the one source of each draft's version (`draft-N`), status (unreleased or released), date and, once released, the release that carries it.
  The status box and the status tables of the revision log are committed fragments generated from it, and a check refuses a fragment that has drifted from the register.
  An entry is marked released before the promote, in the same way the revision log is today, so the release tag carries the register that names it.
  A released entry never changes afterwards, and a check compares it with the entry at its release tag.
- **Labelled from the register.** While the register holds an unreleased draft, the live specification is labelled "Current draft (work in progress)".
  When it holds none, the status box names the newest released draft and its release instead.
  At the promoted commit the draft has just been marked released and no newer draft is open, so the pages the archive freezes read as that released draft.
  The revision log links every released draft's frozen copy.
- **Made at promote.** When the register at the promoted commit names the new release as the release of a draft, the promote builds the site at that commit through the shared build, and takes the rendered specification pages and the files they load.
  A promote refuses a register that names a release tag the run will not make, and one that still holds an open draft beside the draft it releases.
  Each frozen page gets a banner that names the draft, the release, the commit and the build date.
  Links inside the specification stay relative and work offline.
  Links that leave the specification point to the live site, and the banner says so: the frozen copy does not freeze the rest of the site.
  The job that builds the archive cannot write to the repository, and the job that can write runs no code from the promoted commit.
  Before it attaches anything, the promote unpacks the real archive and checks its links and its manifest, because a defect found after publication can never be fixed.
  It attaches the archive and a SHA-256 manifest of its files to the release while the release is still a draft, and checks that what was attached is what it built.
  A release that carries no draft gets neither file.
- **Attached once, before publication.** A promote that is run again on a release that is still a draft finishes its assets, where today's promote would refuse a tag that already has a release.
  It keeps a complete pair, and replaces an incomplete one as a whole.
  Once the release is published, its assets are immutable, so the promote refuses, and says that a re-run cannot help.
  The maintainer publishes the draft release only after the promote run has succeeded.
- **Served by every deploy, never rebuilt.** Every deploy reads the register as `main` holds it and, for each released draft whose release is published, downloads the archive, checks it against its manifest and unpacks it into `spec/draft-N/`.
  The unpack refuses any member that could write outside that folder, and runs in the job that holds no token to write or deploy.
  No build ever builds a commit other than the one it checked out, so a toolchain change cannot alter a frozen draft.
  Because the register is read from `main`, a rollback to an older commit still serves every frozen draft.
  A released draft whose release is not published yet (its tag not made, or its release still a draft) gets a placeholder page at its address that names the release, and a notice in the run summary, so the pages that link it never link a missing page.
  A published release whose archive is missing, or does not match its manifest, fails the deploy through the failure notice: the site never drops a frozen draft silently.
- **Checked by links, not by later editorial rules.** The pull-request check serves the frozen drafts the same way, from the register in the pull request, so it sees the same tree as the deploy.
  The promote's own build does not serve them.
  The link check covers the frozen pages.
  The checks of the site's own editorial rules, and the record of served URLs, leave the frozen pages alone: a page that never changes would otherwise fail every rule added after its release.
  A frozen draft stays served because the register names it and a deploy fails without it.

### Relation to ADR-0171 and #3559

This decision builds on ADR-0171 and changes none of its parts: the schedule, the CI gate, the tags and the rollback stay as they are.
The promote that ADR-0171 introduced gains the archive step and a wider resume for a release that is still a draft, and every publish gains the unpack step.

Issue #3559 is about the whole site, versioned for each release.
This decision covers only the Protocol Specification, one frozen copy for each released draft.
It does not decide which versions of the rest of the site stay live, what `latest` means, or how a versioned site meets the maturity manifest.
If #3559 later versions the whole site, the `spec/draft-N/` addresses must keep resolving, which the register and the deploy failure already require.

### Consequences

- Good, because each released draft has one permanent address, and its pages are the bytes the promote built, protected by an immutable release and checked against a manifest at every deploy.
- Good, because the draft status is written once, and the pages, the promote and the deploy all read it from the register.
- Good, because a toolchain change, a new site rule or a rollback cannot alter or drop a frozen draft.
- Good, because the archive is also a download that a reviewer can read offline.
- Bad, because a published release whose archive is missing or broken cannot be repaired in place: an immutable release refuses a new asset.
  Every deploy fails until a maintainer acts.
  The promote prevents the case, but the maintainer can still publish a draft release before its promote run has succeeded.
- Bad, because the pull-request check and every deploy download the frozen drafts, so a GitHub outage can fail a build that changed nothing.
- Bad, because the frozen pages keep the look of their release day, and their links to the live site can reach pages that have since changed or moved.
- Bad, because the link check still judges the frozen pages, so a stricter link checker added later can fail a page that can never change.
  Such a change must then exempt the frozen pages, or keep their old rule.
- Neutral, because a release that carries no draft is promoted exactly as before.

## Validation

Tests of the promote run it against a fixture repository and check that a release the register names for a draft gets the archive and the manifest, that any other release gets neither, that every frozen page carries the banner, that its relative links resolve inside the archive and its other links name the live site, that a re-run on a draft release finishes or keeps the pair, and that a register naming the wrong tag is refused.
Tests of the deploy unpack fixture archives and check that a published draft is served byte for byte as its manifest lists it, that an unpublished one gets a placeholder and a notice, that an unsafe or mismatched archive is refused, and that a missing archive fails the run.
The specs that this decision generated name each test.

## Pros and Cons of the Options

### Archive attached at promote, unpacked at every deploy

- Good, because each draft is rendered once, by the toolchain of its own release.
- Good, because the archive lives on an immutable release, where neither a commit nor a workflow can change it.
- Good, because it needs no write to `main` and no new credential.
- Bad, because each build downloads the archives, and a missing archive on a published release cannot be fixed in place.

### A folder of frozen pages committed to `main`

- Good, because every build has the frozen pages in its checkout, with no download.
- Bad, because a workflow cannot open a pull request whose CI runs without a new credential, so the commit would need a manual step or a token the project does not hold.
- Bad, because a later commit can edit the frozen pages, and every formatter, linter and sweep over the tree would have to exclude them.
- Bad, because rendered HTML for each draft grows the repository for good.

### Rebuild each released draft from its tag at every deploy

- Good, because nothing extra is stored anywhere.
- Bad, because the rebuild runs today's environment against an old tag, so the dependencies, the actions and the output drift, and the frozen text is not the same bytes from one deploy to the next.
- Bad, because a tag whose build no longer works, as for releases that lack the build's local actions, drops its draft from the site.
- Bad, because each released draft adds a full build to every deploy.

### A frozen copy of the whole site for each release

- Good, because a reader of a release sees every page as it was, not only the specification.
- Bad, because most of the site is guidance that should follow `main`, not a text that people cite.
- Bad, because it puts a version into every URL, which the record of served URLs and the redirect checks do not yet handle (#3559's open questions).
- Bad, because it waits on Zensical's native versioning, which is not expected before the review of Draft 1.

## More Information

Generated spec requirements: `docs-build-workflow.yaml` DOCBW-08-001 through DOCBW-08-036.

Open question: how the site recovers when a published release lacks its archive, or holds one that fails its manifest, is not decided yet.
Until it is, every deploy fails in that case.
