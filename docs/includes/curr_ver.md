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

    <!-- versioning-link -->
    This is a build version, not a protocol version.
    Protocol versions are numbered by the [protocol versioning scheme](../reference/versioning.md).
