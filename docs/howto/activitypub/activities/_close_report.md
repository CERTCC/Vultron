# Close Report

The vendor closes an invalid vulnerability report, which implies that they
will not be taking further action on the vulnerability.

```python exec="true" idprefix=""
from vultron.wire.as2.vocab.examples.vocab_examples import close_report, json2md

print(json2md(close_report()))
```
