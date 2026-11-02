---
description: >
  The release versioning scheme for the Vultron repository.
stakeholder_type: [cvd-practitioner, platform-developer]
level: 200
page_type: reference
subject: neutral
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
  Each later release in the same month adds one.
  **The patch component is always present.**

The year and month are those of the day the release is cut, in UTC.
A release is cut by promoting a commit that the site already published, so a release that fixes an earlier one takes the month in which it is cut.
Each release tag is greater than every earlier one.

Examples:

- The first release in October 2026 is `v2026.10.0`.
- The third release after it in October 2026 is `v2026.10.3`.
- A release cut in November 2026 is `v2026.11.0`, even when it fixes `v2026.10.3`.

No compatibility commitments are made or implied by the release tag.
