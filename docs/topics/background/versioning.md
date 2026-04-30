# Vultron Protocol Version Numbering Scheme

!!! note inline end "Implementations may have their own versioning scheme"

    The versioning scheme described here applies _only_ to the Vultron Protocol itself.
    Implementations of the Vultron Protocol are expected to have their own versioning schemes.

{% include-markdown "../../includes/curr_ver.md" %}

Vultron Protocol versions follow [Calendar Versioning (CalVer)](https://calver.org/)
using the format `YYYY.M.Patch`, where:

- `YYYY` is the four-digit year of the most recent non-patch release.

- `M` is the month of the most recent non-patch release,
    with no zero padding (e.g., `1`, `2`, `3`, ..., `12`).

- `Patch` is the patch number for that release.
    For the first (or only) release in a given month, the patch number
    starts at `0` and is normally omitted, so `2024.4.0` and `2024.4`
    denote the same version.

Version increments work as follows:

- **Significant releases** use the current year and month, with the patch
    number starting at `0` (normally omitted).
    Example: the first significant release in April 2024 is `2024.4`.

- **Patch releases** increment the patch number from the most recent
    non-patch release, even if the patch is published in a later month or year.
    Example: the third small update to `2024.4` is `2024.4.3`, even if it
    is released in May 2024 or later.

Because we are still in the early stages of the project, no backward
compatibility commitments are made or implied at this time.
We anticipate this will change as the protocol matures.
