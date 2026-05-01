---
title: "TOOLS-1 + CONFIG-1 \u2014 Python 3.14 Evaluation + YAML Seed Config\
  \ (2026-04-23)"
type: implementation
timestamp: '2026-04-23T00:00:00+00:00'
source: LEGACY-2026-04-23-tools-1-config-1-python-3-14-evaluation-yaml-see
legacy_file: plan/history/IMPLEMENTATION_HISTORY.md
legacy_line: 7971
legacy_heading: "TOOLS-1 + CONFIG-1 \u2014 Python 3.14 Evaluation + YAML Seed\
  \ Config (2026-04-23)"
date_source: git-blame
legacy_heading_dates:
- '2026-04-23'
---

## TOOLS-1 + CONFIG-1 — Python 3.14 Evaluation + YAML Seed Config (2026-04-23)

**Backfilled from**: `plan/history/IMPLEMENTATION_HISTORY.md:7971`
**Canonical date**: 2026-04-23 (git blame)
**Legacy heading**

```text
TOOLS-1 + CONFIG-1 — Python 3.14 Evaluation + YAML Seed Config (2026-04-23)
```

**Legacy heading dates**: 2026-04-23

### TOOLS-1: Python 3.14 Compatibility Evaluation

**Result**: Tests fail on Python 3.14.0rc2.

**Root cause**: `pydantic==2.13.3` is incompatible with Python 3.14's
changed `typing._eval_type()` internal API. The error:

```text
TypeError: _eval_type() got an unexpected keyword argument 'prefer_fwd_module'
Unable to evaluate type annotation 'ClassVar[MetaData]'.
```

This is a Pydantic/Python 3.14 compatibility issue — `pyproject.toml`
and Docker base images remain at `>=3.12` / `python:3.13-slim-bookworm`
until Pydantic releases Python 3.14 support. Task complete (evaluation
done; conditional update not triggered).

### CONFIG-1: YAML Seed Configuration

Replaced JSON-based actor seed configuration with YAML throughout.

**Changes**:

- `pyproject.toml`: Added `pyyaml>=6.0` to production dependencies.
- `vultron/demo/seed_config.py`: Replaced `json.load()` with
  `yaml.safe_load()`; updated module docstring and `SeedConfig` example.
- `vultron/demo/cli.py`: Updated `--config` help text to say "YAML".
- `docker/seed-configs/`: Converted all 5 seed configs from JSON to YAML
  (`seed-finder.yaml`, `seed-vendor.yaml`, `seed-coordinator.yaml`,
  `seed-case-actor.yaml`, `seed-vendor2.yaml`); deleted old `.json` files.
- `docker/docker-compose-multi-actor.yml`: Updated `VULTRON_SEED_CONFIG`
  references to point to `.yaml` files.
- `test/demo/test_seed_config.py`: Replaced `json.dumps()` with
  `yaml.dump()` in all file-based test fixtures.
- `test/demo/test_multi_actor_seed.py`: Updated all `.json` filename
  references to `.yaml`.
- `vultron/demo/utils.py`: Fixed pre-existing pyright regression introduced
  by updated `types-requests` stubs — changed `**kwargs: object` to
  `**kwargs: Any` in `DataLayerClient.call()`.

### Test results

1812 passed, 12 skipped, 5633 subtests passed. All four linters clean.
