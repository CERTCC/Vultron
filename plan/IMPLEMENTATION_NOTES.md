# Implementation Notes

This file tracks insights, issues, and learnings during implementation.

## Case object notes

An early design for the case object is found in `docs/howto/case_object.md`.
The implementation is in `vultron/as_vocab/objects/vulnerability_case.py`. 
The documentation will need to be updated to reflect the final 
implementation. This is not a high priority right now, just a note to capture
it into the knowledge base for future reference.

## Process models and formal protocol notes

Process model notes can be found in `docs/topics/background/overview.md` with
even more detail in `docs/topics/process_models/**/*.md`. Keep in mind that 
these files were all written prior to the implementation, so they are 
informative but not necessarily reflective of the implementation details. 
However, when the implementation significantly diverges from these 
descriptions, it is worth asking whether the documentation should be updated 
to reflect the implementation, or whether the implementation is diverging
from the intended design.

Formal protocol models exist in `docs/reference/formal_protocol/*.md`. These
correspond to the process models and are also informative but not necessarily 
reflective of the implementation details. Again, changes to the implementation
that significantly diverge from these models should be evaluated for whether the
documentation should be updated or whether the implementation is diverging from
the intended design.

## Case states and what you can do in them

There are suggestions about what actions can be taken in different case states
in `docs/reference/case_states/*.md`. These are derived from pattern matches
found in `vultron/case_states/patterns/*.py` with enums in 
`vultron/case_states/enums/*.py`. These are not required actions, they are more
like a menu of options that an actor might take when the case is in a given 
state. This could be useful for future UI design, or for future agents to 
understand what sorts of actions are possible.

## Vocabulary Examples

The vocabulary examples in `vultron/scripts/vocab_examples.py` are important for
documentation, testing, and demonstration purposes. They should be kept up 
to date with the current implementation of the vocabulary. They can also be used
as a reference for testing the message semantics patterns in  
`vultron/activity_patterns.py`. The examples, method names, and type hints 
should provide enough information to understand how the semantics and 
ActivityStreams vocabulary fit together into the process models.

## Need to reorganize top-level modules

There are a few top-level modules in `vultron/` that probably should be 
reorganized into submodules. They were initially created as top-level modules 
for ease of development, but they are starting to make the `vultron/` directory 
look a bit cluttered. This is not a high priority right now, but it is
something to keep in mind for future refactoring.

Specifically, consider reorganizing:
- `activity_patterns.py`
- `behavior_dispatcher.py`
- `dispatcher_errors.py`
- `enums.py`
- `errors.py`
- `semantic_handler_map.py`
- `semantic_map.py`
- `types.py`

## Refactoring of enums spread across modules

There are enums scattered throughout the codebase. It might make sense at 
some point to reorganize these into a single `vultron/enums/` module with 
submodules for different categories of enums. This would make it easier to find
and manage the enums, and also provide an opportunity to review and clean up any
redundant or unused enums.

## Behavior simulator

There is a ton of behavior logic to be mined from `vultron/bt/**/*.py` that
is informative for understanding the behavior patterns of the intended system.
Much of this logic is not currently being used in the implementation as it is 
from an older simulation, but it is absolutely relevant to the newer 
`vultron/behavior` modules. The documentation that was used as the original 
design for `vultron/bt` is found in `docs/topics/behavior_logic/*.md`.
It may be useful to index these files and map out correspondences between 
the docs and the simulation code and make notes as to how those might relate to
the current implementation. Priority of this depends on how useful it would 
be. It could be worth doing in order to update some `notes/*.md`files with 
insights and hints for future reference.

## "Do Work" behaviors are largely placeholders

Throughout the behavior simulator and documentation, there are a number of 
items under the `do work` node that are largely placeholders for actors to do 
things that are not yet fully specified for automation. These can be though 
of as tasks that the system might need to pose as tasks to an actor (human or 
machine) in order to make progress on a case. Some of them may be more 
amenable to automation than others, we have not yet done a thorough analysis of
which ones those are. It could be useful to review these and make notes about
which ones might be more or less amenable to automation, and what sorts of
actions an agent might take to accomplish them. This could be useful for future
UI design, or for future agents to understand what sorts of actions are possible.

## Code documentation (static and dynamic)

We maintain code documentation in `docs/reference/code/**/*.md` that is 
generated from docstrings in the codebase. This documentation should be updated
to reflect the current implementation, and should be kept up to date with any future
changes to the codebase. This documentation is intended for inclusion in our 
static web site (produced by mkdocs from `/docs`). The organization of this 
section to date has been rather ad-hoc and not very comprehensive. It could 
stand to be reviewed and reorganized to be more systematic and comprehensive, but
this is not a high priority for the prototype.

API documentation is generated via FastAPI's built-in OpenAPI support, which is
available at `/docs` when the server is running. This documentation is intended 
for developers who are interacting with the API, and should be kept up to date 
with any changes to the API endpoints or request/response formats. API 
documentation that is automatically generated and made available via the FastAPI
server is a higher priority to maintain than the static code documentation, as
it is more likely to be used by developers and agents interacting with the 
running system.

## ISO standards cross-references

We have a number of ISO standards that are relevant to our domain, and we've 
documented high-level cross-references to those standards in 
`docs/reference/iso_crosswalks/*.md`. As the system development progresses, it
may be useful to review these crosswalks to incorporate more of the 
ActivityStreams vocabulary implementation details and make more specific
references to how the ISO standards relate to the implementation. 
This is not a high priority right now, but it could be useful for future 
reference and for ensuring that our implementation is aligned with relevant standards.

## Measuring the CVD process using the case state model

There is considerable documentation (based on a research paper) to be found in 
`docs/topics/measuring_cvd/*.md` that describes how to use the sequence of 
events in the case state model to measure the "quality" of the CVD process. 
There is some code that implements this scoring model (and the Hasse diagram of
case states) in `vultron/case_states/hypercube.py`. Applying these techniques
to analyze the implemented `VulnerabilityCase` objects and their history 
would be a useful addition to the system in the future, although it is not a 
high priority for the prototype.

## Broad advice about documentation vs implementation

In general, the documentation in `docs/**/*.md` predates the implementation and
was the original source material for the first few iterations of implementation.
Files like `vultron/case_states/hypercube.py` were some of the earliest 
implementations when we were still working out the details of the case state 
model in a paper called [*A State-Based Model for Coordinated Vulnerability 
Disclosure*](https://www.sei.cmu.edu/documents/1952/2021_003_001_737890.pdf).
The behavior tree implemenation in the simulator (`vultron/bt/**/*.py`) 
and `vultron/demo/vultrabot.py` was also an early implementation that was 
based on the second paper in our series [*Designing Vultron*](https://www.sei.cmu.edu/documents/1954/2022_003_001_887202.pdf)
Both of these papers and the documentation and implementation came before our
decision to implement this using ActivityStreams vocabulary and most of the 
current codebase. So while the documentation is informative for understanding the original
design and the intended behavior patterns, it is not necessarily reflective of the
current implementation details. As the implementation progresses, it may be useful to
review the documentation and update it to reflect the current implementation,
or to make notes about where the implementation diverges from the original design 
and why. Some documentation may eventually be appropriate to archive into a 
clearly marked "historical" section of the docs, while other documentation may be worth
updating to reflect the current implementation. This is not a high priority 
for the prototype, but it could be useful for future reference and for ensuring 
that our documentation is aligned with our implementation.