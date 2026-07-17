# Pattern Specifications

Architectural and framework approach requirements that are language-agnostic
and not CVD-specific. These cover hexagonal architecture, behavior tree
composability, event-driven dispatch, and similar structural patterns.

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
print(render_for_kind("pattern", registry))
```
