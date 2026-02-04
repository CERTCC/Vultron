# AGENTS.md — Vultron Project

## Purpose
This file defines mandatory constraints and working rules for AI coding agents operating in this repository.

Agents MUST follow these rules when generating, modifying, or reviewing code.

---

## Scope of Allowed Work
Agents MAY:
- Implement small to medium features that do not change public APIs or persistence schemas
- Refactor existing code without changing external behavior
- Add or update tests and test fixtures
- Improve typing, validation, and error handling
- Update documentation, examples, and specification markdown in `docs/` and `specs/`
- Propose architectural changes (but not apply them without approval)

Agents MUST NOT:
- Introduce breaking API changes without explicit instruction
- Modify authentication, authorization, or cryptographic logic
- Change persistence schemas or perform data migrations without explicit instruction
- Touch production deployment, CI configuration, or secrets unless explicitly instructed (see exception below for documentation updates)

Note: Small implementation tweaks (non-architectural) do not require an ADR; architectural or protocol changes (component boundaries, persistence paradigms, message formats, or moving away from ActivityStreams) SHOULD be documented as ADRs before merging. See the ADR guidance in `docs/adr/_adr-template.md` for the format and examples.

---

## Technology Stack (Authoritative)
- Python **3.12+** (project `pyproject.toml` specifies `requires-python = ">=3.12"`); CI currently runs tests on Python 3.13
- **FastAPI** for HTTP APIs
- **Pydantic v2** for models and validation (project pins a specific Pydantic version)
- **pytest** for testing
- **mkdocs** with **Material** theme for documentation
- Async-first design where applicable
- **streamlit** for UI prototyping (if needed)

### Development support tools (approved):
- **uv** for package and environment management (used in CI)
- **black** for code formatting (enforced via pre-commit)
- **mypy** for static type checking (recommended)
- **pylint** / **flake8** for linting (recommended)

Agents MUST NOT introduce alternative frameworks or package managers without explicit approval from the maintainers.

---

## Architectural Constraints
- FastAPI routers define the external API surface only
- Business logic MUST live outside route handlers
- Persistence access MUST be abstracted behind repository or data-layer interfaces
- Pydantic models are the canonical schema for data exchange
- Side effects (I/O, persistence, network) MUST be isolated from pure logic

Avoid tight coupling between layers.

When an agent proposes a non-trivial architectural change (new persistence paradigm, swapping ActivityStreams for a different message model, or a major refactor that impacts component boundaries), it SHOULD prepare an ADR and include migration/compatibility notes and tests.

---

## Coding Rules (Non-Negotiable)
- Prefer explicit types over inference
- Use `pydantic.BaseModel` (v2 style) for structured data
- Do not bypass validation for convenience
- Avoid global mutable state
- Prefer small, composable functions
- Raise domain-specific exceptions; do not swallow errors

Formatting and linting are enforced by tooling; do not reformat unnecessarily.

---

## Testing Expectations
- New behavior MUST include tests
- Tests SHOULD validate observable behavior, not implementation details
- Avoid brittle mocks when real components are cheap to instantiate
- One test per workflow is preferred over fragmented stateful tests

If a change touches the datalayer, include repository-level tests that verify behavior across backends (in-memory / tinydb) where reasonable.

---

## Change Protocol
When making non-trivial changes, agents SHOULD:
1. Briefly state assumptions
2. Describe the intended change
3. Apply the minimal diff required
4. Update or add tests
5. Call out risks or follow-ups

Do not produce speculative or exploratory code unless requested. For proposed architectural changes, draft an ADR (use `docs/adr/_adr-template.md`) and link to relevant tests and design notes.

---

## Safety & Guardrails
- Treat anything under `/security`, `/auth`, or equivalent paths as sensitive
- Do not generate secrets, credentials, or real tokens
- Flag ambiguous requirements instead of guessing

---

## Project Vocabulary
- Use **`vul`** (not `vuln`) as the abbreviation for vulnerability
- Prefer domain terms already present in the codebase
- Do not invent new terminology without justification

---

## Default Behavior
If instructions are ambiguous:
- Choose correctness over convenience
- Choose explicitness over brevity
- Ask for clarification rather than assuming intent

---

## Governance note for agents
- Agents MAY update `AGENTS.md` to correct or clarify agent rules, but substantive changes to this file SHOULD be discussed with a human maintainer via Issue or PR. If an agent edits `AGENTS.md`, it must include a short rationale in the commit message and open a PR for human review.
