# Project Ideas

## Evaluate readiness and upgrade to Python 3.14

Python 3.14.3 is the latest stable Python release as of this writing. Since
we have been developing the prototype using Python 3.12 and 3.13, we should
try an upgrade in a branch to 3.14 to see if everything works as expected so
we can take advantage of the latest language features and improvements. If
it works without issue, we can make it permanent. Otherwise we can abandon
the upgrade and stay with what we have.

## Get rid of `as_` prefix on fields across the board

The difference between when to use `as_object` and `object_`  (and
all other `as_<python_keyword>` vs `<python_keyword>_` fields) depending on
which vultron submodule you're in is a source of confusion and inconsistency.
We should just go through and standardize on the "trailing underscore"
convention for all fields across the codebase where there is a conflict with
a Python reserved keyword. (Note that *prefixing* with an underscore is not
an option because these are not private fields to begin with, and Pydantic will
complain about private fields with leading underscores.) So
underscore-suffix is the way to go for all fields that conflict with
reserved keywords. Create a task to do a global search and replace for any
`as_` prefixed fields and replace them with the trailing underscore
convention. E.g., `as_foo` becomse `foo_`. Note that this requirement only
applies to fields, not to class names where the `as_` prefix is actually  
helpful to indicate that it's an ActivityStreams-specific model. Update  
`specs/`, `notes/`, `AGENTS.md`, `plan/` docs as appropriate to reflect this
new naming convention (but only where the `as_` prefix is used in the
context of a field name).
