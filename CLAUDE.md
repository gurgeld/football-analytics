# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Active Feature

**Branch**: `001-football-analytics-pipeline`

### Technology Stack
- **Ingestion**: Python 3.11+, `requests`, `google-cloud-bigquery`, `tenacity`
- **Transformation**: dbt-core 1.8+ with dbt-bigquery adapter (project root: `dbt/`)
- **Linting**: SQLFluff 3.x (BigQuery dialect)
- **Storage**: Google BigQuery — 4 datasets: `raw`, `staging`, `intermediate`, `football_analytics`
- **Scheduling**: Ubuntu cron + bash (`scripts/run_pipeline.sh`)
- **CI**: GitHub Actions (`.github/workflows/ci.yml`)

### BigQuery Datasets
| Dataset | dbt layer | Materialization |
|---------|-----------|-----------------|
| `raw` | Source (ingestion) | Append-only tables |
| `staging` | Staging | Views |
| `intermediate` | Intermediate | Views |
| `football_analytics` | Marts | Tables (dims) + Incremental (facts) |

### dbt Project Layout
```
dbt/
  dbt_project.yml          # project config + schema routing
  packages.yml             # dbt-utils dependency
  macros/generate_schema_name.sql  # overrides dataset routing
  models/
    staging/football_data_api/    # 7 staging views + _football_data_api.yml
    intermediate/                 # 2 intermediate views + _intermediate.yml
    marts/football_analytics/     # 5 dims + 4 facts + _football_analytics.yml
  ci_profiles/profiles.yml        # CI-only dbt profile (service account auth)
```

### Ingestion CLI
```bash
# Full incremental run (all resources, all competitions)
python -m ingestion.main

# Single resource
python -m ingestion.main --resource matches

# Full refresh (scoped to one competition)
python -m ingestion.main --full-refresh --competition PL [--season 2023]
```
Exit codes: `0` = clean, `1` = skips, `2` = fatal (e.g. `--full-refresh` without `--competition`).

### Key Conventions
- Raw layer is append-only — never overwrite or delete historical records
- All nested API fields stored as `STRING` (JSON-serialized via `json.dumps`)
- dbt staging: views only, snake_case, no business logic
- dbt facts: incremental with `unique_key` (merge strategy)
- Rate limit: ≤10 API requests/minute (enforced in `ingestion/client.py`)
- `--full-refresh` requires `--competition` argument; scope is per-competition (+ optional season)
- `dbt_utils.generate_surrogate_key` used for all composite-keyed facts
