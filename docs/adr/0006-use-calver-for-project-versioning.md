---
status: accepted
date: 2024-04-22
amended: "2026-09-28"
deciders: Allen D. Householder
stakeholder_type: [project-contributor]
---

# Vultron Release Versioning

## Context and Problem Statement

We need a versioning strategy for Vultron releases.
The repository contains documentation, protocol specifications, and a prototype implementation.
A release tag names a snapshot of the whole repository.
Interface versioning — what gets a version besides the release tag, and what bumps it — is a separate question answered in ADR-0106.

## Decision Drivers

- Release identification for the repository as a whole
- Tooling compatibility: `pyproject.toml`'s `tag_regex` constrains which formats are recognized
- Monotonic, unambiguous version numbers
- No implied compatibility claims from the release tag itself

## Considered Options

- Semantic Versioning with Major.Minor.Patch
- Calendar Versioning with YYYY.M.Patch

## Decision Outcome

Chosen option: **Calendar Versioning**, because the project is pre-stable, most content is documentation and prototypes, and the release date is the most meaningful signal about what shipped.

### The tag names a repository snapshot

The CalVer tag names a snapshot of the whole repository.
It makes no compatibility claim about any interface.
Pages, demo scenarios, and spec text are contents of that snapshot and carry no version of their own.
Interface versions are governed by ADR-0106.

### Format: three components, always — `vYYYY.M.P`

The format is `vYYYY.M.P`, where:

- `YYYY` is the four-digit year
- `M` is the month, no zero padding (e.g., `1`, `2`, ..., `12`)
- `P` is the patch number, starting at `0` for the first release in a given month

The patch component is **always present**.
The shorthand `v2026.9` (patch omitted) silently yields the `0.0.0+dev` fallback because
`pyproject.toml`'s `tag_regex` (`^(?:v)?(?P<version>\d+\.\d+\.\d+(?:[.-]rc\d+)?)$`) requires three components.
Do not use two-component tags.

### Monotonicity: tags MUST be monotonically increasing

Each new CalVer tag MUST compare greater than all preceding tags under standard version comparators.
Tags ran `v0.5 … v0.7.2`, then `v2023.9 … v2024.4.3`.
Every version comparator reads `2024.4.3 > 1.0.0`, so restoring SemVer would require a PEP 440 epoch (`1!1.0.0`).
A SemVer revert is therefore structurally blocked; this is recorded so it is not re-litigated.

### alpha/beta/rc tags are rejected

Pre-release labels (`alpha`, `beta`, `rc`) are cycle markers that presuppose an imminent final release.
Vultron is pre-stable as a standing condition with no `1.0` target.
Use a `snapshot-YYYYQn` tag for intermediate checkpoints that are not releases.
Note: `pyproject.toml`'s `tag_regex` currently includes an `(?:[.-]rc\d+)?` branch as a legacy artifact; it should be updated to `^(?:v)?(\d+\.\d+\.\d+)$` to match this policy.

### One GitHub Release per CalVer tag, not Pre-release

A GitHub Release is created for exactly one CalVer tag, covering the whole repository.
The **Pre-release checkbox MUST be unticked** so the repository has a Latest release.
`snapshot-YYYYQn` tags never receive a GitHub Release.

Note: existing GitHub Releases in this repository were created with the Pre-release box ticked; they should be updated to untick Pre-release to restore the Latest release pointer.

### Consequences

- Good, because CalVer communicates when something shipped without implying compatibility.
- Good, because three-component tags match `pyproject.toml`'s `tag_regex`, so built packages always carry a real version.
- Bad, because existing GitHub Releases must have the Pre-release box unticked before the repository shows a Latest release.
- Neutral, because CalVer is less universally recognized than SemVer, but it is common for documentation-heavy projects.

## Pros and Cons of the Options

### Semantic Versioning

- Good, because it is widely recognized and understood
- Good, because it communicates the relative importance of versions
- Bad, because a revert from CalVer is structurally blocked (see Monotonicity above)
- Bad, because pre-1.0 versions have only minor and patch components, which reduces version granularity

### Calendar Versioning (chosen)

- Good, because it communicates timing without implying compatibility claims
- Good, because three-component tags match the existing `tag_regex`
- Good, because the date makes the relative age of a release immediately apparent
- Neutral, because pre-stable development has no API surface to protect anyway

## More Information

- Interface versioning: ADR-0106
- [Calendar Versioning](https://calver.org/)
- [Semantic Versioning](https://semver.org/)
- Source: #3553 (amendment), #2960 (context)
