# Load Specs — Output Reference

## JSON Structure

```json
{
  "topics": [...],
  "requirements": [...],
  "edges": [...]
}
```

### `topics`

One entry per spec topic (source file). Fields: `id`, `title`, `version`, `kind`.
Use to resolve the short `topic` field on each requirement to a human-readable title.
Do not open source YAML files — all requirement content is in `requirements`.

### `requirements`

| Field | Meaning |
|---|---|
| `id` | Unique requirement ID (e.g. `ARCH-01-001`) |
| `topic` | Parent spec topic ID (e.g. `ARCH`) |
| `group` | Group within the file (e.g. `ARCH-01`) |
| `group_title` | Human-readable group name |
| `priority` | `MUST`, `MUST_NOT`, `SHOULD`, `SHOULD_NOT`, or `MAY` |
| `statement` | The normative requirement text |
| `kind` | `domain`, `general`, `implementation`, `language`, or `pattern` |
| `scope` | List: `prototype`, `production`, or both |
| `type` | Always `behavioral` |
| `relationships` | Optional inline list of `{rel_type, spec_id, note?}` edges |
| `rationale` | Optional explanatory text |

### `edges`

Centralized list of all relationships across all files:

```json
{"from": "ARCH-01-001", "rel_type": "depends_on", "to": "CS-01-001"}
```

Edge `rel_type` values: `constrains`, `depends_on`, `derives_from`, `implements`, `refines`.

## Usage examples

```bash
# Full dump
PYTHONPATH= uv run spec-dump

# Write to file
PYTHONPATH= uv run spec-dump > /tmp/specs.json

# Count requirements
PYTHONPATH= uv run spec-dump | python -c "import json,sys; r=json.load(sys.stdin); print(len(r['requirements']))"

# Filter MUST requirements
PYTHONPATH= uv run spec-dump | python -c "
import json, sys
data = json.load(sys.stdin)
musts = [r for r in data['requirements'] if r['priority'] == 'MUST']
print(f'{len(musts)} MUST requirements')
"
```
