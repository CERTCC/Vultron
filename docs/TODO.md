# TO DO

## Generic checklist for every latex->md conversion

- [x] regex replace acronym pointers with the acronym `\[(\w+)\]\{[^}]+\}` -> `$1`
- [ ] replace first use of an acronym on a page with its expansion (if not already done)
- [ ] OR replace acronym usage with link to where it's defined
- [x] reproduce diagrams using mermaid
- [x] replace text about figures to reflect mermaid diagrams
- [x] replace latex tables with markdown tables
- [x] replace some equations with diagrams (especially for equations describing state changes)
- [x] move latex math definitions into note blocks `???+ note _title_` to offset from text
- [x] move MUST SHOULD MAY etc statements into note blocks with empty title `!!! note ""` to offset from text
- [x] revise cross-references to be links to appropriate files/sections
- [x] replace latex citations with markdown citations (not sure how to do this yet)
- [x] review text for flow and readability as a web page
  - [x] add section headings as needed for visual distinction
  - [x] add links to other sections as needed
  - [x] add links to external resources as needed
  - [ ] replace phrases like `this report` or `this section` with `this page` or similar
  - [x] add `above` or `below` for in-page cross-references if appropriate (or just link to the section)
  - [x] reduce formality of language as needed

## Clean up

### Report Management
- [x] [report_management.md](rm/index.md)
- [x] [rm_interactions.md](rm/rm_interactions.md)

### Embargo Management
- [ ] [em/index.md](em/index.md)
- [ ] [em/defaults.md](em/defaults.md)
- [ ] [em/early_termination.md](em/early_termination.md)
- [ ] [em/em_dfa_diagram.md](em/em_dfa_diagram.md)
- [ ] [em/nda-sidebar.md](em/nda-sidebar.md)
- [ ] [em/negotiating.md](em/negotiating.md)
- [ ] [em/principles.md](em/principles.md)
- [ ] [em/working_with_others.md](em/working_with_others.md)
- 
