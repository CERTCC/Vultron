# Add Report to Case

Below we demonstrate how to add a report to a case.
As noted above, this might more commonly be done in the initial case creation process.
However, we show it here since there are times it may be necessary to treat it separately.
For example, when a second report arrives for a case that already has a report.

```python exec="true" idprefix=""
from vultron.scripts.vocab_examples import add_report_to_case, json2md

print(json2md(add_report_to_case()))
```
