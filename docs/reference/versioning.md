---
description: >
  The release versioning scheme for the Vultron repository.
stakeholder_type: [cvd-practitioner, platform-developer]
level: 200
---

# Vultron Release Versioning

{% include-markdown "../includes/curr_ver.md" end="<!-- versioning-link -->" %}

Vultron releases follow [Calendar Versioning (CalVer)](https://calver.org/) using the format `vYYYY.M.P`.
The release tag names a snapshot of the whole repository.
It makes no compatibility claim about any interface.
For interface versioning, see [ADR-0106](../adr/0106-versioning-machine-facing-interfaces.md).

The format components are:

- `YYYY` is the four-digit year of the release.

- `M` is the month of the release, with no zero padding (e.g., `1`, `2`, ..., `12`).

- `P` is the patch number for that release, starting at `0` for the first release in a given month.
  Patch releases increment this number from the most recent non-patch release, even if the patch is published in a later month or year.
  **The patch component is always present.**

Examples:

- The first release in October 2026 is `v2026.10.0`.
- A third patch to that release is `v2026.10.3`, even if it is published in November 2026.
- A subsequent non-patch release in March 2027 is `v2027.3.0`.

No compatibility commitments are made or implied by the release tag.
