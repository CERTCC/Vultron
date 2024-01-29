# Add Participant to Case

Here we provide two examples of adding a participant to a case.

## Vendor adds self to case

In the first example, the vendor actor adds itself to the case in the vendor role.
Normally, this might not be done as a separate step, but would be done as part of the
creation of the case itself.

```python exec="true" idprefix=""
from vultron.scripts.vocab_examples import add_vendor_participant_to_case, json2md

print(json2md(add_vendor_participant_to_case()))
```

## Vendor adds finder to case

In the second example, the vendor actor adds the finder to the case in the finder and reporter roles.
Again, this might not be done as a separate step, and could be done as part of the
case creation step. But we include it here to show how to add multiple participants to a case.

For example, if a finder reported a vulnerability that was already known to the vendor, the vendor
might add the finder to the case in the reporter role, but not in the finder role.

```python exec="true" idprefix=""
from vultron.scripts.vocab_examples import add_finder_participant_to_case, json2md

print(json2md(add_finder_participant_to_case()))
```
