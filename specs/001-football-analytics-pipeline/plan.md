# Implementation Plan: End-to-End Football Analytics Data Pipeline

**Branch**: `001-football-analytics-pipeline` | **Date**: 2026-04-03 | **Spec**: [spec.md](./spec.md)
**Input**: Feature specification from `/specs/001-football-analytics-pipeline/spec.md`

## Summary

Build a batch data pipeline that ingests football data from the football-data.org API v4 into BigQuery (raw layer), transforms it with dbt Core through staging → intermediate → marts layers, and exposes a star schema for Looker Studio analysis. The pipeline runs daily via cron, is rate-limited to 10 req/min, is idempotent and append-only at the raw layer, and has CI validation via GitHub Actions.

## Technical Context

**Language/Version**: Python 3.11+, SQL (BigQuery dialect)
**Primary Dependencies**:
- Ingestion: `requests` 2.x, `google-cloud-bigquery` 3.x, `tenacity` 8.x
- Transformation: `dbt-core` 1.8+, `dbt-bigquery` 1.8+
- Linting: `sqlfluff` 3.x (BigQuery dialect)
- Scheduling: Ubuntu cron + bash
- CI: GitHub Actions

**Storage**: Google BigQuery — 4 datasets:
- `raw` (append-only API mirror)
- `staging` (dbt views)
- `intermediate` (dbt views)
-  each dbt/models/marts/ subfolder is it's own schema (eg. `football_analytics`), (dbt tables + incremental facts)

**Testing**: `pytest` (Python ingestion unit tests), dbt tests (unique, not_null, accepted_values per schema.yml)
**Target Platform**: Ubuntu 22.04 LTS (cron host), GitHub Actions (CI runners)
**Project Type**: Batch ETL data pipeline
**Performance Goals**: ≤10 API requests/minute; daily incremental run ≤2 hours; initial backfill is multi-hour (no SLA)
**Constraints**: Append-only raw layer; idempotent pipeline runs; free plan API (10 req/min, 12 competitions); `--full-refresh` scoped to competition + optional season
**Scale/Scope**: 12 competitions, ~30–60 seasons total, ~50K–200K matches historical

## Constitution Check

The project constitution (`/.specify/memory/constitution.md`) contains only unfilled template placeholders — no active principles are defined. No gates to evaluate.

*Post-design re-check*: N/A — constitution is empty template.

## Project Structure

### Documentation (this feature)

```text
specs/001-football-analytics-pipeline/
├── plan.md              # This file
├── research.md          # Phase 0 — API findings, tool decisions
├── data-model.md        # Phase 1 — Raw, staging, intermediate, marts schemas
├── quickstart.md        # Phase 1 — Setup and run instructions
├── contracts/
│   ├── ingestion-cli.md  # CLI contract for ingestion entrypoint
│   └── mart-outputs.md   # BigQuery mart output schema contract
└── tasks.md             # Phase 2 output (/speckit.tasks — not yet created)
```

### Source Code (repository root)

```text
ingestion/                      # Python package — API → BigQuery
├── __init__.py
├── main.py                     # CLI entrypoint (argparse)
├── client.py                   # API client: rate limiting + retry
├── bq_loader.py                # BigQuery write helpers (idempotency checks)
├── setup_bq.py                 # One-time dataset/table creation
└── resources/
    ├── areas.py                # Ingest areas
    ├── competitions.py         # Ingest competitions + seasons
    ├── matches.py              # Ingest competition→matches
    ├── teams.py                # Ingest competition→teams
    ├── persons.py              # Ingest persons (from squad data)
    ├── standings.py            # Ingest competition→standings
    └── top_scorers.py          # Ingest competition→scorers

dbt/                      # dbt project root
├── dbt_project.yml
├── profiles.yml.example        # Template — real profiles.yml is gitignored
├── packages.yml                # dbt-utils for surrogate keys
├── .sqlfluff                   # SQLFluff config (BigQuery dialect)
├── models/
│   ├── staging/
│   │   └── football_data_api/
│   │       ├── _football_data_api.yml
│   │       ├── stg_areas.sql
│   │       ├── stg_competitions.sql
│   │       ├── stg_matches.sql
│   │       ├── stg_teams.sql
│   │       ├── stg_persons.sql
│   │       ├── stg_standings.sql
│   │       └── stg_top_scorers.sql
│   ├── intermediate/
│   │   ├── _intermediate.yml
│   │   ├── int_match_events.sql
│   │   └── int_competition_seasons.sql
│   └── marts/
│       └── football_analytics/
│           ├── _football_analytics.yml
│           ├── dim_areas.sql
│           ├── dim_competitions.sql
│           ├── dim_teams.sql
│           ├── dim_persons.sql
│           ├── dim_seasons.sql
│           ├── fct_matches.sql
│           ├── fct_standings.sql
│           ├── fct_top_scorers.sql
│           └── fct_match_events.sql
├── macros/
│   └── generate_schema_name.sql  # Dataset routing macro
├── analyses/
└── tests/

scripts/
├── run_pipeline.sh             # Daily cron entrypoint
└── setup_venv.sh               # Virtualenv setup helper

.github/
└── workflows/
    └── ci.yml                  # dbt compile + sqlfluff lint on PRs

logs/                           # gitignored; created at runtime
requirements.txt                # Production dependencies
requirements-dev.txt            # Dev + lint dependencies
.env.example                    # Template for environment variables
.gitignore
```

**Structure Decision**: Single-project layout. Ingestion (Python) and transformation (dbt) are sibling directories at the repo root, sharing one virtualenv. This avoids unnecessary project nesting while keeping ingestion and transformation concerns clearly separated.

## Complexity Tracking

No constitution violations to justify — constitution is an unfilled template.

---

## Phase 0 Findings Summary

See [research.md](./research.md) for full details. Key decisions:

| Topic | Decision |
|---|---|
| Free plan competitions | 12 competitions (PL, ELC, BL1, PD, SA, FL1, DED, PPL, SB, CL, EC, WC) |
| "Trends" resource | Does not exist in API v4 — removed from scope |
| Raw table design | Partitioned by `_ingested_at` or relevant date; clustered by PK |
| Idempotency | Check raw table by PK before each API call |
| Rate limiting | Sliding-window counter with `time.sleep()` |
| Retry | `tenacity` — exponential backoff, 3 attempts, log+skip on failure |
| dbt materialization | Views (staging/intermediate), tables (dims), incremental merge (facts) |
| SQLFluff | BigQuery dialect, 4-space indent, max line length 120 |
| Cron script | `set -euo pipefail`; source venv; ingest → dbt build → dbt docs generate |

## Phase 1 Design Summary

See [data-model.md](./data-model.md), [contracts/](./contracts/), [quickstart.md](./quickstart.md).

**Raw layer**: 7 tables (areas, competitions, matches, teams, persons, standings, top_scorers)
**Staging layer**: 7 dbt views (one per raw table)
**Intermediate layer**: 2 dbt views (int_match_events, int_competition_seasons)
**Marts layer**: 5 dimensions + 4 facts (star schema)

**Contracts defined**:
- `contracts/ingestion-cli.md` — CLI flags, exit codes, log format
- `contracts/mart-outputs.md` — stable BigQuery schemas for Looker Studio consumers

## Spec Correction

**FR-001** references "six main data entities including Trends." The "Trends" resource does not exist in API v4. The pipeline ingests **5 main resources** (Areas, Competitions, Matches, Teams, Persons) plus **2 subresource tables** (Standings, Top Scorers). This is a data source documentation error in the original feature description — no functional requirement is lost.
