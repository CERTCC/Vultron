---
# These are optional elements. Feel free to remove any of them.
status: accepted
date: 2024-04-22
deciders: Allen
---

# Vultron Project Versioning

## Context and Problem Statement

We need to delineate a versioning strategy for the Vultron project to ensure that we can manage changes to the 
protocol and its implementations effectively.

## Decision Drivers

- Release of new documentation
- Changes to the protocol
- Changes to the prototype implementation

## Considered Options

- Semantic Versioning with Major.Minor.Patch
- Calendar Versioning with YYYY.M.Patch
 
## Decision Outcome

Chosen option: "Calendar Versioning", because
we are still in the early stages of the project and are not yet ready to commit to a stable API.
Most of the project consists of documentation and prototypes, so we can use the date to indicate the version.

We will use the format YYYY.MM.Patch, where:
- YYYY is the year of the most recent non-patch release (four digits)
- MM is the month of the most recent non-patch release (no zero padding, e.g., 1, 2, 3, ..., 12)
- Patch is the patch number for that release (default to 0 for the first release in a month, omit for non-patch releases)

Version increments will be as follows:

- Significant releases will use the current year and month, with the patch number starting at 0 (normally omitted)
- Small changes will increment the patch number from the most recent release, even if it is a later month or year

Examples:

- The first significant release in April 2024 will be 2024.4.0 (shortened 2024.4)
- The third small update to v2024.4 will be 2024.4.3, even if it is released in May 2024 or later.
- A subsequent significant release in September 2024 would be 2024.9.0 (shortened 2024.9)


### Consequences

- Good, because we can easily track the progress of the project and the changes to the protocol and its implementations.
- Good, because we can still communicate the relative importance of versions
- Bad, because we may need to change the versioning strategy if we decide to commit to a stable API in the future
- Neutral, because the versioning strategy is not as widely recognized as semantic versioning, but it is still
  a common practice for projects that are more complex than a simple library or tool.'
- Neutral, because we are not committing to either a release schedule or a stable API at this time.

## Pros and Cons of the Options

### Semantic Versioning

- Good, because it is widely recognized and understood
- Good, because it can communicate the relative importance of versions and the impact of changes
- Bad, because it may not be appropriate for projects like Vultron that are still in the early stages of implementation
- Neutral, because pre-1.0 versions lose granularity in the version number, having only a minor and patch number
- Neutral, because it is not as well-suited for projects that are primarily documentation and prototypes

## More Information

- [Semantic Versioning](https://semver.org/)
- [Calendar Versioning](https://calver.org/)
