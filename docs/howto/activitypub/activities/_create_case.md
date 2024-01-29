# Create Case

A vendor creates a case in response to a vulnerability report.
Here we show a case creation including a single participant and a pointer to a report.
In practice, a case may have multiple participants and (less often) multiple reports.
See also  [Initializing a Case](./initialize_case.md).

```python exec="true" idprefix=""
from vultron.scripts.vocab_examples import create_case, json2md

print(json2md(create_case()))
```
