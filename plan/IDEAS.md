# Project Ideas

## ~~Add pyright for linting and type checking~~

> **Captured in**: `specs/tech-stack.md` `IMPL-TS-07-002`

~~We'd like to start using pyright for static type checking and linting (in~~
~~addition to black for formatting). This will help us catch type errors and~~
~~enforce consistent type annotations across the codebase. However, since this~~
~~is a new requirement, we should make a gradual transition to it rather than~~
~~enforcing it immediately on all code. What this might look like in practice~~
~~is that we add pyright to the project and run it on all the existing code,~~
~~noting any critical errors as technical debt to be addressed over time, then~~
~~enforce it on all new and modified source going forward. We might also~~
~~leverage the pyright configuration to allow for gradual adoption, such as by~~
~~setting a higher error threshold for existing code and a stricter threshold~~
~~for new code or ignoring less critical errors in legacy code while enforcing~~
~~all errors in new code. It is possible that we might want to use different~~
~~configuration files depending on which folder we are in, or based on whether~~
~~we're checking old code vs new code. Use expert knowledge of pyright~~
~~configuration to design an effective strategy for this transition and ensure~~
~~that it is captured as part of the specs and implementation plan for the~~
~~project.~~

