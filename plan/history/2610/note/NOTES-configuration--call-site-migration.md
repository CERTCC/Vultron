---
source: NOTES-configuration--call-site-migration
timestamp: '2026-10-02T16:20:19.024101+00:00'
title: Call-site Migration
type: note
---

**Archived:** 2026-10-02
**Reason:** delivered — call sites use get_config()
**Superseded by:** vultron/config (get_config())

---

## Call-site Migration

### Before (scattered os.environ.get)

```python
# vultron/adapters/utils.py
BASE_URL = os.environ.get("VULTRON_BASE_URL", "https://demo.vultron.local/")

# vultron/adapters/driven/datalayer_sqlite.py
_DEFAULT_DB_URL = os.environ.get("VULTRON_DB_URL", "sqlite:///vultron.db")

# vultron/adapters/driving/fastapi/app.py
log_level_name = os.environ.get("LOG_LEVEL", "INFO").upper()
```

### After (unified get_config())

```python
from vultron.config import get_config

# vultron/adapters/utils.py
BASE_URL = get_config().server.base_url

# vultron/adapters/driven/datalayer_sqlite.py
_DEFAULT_DB_URL = get_config().database.db_url

# vultron/adapters/driving/fastapi/app.py
log_level_name = get_config().server.log_level
```

### FastAPI Depends injection

```python
from fastapi import Depends
from vultron.config import AppConfig, get_config

@router.get("/info")
async def info(config: AppConfig = Depends(get_config)):
    return {"base_url": config.server.base_url}
```

---
