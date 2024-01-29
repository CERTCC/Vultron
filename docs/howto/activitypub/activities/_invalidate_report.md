# Invalidate Report

The vendor invalidates the vulnerability report, which implies that they will
not be taking further action on the vulnerability. They may choose to hold
the report open for a period of time before closing it in order to allow the reporter to
provide additional information that could change the vendor's decision.

```python exec="true" idprefix=""
from vultron.scripts.vocab_examples import invalidate_report, json2md

print(json2md(invalidate_report()))
```
