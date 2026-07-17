# Implementation Specifications

Requirements specific to this codebase. These cover file paths under
`vultron/`, class names in `vultron/core/`, notes frontmatter schema, and
other implementation-specific details.

```python exec="true" idprefix=""
import sys
from pathlib import Path
_repo = Path.cwd()
if str(_repo) not in sys.path:
    sys.path.insert(0, str(_repo))
for _k in list(sys.modules.keys()):
    if _k.startswith("vultron"):
        del sys.modules[_k]
from vultron.metadata.specs import load_registry
from vultron.metadata.specs.docs_render import render_for_kind
registry = load_registry(_repo / "specs")
print(render_for_kind("implementation", registry))
```
