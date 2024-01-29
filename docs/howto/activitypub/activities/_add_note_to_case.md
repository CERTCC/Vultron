# Add Note to Case

If we think of a case as being a collection of information about a particular
report or set of reports, then a note can be thought of as a comment on
that information. Here we show a note being added to a case.

```python exec="true" idprefix=""
from vultron.scripts.vocab_examples import add_note_to_case, json2md

print(json2md(add_note_to_case()))
```

!!! note "Add vs Create+Target"

    Creating a Note and adding it to a Case is functionally equivalent to Creating
    a Note with the Case as the target. We use the `as:Add` activity to represent
    the addition of an existing object to another object, such as adding a note to 
    a case. However, it is likely acceptable within an ActivityPub implementation to
    use the `as:Create` activity, since the `as:Create` activity includes a `target`
    property that can be used to specify the object to which the newly created object 
    is being attached.
