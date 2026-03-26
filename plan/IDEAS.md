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

## Treat test warnings as errors to be fixed

Test suite warnings from pytest are a sign of technical debt and potential
issues that need to be addressed in the codebase. It is not acceptable to
commit code that generates warnings in the test suite, as this can lead to
overlooked problems and a degraded code quality over time. Update `pyproject.
toml` to reflect the expectation that warnings are errors (hint: tool.pytest.
ini_options, filterwarnings, error). Then update `AGENTS.md`, `specs/`,
and `.github/skills/**/SKILL.md` and any other relevant files where `pytest`
invocation may need to be updated to reflect this change.

## Clarify that IMPLEMENTATION_HISTORY.md is intended to be appended

IMPLEMENTATION_HISTORY.md is intended to serve as an append-only log of
completed tasks, with new entries added to the end of the file as tasks are
completed. We have had instances where agents have inserted new entries at
the top or in the middle of the file. This needs to be addressed in the
documentation to clarify that new entries should always be appended to the
end of the file. Update `plan/IMPLEMENTATION_HISTORY.md` to include a clear
note at the top of the file stating that this file is intended to be an
append-only log and that new entries should always be added to the end of
the file. Also update `AGENTS.md`, and any relevant `specs/*.md` or `.
github/skills/**/SKILL.md` files to reflect this expectation in agent
behavior when updating IMPLEMENTATION_HISTORY.md.
