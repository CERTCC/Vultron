---
stakeholder_type: [platform-developer]
level: 400
page_type: reference
---

# Protocol Specifications

{% include-markdown "../../includes/normative.md" %}

The Vultron layer: what every implementation, in any language, must obey to take part in Vultron.
It covers Vultron's message forms on the wire, including where ActivityStreams allows several forms and Vultron requires one.
It also covers which messages are sent and when, what a receiver does given its state, including on duplicate delivery, and the state machines underlying those behaviors.
Rules Vultron inherits unchanged from ActivityStreams 2.0, ActivityPub, or HTTP are on the [Foundation](foundation.md) page.

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
print(render_for_kind("protocol", registry))
```
