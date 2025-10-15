# GitHub Copilot Instructions for Vultron

## Project Overview

Vultron is a research project exploring the creation of a federated, decentralized, and open source protocol for Coordinated Vulnerability Disclosure (CVD). This project emerged from the CERT/CC's decades of experience in coordinating global responses to software vulnerabilities.

### Key Concepts

- **CVD (Coordinated Vulnerability Disclosure)**: A process for multiple parties to coordinate the disclosure and remediation of security vulnerabilities
- **Multi-Party CVD (MPCVD)**: Extension of CVD to involve multiple vendors, coordinators, finders, and other stakeholders
- **Behavior Trees**: The modeling approach used to simulate and implement the Vultron protocol
- **ActivityStreams Vocabulary**: The message format used for Vultron protocol communications

## Architecture Decision Records (ADRs)

**Important**: This project uses Architecture Decision Records (ADRs) to document significant decisions. ADRs are located in `docs/adr/` and should be consulted when making architectural changes.

### Key Architectural Decisions

1. **ADR-0000**: Record architecture decisions using ADRs
2. **ADR-0001**: Use MADR (Markdown Any Decision Records) format for all decision documentation
3. **ADR-0002**: Model Vultron processes as Behavior Trees to handle complex state machine interactions
4. **ADR-0003**: Build a custom Python Behavior Tree engine tailored to Vultron's needs
5. **ADR-0004**: Use factory methods for common BT (Behavior Tree) node types to maintain consistency and flexibility
6. **ADR-0005**: Use ActivityStreams Vocabulary as the basis for Vultron message formats
7. **ADR-0006**: Use Calendar Versioning (CalVer: YYYY.MM.Patch) for project versioning

When proposing changes that affect architecture, consider whether an ADR should be created or updated. Follow the template at `docs/adr/_adr-template.md`.

## Code Structure

- **`vultron/`**: Main Python package
  - **`vultron/bt/`**: Behavior Tree implementation (base classes and Vultron-specific nodes)
  - **`vultron/demo/`**: Demonstration and simulation code
  - **`vultron/scripts/`**: Utility scripts, including ActivityStreams vocabulary examples
- **`docs/`**: Project documentation (MkDocs-based)
  - **`docs/adr/`**: Architecture Decision Records
- **`test/`**: Test files
- **`doc/examples/`**: Example files demonstrating protocol usage

## Development Guidelines

### Python Standards

- **Python Version**: Requires Python 3.12+
- **Code Formatting**: Use [Black](https://black.readthedocs.io/en/stable/) for code formatting
- **Type Hints**: Use type hints throughout the codebase
- **Dependencies**: Managed via `pyproject.toml` with `uv.lock`

### Key Technologies and Libraries

- **Pydantic**: Used for data modeling and validation
- **NetworkX**: Used for graph operations
- **pandas**: Used for data analysis in simulations
- **MkDocs Material**: Documentation site generator
- **OWL/RDF libraries**: For ontology work (owlready2, rdflib)

### Testing

- Run tests to ensure changes don't break existing functionality
- Follow existing test patterns in the `test/` directory

### Linting and Pre-commit

- Project uses pre-commit hooks (`.pre-commit-config.yaml`)
- Markdown linting via `.markdownlint-cli2.yaml`
- Flake8 configuration in `.flake8`
- MyPy configuration in `.mypy.ini`

## Domain-Specific Conventions

### State Machines

The Vultron protocol is built around three interacting state machines:

1. **Report Management (RM)**: Tracks the lifecycle of vulnerability reports
2. **Embargo Management (EM)**: Manages coordinated disclosure timelines
3. **Case State (CS)**: Tracks the overall case status

### Behavior Trees

- Use factory methods (not direct subclassing) to create BT nodes for consistency
- Keep `vultron.bt.base` focused on base classes
- Keep Vultron-specific logic in higher-level modules

### Message Format

- Messages use ActivityStreams Vocabulary semantics
- Examples in `vultron/scripts/vocab_examples.py` and `doc/examples/`
- Messages follow ActivityPub-compatible patterns for future federation

## Contribution Process

1. **Review Contribution Instructions**: See `ContributionInstructions.md` for legal requirements
2. **Discuss First**: For significant changes, open an Issue or Discussion before submitting a PR
3. **Follow CONTRIBUTING.md**: See `CONTRIBUTING.md` for detailed contribution guidelines
4. **Consider ADRs**: Significant architectural changes should be documented as ADRs
5. **Code Owner**: @ahouseholder is the primary code owner (see `.github/CODEOWNERS`)

## Documentation

- Documentation is built with MkDocs Material
- Use `mkdocs.yml` for configuration
- Include markdown documentation alongside code changes when appropriate
- Examples should be generated via `vultron/scripts/vocab_examples.py`

## Project Status

This is a research prototype and is **not production-ready**. The focus is on:

- Prototyping the Vultron protocol
- Demonstrating feasibility of federated CVD
- Exploring behavior tree modeling for CVD processes
- Building a foundation for future interoperability

## Key References

- [Designing Vultron (2022 Report)](https://resources.sei.cmu.edu/library/asset-view.cfm?assetid=887198)
- [CERT Guide to CVD](https://certcc.github.io/CERT-Guide-to-CVD)
- [ActivityStreams Vocabulary](https://www.w3.org/TR/activitystreams-vocabulary/)
- [Behavior Trees in Robotics and AI](https://arxiv.org/abs/1709.00084)

## Code Style Notes

- Minimize use of comments; prefer self-documenting code
- When comments are needed, match the style of existing comments in the file
- Use existing libraries whenever possible
- Only add new libraries or update versions if absolutely necessary
