"""Load a ``.github/scripts/*.py`` script as a module, once per test process.

The scripts are files, not a package: each puts its own directory on
``sys.path`` and imports its neighbours by bare name (``gh_cli``,
``release_tags``, ``publish_gate``). A test loads a script under that same
name, so a script and the tests that load it share one module object, and a
``monkeypatch`` on it reaches every caller.
"""

from __future__ import annotations

import importlib.util
import sys
from types import ModuleType

from test.ci._workflows import REPO_ROOT

SCRIPTS_DIR = REPO_ROOT / ".github" / "scripts"


def load_script(name: str) -> ModuleType:
    """The script ``.github/scripts/<name>.py``, loaded under *name*."""
    path = SCRIPTS_DIR / f"{name}.py"
    loaded = sys.modules.get(name)
    if loaded is not None and getattr(loaded, "__file__", None) == str(path):
        return loaded
    spec = importlib.util.spec_from_file_location(name, path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    # Dataclasses look their module up in sys.modules while being defined.
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module
