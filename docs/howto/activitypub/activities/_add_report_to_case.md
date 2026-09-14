# Add Report to Case

The following example demonstrates how to add a report to a case.
As noted above, this might more commonly be done in the initial case creation process.
However, there are times it may be necessary to treat it separately.
For example, when a second report arrives for a case that already has a report.

```python exec="true" idprefix=""
from vultron.wire.as2.vocab.examples.vocab_examples import add_report_to_case, json2md

print(json2md(add_report_to_case()))
```
