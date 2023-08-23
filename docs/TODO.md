# TO DO

## Generic checklist for every latex->md conversion

- [ ] regex replace acronym pointers with the acronym `\[(\w+)\]\{[^}]+\}` -> `$1`
- [ ] replace first use of an acronym on a page with its expansion (if not already done)
- [ ] OR replace acronym usage with link to where it's defined
- [ ] reproduce diagrams using mermaid
- [ ] replace text about figures to reflect mermaid diagrams
- [ ] replace latex tables with markdown tables
- [ ] replace some equations with diagrams (especially for equations describing state changes)
- [ ] move latex math definitions into note blocks `???+ note _title_` to offset from text
- [ ] move MUST SHOULD MAY etc statements into note blocks with empty title `!!! note ""` to offset from text
- [ ] revise cross-references to be links to appropriate files/sections
- [ ] replace latex citations with markdown citations (not sure how to do this yet)
- [ ] review text for flow and readability as a web page
  - [ ] add section headings as needed for visual distinction
  - [ ] add links to other sections as needed
  - [ ] add links to external resources as needed
  - [ ] replace phrases like `this report` or `this section` with `this page` or similar
  - [ ] add `above` or `below` for in-page cross-references if appropriate (or just link to the section)
  - [ ] reduce formality of language as needed

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
