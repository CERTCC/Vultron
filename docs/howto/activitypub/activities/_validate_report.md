# Validate Report

The vendor validates the vulnerability report, which implies that they will
shortly create a case to track the vulnerability response.

```python exec="true" idprefix=""
from vultron.scripts.vocab_examples import validate_report, json2md

print(json2md(validate_report()))
```
