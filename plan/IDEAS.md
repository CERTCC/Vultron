# Project Ideas

ID format: IDEA-YYMMDDNN

## IDEA-26043001 append-history should reject future dates

The `append-history` command should reject attempts to create history
entries with a frontmatter timestamp in the future. This is probably just a
validator needed in HistoryEntryFrontmatter that compares the timestamp to
current system time and raises an error if it's in the future. I don't think
we need an override for this, and am willing to declare YAGNI on the ability
to create future-dated history entries. This might need to be a history
management spec item just to be sure that agents are aware of it before they
hit an error trying to create a future-dated history entry.
