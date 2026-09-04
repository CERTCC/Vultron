# What's New

Pages added in the last 90 days:

```python exec="true" idprefix=""
import sys
from pathlib import Path

_repo = Path.cwd()
if str(_repo) not in sys.path:
    sys.path.insert(0, str(_repo))

from vultron.metadata.docs.whats_new import added_doc_pages, render_recent_pages

# Emit directory-style relative URLs (markdown-exec output is not rewritten by
# MkDocs); root-absolute links would 404 under the /Vultron/ base path (#3144).
print(render_recent_pages(added_doc_pages(since_days=90)))
```
