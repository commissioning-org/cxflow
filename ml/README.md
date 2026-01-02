# ML service

This folder contains the FastAPI-based ML service (`ml/app`).

## Meilisearch integration

The service can optionally index and search local **model metadata** and **experiments** using Meilisearch.

### Configure

Set these environment variables (prefix is `ML_`):

- `ML_MEILI_URL` (required to enable search) — e.g. `http://localhost:7700`
- `ML_MEILI_API_KEY` (optional)
- `ML_MEILI_MODELS_INDEX` (default: `ml_models`)
- `ML_MEILI_EXPERIMENTS_INDEX` (default: `ml_experiments`)
- `ML_MEILI_TIMEOUT_SEC` (default: `5`)
- `ML_MEILI_CONFIGURE_INDEXES` (default: `true`) — whether the service should push basic index settings.

A commented template exists in `ml/.env` for local use.

### API endpoints

- `GET /search/health` — returns whether search is configured and the Meilisearch health payload.
- `GET /search/models?q=...&filter=...` — search indexed model metadata.
- `GET /search/experiments?q=...&filter=...` — search indexed experiments.
- `POST /search/reindex` — (re)index documents from local storage into Meilisearch.

`POST /search/reindex` body:

- `models` (bool, default `true`)
- `experiments` (bool, default `true`)
- `batch_size` (int, default `1000`)
- `dry_run` (bool, default `false`) — when true, only returns document counts and does not call Meilisearch.

### Notes

- If `ML_MEILI_URL` is unset, search endpoints return **503**.
- Search uses a small stdlib-only HTTP client (`app/services/meilisearch.py`) to avoid adding new dependencies.
