| State | Meaning |
|---|---|
| `UNINVITED` | Not asked about this embargo; the start state of every row |
| `INVITED` | Asked, with no answer yet; carries that invitation's RSVP deadline |
| `AGREED` | Agreed to this embargo: explicitly, as its proposer, by seeding, or by carry-over |
| `DECLINED` | Explicitly refused this embargo, or withdrew from it |
| `TIMED_OUT` | Invited, and the RSVP deadline passed with no answer; not a refusal |
