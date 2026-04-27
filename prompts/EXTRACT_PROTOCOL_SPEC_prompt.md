## Objective

Review older project documentation to extract a list of requirements
previously defined in the project documentation.

## Tasks

### Primary constraints

- Modify only the `specs/vultron-protocol-spec.yaml`
- Do not modify code or tests or any other files.

### Study and understand the documentation

1. Search all markdown (`*.md`) files in `docs/` to discover capitalized
   occurrences of RFC 2119 keywords (e.g., "MUST", "SHOULD", "MAY") to
   identify candidate requirements.
   1. Note that `docs/howto/em_icalendar.md` was written at a time when we were
      considering iCalendar as a potential format for embargo representation.
      That is no longer the case. However, there may be some ideas in that file
      that are still relevant regarding privacy concerns in embargo
      representation.
2. Review identified occurrences in context to determine if they represent
   valid requirements that should be extracted, or if they are false positives (e.g.,
   usage of "must" in a non-requirements context).
3. For valid requirements, extract the requirement text and reformat it according to the style used in `specs/meta-specification.yaml`, including:
   1. Assigning a unique requirement ID (e.g., `VP-01-001`) following the existing convention.
   2. Adding the `PROD_ONLY` tag if the requirement only applies to production.
   3. Clearly indicating in the text of the requirement what the requirement is about, especially if it is not immediately clear from the context.
   4. Ensuring that the requirement is atomic, specific, concise, and verifiable.
   5. For each requirement, include a reference to the source document and
      section where it was found for traceability
4. Compose a new markdown file `specs/vultron-protocol-spec.yaml` to capture
the extracted requirements related to the Vultron Protocol.
   1. Follow
      guidance in `specs/meta-specification.yaml` for formatting and organization
      of the spec file.
   2. Do not split `vultron-protocol-spec.md` into multiple  
      files; keep all protocol-related items in a single file for now, even
      if there are multiple topics.
   3. Use headings to organize different topics within the file as needed.
   4. Use the `PROD_ONLY` tag for any requirements that only apply to
      production (i.e., not prototoype), and
      clearly indicate in the text of the requirement what the requirement is about.
5. Git add and commit the new `specs/vultron-protocol-spec.yaml` file with a descriptive commit message.
6. EXIT
