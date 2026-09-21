"""Shared type aliases and helpers for the vultron.metadata tooling layer."""

from pathlib import Path
from typing import Annotated

import yaml
from pydantic import StringConstraints

NonEmptyStr = Annotated[str, StringConstraints(min_length=1)]
NonEmptyStrList = list[NonEmptyStr]


def repo_root(start: Path | None = None) -> Path:
    """Return the repository root by searching upward for ``pyproject.toml``.

    Every loader and generator in this package needs the repo root and none of
    them can assume the caller's working directory (NF-03-005), so this lives
    here rather than being re-derived per module.

    Args:
        start: Directory to search upward from. Defaults to the current working
            directory. Resolved first, so a relative ``start`` still yields
            absolute parents to walk.

    Raises:
        FileNotFoundError: If ``pyproject.toml`` is in no parent directory,
            which means the tool was invoked outside a Vultron checkout.
    """
    origin = (start or Path.cwd()).resolve()
    for parent in [origin, *origin.parents]:
        if (parent / "pyproject.toml").exists():
            return parent
    raise FileNotFoundError(
        f"Could not locate repository root (pyproject.toml) starting from "
        f"{origin}"
    )


class MkDocsYamlLoader(yaml.SafeLoader):
    """SafeLoader that tolerates the custom YAML tags in ``mkdocs.yml``.

    ``mkdocs.yml`` carries ``!ENV`` and ``!!python/name:`` tags that a plain
    ``yaml.safe_load`` refuses to construct.  Callers here only ever want plain
    config values (the ``nav:`` tree, ``use_directory_urls``), so permissive
    constructors discard the tag and keep the underlying node rather than
    executing anything.
    """


MkDocsYamlLoader.add_multi_constructor("!", lambda _l, _s, _n: None)
MkDocsYamlLoader.add_multi_constructor(
    "tag:yaml.org,2002:python/name:", lambda _l, _s, _n: None
)
