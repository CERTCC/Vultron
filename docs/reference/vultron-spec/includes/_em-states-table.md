| State | Meaning | Embargo register entries |
|---|---|---|
| None | No embargo is in effect for this case, and none is proposed | none `ACTIVE`, `PROPOSED` or `TERMINATED` |
| Proposed | At least one embargo is proposed, and none is in force | one or more `PROPOSED`, none `ACTIVE` |
| Active | An embargo is in force, and no revision is open | one `ACTIVE`, none `PROPOSED` |
| Revised | An embargo is in force, and at least one revision of it is open | one `ACTIVE`, one or more `PROPOSED` |
| Exited | The embargo has been torn down | one `TERMINATED` |
