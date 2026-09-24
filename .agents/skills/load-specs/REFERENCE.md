# Load Specs — Output Reference

## `--index` output

```text
# spec map: 69 topics, 3087 reqs. Load with: ...
ARCH  Architecture  (N reqs)
  ARCH-01  group title (N)
```

The first line is a header. Each topic line is `ID  Title  (N reqs)`. Each
group line is `GROUP-ID  title (N)`, indented two spaces. The counts show
only requirements that match the other flags. Topics and groups with no
match are left out.

## `--text` output

```text
# N requirements, statements only. Relationships, verification, and tags are
# omitted here — drop --text for the full JSON record of any ID below.
ARCH  Architecture
  ARCH-01  group title
    ARCH-01-001 MUST  The statement, whitespace-collapsed to one line.
```

Same topic/group nesting as `--index`, with one line per requirement:
`ID PRIORITY  statement`, indented four spaces. This is the default form for
loading requirements — the JSON forms print as a single line, so a large
selection shows only a truncated prefix. `--text` requires a selection.

## JSON structure

```json
{"topics": [...], "requirements": [...], "edges": [...]}
```

### `topics`

One entry per spec topic that has a selected requirement. Fields: `id`,
`title`, `version` (with `--slim`: `id` and `title` only).

### `requirements`

| Field | Meaning |
|---|---|
| `id` | Unique requirement ID (e.g. `ARCH-01-001`) |
| `topic` | Parent spec topic ID (e.g. `ARCH`) |
| `group` | Group ID (e.g. `ARCH-01`) |
| `group_title` | Human-readable group name |
| `type` | `behavioral` or `statement` |
| `priority` | `MUST`, `MUST_NOT`, `SHOULD`, `SHOULD_NOT`, or `MAY` |
| `statement` | The normative requirement text |
| `kind` | `protocol`, `architecture`, `project`, or `process` |
| `scope` | List: `prototype`, `production`, or both |
| `tags` | Optional topic tags |
| `rationale` | Optional explanatory text |
| `note` | Optional caveat (for example, which side an obligation binds) |
| `relationships` | Optional list of `{rel_type, spec_id, note?}` |
| `verification` | How the requirement is verified, or `null` |

With `--slim`, a record has only `id`, `priority`, `statement`, and `note`
(when set).

### `edges`

All relationships of the selected requirements, plus `derives_from` edges to
ADRs:

```json
{"from": "ARCH-01-001", "rel_type": "depends_on", "to": "CS-01-001"}
```

With `--slim`, only relationship edges whose two ends are both selected
remain.

## Usage examples

```bash
# Map, narrowed to protocol requirements
PYTHONPATH= uv run spec-dump --index --kind protocol

# Two topics plus cross-cutting constraints, compact
PYTHONPATH= uv run spec-dump --topic CM,EP --cross-cutting --text

# One requirement and everything it depends on, full records
PYTHONPATH= uv run spec-dump --ids EP-04-001 --deps

# MUST requirements in a group
PYTHONPATH= uv run spec-dump --group ARCH-01 --priority MUST

# Full corpus (spec-audit only; ~2.5 MB, warns on stderr)
PYTHONPATH= uv run spec-dump > /tmp/specs.json
```
