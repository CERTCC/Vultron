---
stakeholder_type: [platform-developer]
level: 400
---

# Foundation Specifications

Rules Vultron inherits from the standards beneath it: ActivityStreams 2.0, ActivityPub, and HTTP.
They cover addressing and delivery, HTTP status codes, and rules that only restate ActivityStreams, such as treating object IDs as opaque URIs.
Each requirement carries a tag that names its standard: `as2`, `activitypub`, or `http`.
Where Vultron requires one form among several that a standard allows, the rule is a [Protocol](protocol.md) requirement, not a foundation one.
An implementer reads this page together with the Protocol page.

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
print(render_for_kind("foundation", registry))
```
