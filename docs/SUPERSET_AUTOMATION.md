# Superset Automation Integration

Automation and integration guide for Apache Superset, using the built-in `superset/` Python package and the ML service Superset endpoints.

This repository ships a lightweight Superset client in `superset/` (sync + optional async), plus an ML API router exposing a few common operations under `/superset/*`.

## What’s included

- **Python client**: `superset/client.py`
  - Login (username/password) or API key auth
  - CSRF handling for mutating requests
  - Retry/backoff for transient failures
- **ML API endpoints**: `ml/app/api/superset.py`
  - `GET /superset/health`
  - `GET /superset/dashboards`
  - `POST /superset/dashboards`
  - `GET /superset/datasets`
  - `POST /superset/datasets/{dataset_id}/refresh`
  - `POST /superset/datasets/refresh` (macro-friendly)
  - `POST /superset/sql/execute`

## Configuration

Set environment variables (recommended via `.env` / docker-compose environment):

- `SUPERSET_URL` (default `http://localhost:8088`)
- `SUPERSET_USERNAME` / `SUPERSET_PASSWORD` (for login auth)
- OR `SUPERSET_API_KEY` (for API-key auth)
- `SUPERSET_TIMEOUT` (default `30`)

## Examples

### Python (direct client)

```python
from superset.config import SupersetConfig
from superset.client import SupersetClient

cfg = SupersetConfig.from_env()
client = SupersetClient(cfg.base_url, cfg.username, cfg.password, cfg.api_key, config=cfg)

# Authenticate if using username/password
if not cfg.api_key and cfg.username and cfg.password:
    client.login()

print(client.get_version())
print(client.get_dashboards(page=0, page_size=25))
```

### ML API (HTTP)

Health check:

```bash
curl http://localhost:8000/superset/health
```

List dashboards:

```bash
curl "http://localhost:8000/superset/dashboards?page=0&page_size=25"
```

Create dashboard:

```bash
curl -X POST http://localhost:8000/superset/dashboards \
  -H 'Content-Type: application/json' \
  -d '{"dashboard_title":"CXFlow Overview","published":true}'
```

Refresh a dataset (macro-friendly):

```bash
curl -X POST http://localhost:8000/superset/datasets/refresh \
  -H 'Content-Type: application/json' \
  -d '{"dataset_id": 123}'
```

Execute SQL:

```bash
curl -X POST http://localhost:8000/superset/sql/execute \
  -H 'Content-Type: application/json' \
  -d '{"database_id":1,"sql":"SELECT 1"}'
```

## Automation (macros)

A sample macro is provided at:

- `.cxflow/macros/refresh_superset.json`

It is designed to be scheduled and can be adapted to:
- loop through dataset ids stored in memory (e.g., `superset_datasets`)
- refresh those datasets via `/superset/datasets/refresh`

## Notes

- Some Superset operations require **CSRF**; the client handles this for POST/PUT/PATCH/DELETE after login.
- If you’re using `SUPERSET_API_KEY`, ensure it has the necessary permissions for the endpoints you’re calling.
