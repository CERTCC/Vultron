# Project Ideas

## IDEA-26042402 Convert spec.md files to YAML governed by a pydantic dataclass schema

As our collection of `specs/*.md` files has grown, it's become unwieldy to
enforce and maintain consistent formatting and structure across all the
files. Specs are also inherently a graph of interconnected requirements, and
we need to be able to do things like easily distinguish between different
kinds of requirements. Some are general across any implementation, others
are specific to this particular implementation (e.g., python or library
specific), we have format-based linking between requirements and sometimes
accompanying notes files, but it's all just markdown files with informal
conventions. `wip_notes/spec_registry_design.md` captures some generated notes which we
need to review as part of the ingest process.

The goal is to end up with `specs/*.yaml` files that can be loaded by a
vultron.specs module that creates a registry of all requirements in a
pydantic dataclass structure, so we'd need a full registry, per-file, and
per-spec. We should use strEnums for fixed vocabularies. We should have
structures that capture all the details in the existing markdown files, so
this needs to be a lossless conversion in format without semantic changes to
the content.

A tool to load the specs and generate context for agents to use when
reasoning about requirements would be useful to have as well.

Requirements checks could be made into pre-commit hooks and part of the
pytest suite so we get errors when structure is invalid.

## IDEA-26042403 Add YAML frontmatter to notes/*.md files

Similar to IDEA-26042402, we should add YAML frontmatter to the `notes/*.md`
files to capture file-level metadata such as related spec files, related
notes files, relevant packages, etc. We could also note things like whether
a note is a long-term design idea that will be persistent or a short-term
implementation note that is ephemeral until the tasks that need it are
completed, etc. This will improve our ability to harvest obsoleted notes
into the archive and keep context relevant for active development. We will
need to consider maintenance of the frontmatter and ensure it gets updated
whenever the files are modified, so it may require changes to some
documentation related specs, skills, AGENTS.md, and prompts to ensure that
the frontmatter is maintained consistently with changes to the notes files.

As with specs, yaml frontmatter means we can make a pydantic based loader
that can validate them and make the frontmatter testable as well as build a
graph of the notes and their relationships to each other and to specs. This
could be part of the same tool that loads the specs, so that we have a way
to easily dump "all the notes and specs relevant to topic X" for an agent to
use when reasoning about a topic or task.
