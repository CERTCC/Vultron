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

Closely related is IDEA-26043002

## IDEA-26043002 history log entries should use tz-aware timestamps

Currently, `HistoryEntryFrontmatter` uses `date: datetime.date` instead of a
tz-aware ISO 8601 / RFC 3339 timestamp. This means that the monthly readme
gets sorted by day but not time. We should either update the `date` field to
be a tz-aware timestamp, or add a new `time` field that is tz-aware and
use that combined with `date` to sort the history entries. If we use
separate fields, we retain backwards compatibility with existing history
entries. As part of any change we make for this we should also retroactively
update existing history entries to have tz-aware timestamps in the desired
format assuming that the datetime found in git log history for the file is
on the same day as the asserted date (we cannot trust datetime from git log
for entries prior to mid-April 2026 because we only backfilled the history
files in the recent past. Many older entries will have a create date long
after their asserted date. For those entries, we should just set a timestamp
of 00:00:00 on the asserted date, use the git log timestamp for entries
where the git log date matches the `date:`, and going forward always use the
current system time for creating new history entries. If it is not already
implemented this way, `append-history` should default to the current time
when creating both `date:` and `time:` fields for new history entries
without being told what time to use -- the `append-history` command itself
can be the timestamper-of-record for new entries, reducing the chance that
agents will create entries with inconsistent timestamps. This should be
enforced in specs and tooling as needed.
