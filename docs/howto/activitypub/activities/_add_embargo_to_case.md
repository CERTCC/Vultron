# Add Embargo to Case

The case owner adds an embargo to the case. This is the generic form of activating an embargo,
and is mainly included to allow for a case owner to add an embargo to a case without having to
first propose the embargo to the case.
In most cases, the case owner will activate an embargo in response to an embargo proposal.

```python exec="true" idprefix=""
from vultron.scripts.vocab_examples import add_embargo_to_case, json2md

print(json2md(add_embargo_to_case()))
```
