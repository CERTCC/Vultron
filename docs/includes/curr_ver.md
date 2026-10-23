!!! info inline end "Site build"

    ```python exec="true" idprefix=""
    import sys
    from pathlib import Path

    _repo = Path.cwd()
    if str(_repo) not in sys.path:
        sys.path.insert(0, str(_repo))

    from vultron import __version__
    from vultron.metadata.docs.build_version import describe_build

    print(describe_build(__version__))
    ```

    This is a build version, not a release version.
    <!-- versioning-link -->
    Release versions are numbered by the [release versioning scheme](../reference/versioning.md).
