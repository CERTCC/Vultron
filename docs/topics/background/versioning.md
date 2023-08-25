# Vultron Version Numbering Scheme

!!! note inline end "Implementations may have their own versioning scheme"

    The versioning scheme described here applies only to the Vultron protocol itself.
    Implementations of the Vultron protocol may have their own versioning schemes.

While we have not yet mapped out a future release schedule, in
anticipation of future revisions, we have chosen a semantic versioning
scheme for the Vultron protocol. Specifically, Vultron protocol versions will be
assigned according to the format `MAJOR.MINOR.MICRO`, where

-   `MAJOR` represents the zero-indexed major version for the release.

-   `MINOR` represents a zero-indexed counter for minor releases that
    maintain compatibility with their MAJOR version.

-   `MICRO` represents an optional zero-indexed micro-version (patch)
    counter for versions that update a MINOR version.

Trailing zero values may be omitted (e.g., `3.1` and `3.1.0` denote the
same version, similarly `5` and `5.0`). It may be useful at some point
to use pre-release tags such as `-alpha`, `-beta`, `-rc` (with optional
zero-indexed counters as needed), but we reserve that decision until
their necessity becomes clear. The same goes for build-specific tags;
while we do not currently have a use for them, we do not rule out their
future use.

Because of the early nature of the current protocol, as of this writing,
no backward compatibility commitments are made or implied within the `0.x` versions.
We anticipate this commitment will change as we get closer to a major release.

