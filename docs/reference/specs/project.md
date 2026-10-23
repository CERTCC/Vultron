---
stakeholder_type: [project-contributor]
---

# Project Specifications

Rules that bind this codebase only.
They cover deployment choices, such as running the CASE_MANAGER as an actor separate from the case owner, performance and operating limits, how a receiver records what it receives, and core internals.
Naming a Python path, library, or class does not by itself make a rule a project rule: who must obey the rule decides its kind.

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
print(render_for_kind("project", registry))
```
