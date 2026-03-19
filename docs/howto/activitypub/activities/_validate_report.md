# Validate Report

The vendor validates the vulnerability report, which implies that they will
shortly create a case to track the vulnerability response.

```python exec="true" idprefix=""
from vultron.wire.as2.vocab.examples.vocab_examples import validate_report, json2md

print(json2md(validate_report()))
```
