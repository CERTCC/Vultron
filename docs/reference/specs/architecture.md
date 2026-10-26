---
stakeholder_type: [platform-developer, project-contributor]
level: 400
page_type: reference
---

# Architecture Specifications

Recommended structure that carries over to other languages but is not required for Vultron compliance.
Behavior trees, and keeping protocol behavior inside the behavior tree, are architecture, as are hexagonal boundaries, event-driven dispatch, port and adapter patterns, and fail-fast principles.

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
print(render_for_kind("architecture", registry))
```

{% include-markdown "../../start/_paths/contribute/reference__specs__architecture.md" %}
