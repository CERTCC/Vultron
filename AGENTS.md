# AGENTS.md — Vultron Project

## Purpose
This file defines mandatory constraints and working rules for AI coding agents operating in this repository.

Agents MUST follow these rules when generating, modifying, or reviewing code.

---

## Scope of Allowed Work
Agents MAY:
- Implement small to medium features
- Refactor existing code without changing external behavior
- Add or update tests
- Improve typing, validation, and error handling
- Propose architectural changes (but not apply them without approval)

Agents MUST NOT:
- Introduce breaking API changes without explicit instruction
- Modify authentication, authorization, or cryptographic logic
- Change persistence schemas or data migration behavior
- Touch deployment, CI, or production configuration unless instructed

---

## Technology Stack (Authoritative)
- Python **3.13+**
- **FastAPI** for HTTP APIs
- **Pydantic v2** for models and validation
- **pytest** for testing
- **mkdocs** with **Material** theme for documentation
- Async-first design where applicable
- **streamlit** for UI prototyping (if needed)

### Development support tools:
- **uv** for package and environment management
- **black** for code formatting
- **mypy** for static type checking
- **pylint** for linting

Agents MUST NOT introduce alternative frameworks without approval.

---

## Architectural Constraints
- FastAPI routers define the external API surface only
- Business logic MUST live outside route handlers
- Persistence access MUST be abstracted behind repository or data-layer interfaces
- Pydantic models are the canonical schema for data exchange
- Side effects (I/O, persistence, network) MUST be isolated from pure logic

Avoid tight coupling between layers.

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

---

## Change Protocol
When making non-trivial changes, agents SHOULD:
1. Briefly state assumptions
2. Describe the intended change
3. Apply the minimal diff required
4. Update or add tests
5. Call out risks or follow-ups

Do not produce speculative or exploratory code unless requested.

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
```

