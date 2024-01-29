# Announce Embargo

The case owner announces an embargo to the case. This is meant to remind case participants of the embargo terms.

```python exec="true" idprefix=""
from vultron.scripts.vocab_examples import announce_embargo, json2md

print(json2md(announce_embargo()))
```

!!! tip "Announce Embargo"

    The `AnnounceEmbargo` activity is used to indicate that an embargo has been
    established or to remind participants of its status. It is used to announce
    the embargo to the case participants. It is also used to draw attention to
    significant changes to the embargo status over and above the corresponding 
    CaseStatus messages, such as when an embargo is deactivated or removed from
    a case.
