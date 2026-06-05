# How to find your way around the codebase

Use this guide when you need a fast orientation to the files maintainers touch
most often.

## Start from the architecture pipeline

Use this request path as your map:

`FastAPI inbox -> AS2 parser/extractor -> dispatcher -> use-case`

Primary files:

- `vultron/adapters/driving/fastapi/routers/actors.py`
- `vultron/wire/as2/parser.py`
- `vultron/wire/as2/extractor.py`
- `vultron/core/dispatcher.py`
- `vultron/core/use_cases/`

## Find semantic routing points

Check these first when adding or debugging message types:

- `vultron/core/models/events/base.py` (`MessageSemantics`)
- `vultron/wire/as2/extractor.py` (`SEMANTICS_ACTIVITY_PATTERNS`)
- `vultron/core/use_cases/use_case_map.py` (`USE_CASE_MAP`)

## Find canonical maintainer guidance

Use these as source-of-truth jump points:

- Codebase reference: `docs/reference/codebase/index.md`
- Durable design notes: `notes/README.md` (in-repo path)
- Agent operating rules: `AGENTS.md` (in-repo path)
- Skill procedures: `.agents/skills/*/SKILL.md` (in-repo path)

## Troubleshooting

- If behavior seems to cross layers incorrectly, verify imports against
  hexagonal rules before debugging runtime symptoms.
- If naming seems inconsistent, check AGENTS naming conventions before
  introducing new terms.
