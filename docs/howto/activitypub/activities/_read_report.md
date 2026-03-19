# Read Report

The vendor reads the vulnerability report, acknowledging that they have received it.

```python exec="true" idprefix=""
from vultron.wire.as2.vocab.examples.vocab_examples import read_report, json2md

print(json2md(read_report()))
```
