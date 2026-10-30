### 14.8 Inherited Requirements

These are the rules Vultron inherits from the standards beneath it: ActivityStreams 2.0 (AS2), ActivityPub, and the Hypertext Transfer Protocol (HTTP).
They cover addressing and delivery, HTTP status codes, and rules that only restate AS2, such as every object ID being an Internationalized Resource Identifier (IRI).
Where Vultron asks for one form among several that a standard allows, the rule is a Vultron requirement on one of the pages before this one, not an inherited one.

```python exec="true" idprefix=""
from vultron.metadata.specs.docs_render import render_catalog_page; print(render_catalog_page("foundation"))
```
