# Research: End-to-End Football Analytics Data Pipeline

**Phase**: 0 — Outline & Research
**Date**: 2026-04-03

---

## 1. API Scope — Free Plan Competitions

**Decision**: The pipeline ingests exactly 12 competitions available on the football-data.org free plan.

| Code | Competition | Country/Region |
|------|-------------|----------------|
| PL   | Premier League | England |
| ELC  | Championship | England |
| BL1  | Bundesliga | Germany |
| PD   | La Liga | Spain |
| SA   | Serie A | Italy |
| FL1  | Ligue 1 | France |
| DED  | Eredivisie | Netherlands |
| PPL  | Primeira Liga | Portugal |
| SB   | Série A (Brazil) | Brazil |
| CL   | UEFA Champions League | Europe |
| EC   | European Championship | Europe |
| WC   | FIFA World Cup | International |

**Rationale**: Free plan is the stated constraint. These codes are stable identifiers used in all API calls.

---

## 2. "Trends" Resource — Correction

**Decision**: Remove "Trend" from the data model. It does not exist in API v4.

**Finding**: The football-data.org API v4 has **5 main resources** (Areas, Competitions, Matches, Teams, Persons) plus subresources. No "Trend" or "Trends" endpoint exists in v4 documentation or the free plan. The spec mentioned it in error.

**Impact**: Raw layer has 5 main tables + 2 subresource tables (standings, top_scorers). FR-001 should reference 5 entities, not 6.

---

## 3. API Endpoint Map

| Resource | Endpoint | Notes |
|---|---|---|
| Areas (list) | `GET /v4/areas` | Returns all areas |
| Area (detail) | `GET /v4/areas/{id}` | Single area |
| Competitions (list) | `GET /v4/competitions` | Filterable by `areas` param |
| Competition (detail) | `GET /v4/competitions/{code}` | Accepts code (PL) or numeric ID |
| Competition → Matches | `GET /v4/competitions/{code}/matches` | Filter: `season`, `matchday`, `status` |
| Competition → Standings | `GET /v4/competitions/{code}/standings` | Filter: `season`, `matchday` |
| Competition → Teams | `GET /v4/competitions/{code}/teams` | Filter: `season` |
| Competition → Top Scorers | `GET /v4/competitions/{code}/scorers` | Filter: `season`, `limit` |
| Match (detail) | `GET /v4/matches/{id}` | Full detail including events |
| Team (detail) | `GET /v4/teams/{id}` | Squad included |
| Team → Matches | `GET /v4/teams/{id}/matches` | Filter: `status`, `competitions`, `dateFrom`, `dateTo` |
| Person (detail) | `GET /v4/persons/{id}` | |
| Person → Matches | `GET /v4/persons/{id}/matches` | |

**Pagination**: `limit` (1–500, default 100) and `offset` parameters on list endpoints.

---

## 4. Response Shape — Scalar vs Nested

| Resource | Scalar fields | Nested (stored as JSON string in raw) |
|---|---|---|
| Area | `id`, `name`, `code` | `parentArea`, `childAreas` |
| Competition | `id`, `name`, `code`, `type`, `emblem`, `lastUpdated` | `area`, `seasons`, `currentSeason` |
| Match | `id`, `utcDate`, `status`, `matchday`, `stage`, `lastUpdated`, `attendance`, `venue` | `area`, `competition`, `season`, `homeTeam`, `awayTeam`, `score`, `goals`, `bookings`, `substitutions`, `penalties`, `referees`, `odds` |
| Team | `id`, `name`, `shortName`, `tla`, `address`, `website`, `founded`, `clubColors`, `venue`, `lastUpdated` | `area`, `coach`, `runningCompetitions`, `squad`, `staff` |
| Person | `id`, `name`, `firstName`, `lastName`, `dateOfBirth`, `nationality`, `position`, `shirtNumber`, `lastUpdated` | `currentTeam` |
| Standing (row) | `position`, `playedGames`, `won`, `drawn`, `lost`, `points`, `goalsFor`, `goalsAgainst`, `goalDifference` | `team` |
| Top Scorer (row) | `goals`, `assists`, `penalties` | `player`, `team` |

**Response envelope**: All list endpoints wrap data in a resource-specific key (e.g., `matches`, `standings`, `scorers`) alongside `count` and `filters` metadata fields. These envelope fields are **not** stored in raw tables — only the resource records themselves.

---

## 5. Idempotency Strategy

**Decision**: Check raw table for existing record by primary key before each API call.

| Resource | Primary Key for idempotency check |
|---|---|
| Area | `id` |
| Competition | `id` |
| Match | `id` |
| Team | `id` |
| Person | `id` |
| Standing | `(competition_id, season_year, matchday, type)` |
| Top Scorer | `(competition_id, season_year, player_id)` |

**Rationale**: Querying BigQuery before requesting from the API prevents duplicate inserts and unnecessary API calls, satisfying both FR-005 and FR-007.

---

## 6. Rate Limiting Implementation

**Decision**: Sliding-window counter with `time.sleep()` — no third-party rate-limiting library.

**Rationale**: The constraint is simple (10 req/min). A list of recent request timestamps + sleep-until-safe is sufficient and has zero additional dependencies.

**Pattern**:
```
maintain a deque of timestamps of the last 10 requests
before each request:
  if len(deque) == 10 and (now - deque[0]) < 60s:
    sleep(60s - (now - deque[0]))
  make request
  append now to deque
```

---

## 7. Retry Strategy

**Decision**: Use `tenacity` library with exponential backoff.

**Rationale**: `tenacity` cleanly separates retry logic from business logic, supports jitter, and handles both HTTP status codes and exceptions uniformly.

**Configuration**:
- Retry on: `requests.exceptions.ConnectionError`, `requests.exceptions.Timeout`, HTTP 5xx, HTTP 429
- Wait: exponential backoff starting at 2s, multiplier 2, max 60s
- Stop: after 3 attempts
- On failure after 3 attempts: log error, skip record, continue pipeline

**Alternatives considered**: `requests-retry` (simpler but less control over logging), manual loop (more boilerplate).

---

## 8. BigQuery Raw Table Design

**Decision**: Partitioned by `_ingested_at` (DATE), clustered by primary key column.

**Rationale**: Partitioning by ingestion date keeps incremental queries cheap (BigQuery only scans recent partitions). Clustering by ID makes idempotency-check queries fast.

**Schema conventions**:
- All column names in `snake_case`
- Nested API objects stored as `STRING` (JSON-serialized via `json.dumps`)
- `_ingested_at TIMESTAMP` added to every raw row (pipeline-managed metadata)
- No `REQUIRED` mode on nullable API fields — all raw columns are `NULLABLE`

---

## 9. dbt Materialization Strategy

**Decision**: Views for staging, tables for dimensions, incremental (merge) for facts.

| Layer | Materialization | Rationale |
|---|---|---|
| Staging | `view` | No storage cost; always reflects latest raw; trivial queries |
| Intermediate | `view` | Same reasoning; intermediate is logical, not persisted |
| Dimensions | `table` | Small, rarely change; full rebuild is fast |
| Facts | `incremental` + `unique_key` | Append-heavy; merge strategy prevents duplicates on re-run |

**unique_key per fact**:
- `fct_matches`: `match_id`
- `fct_standings`: surrogate key on `(competition_id, season_year, matchday, team_id, type)`
- `fct_top_scorers`: surrogate key on `(competition_id, season_year, person_id)`
- `fct_match_events`: surrogate key on `(match_id, minute, event_type, person_id)`

---

## 10. SQLFluff Configuration

**Decision**: BigQuery dialect, max line length 120, 4-space indent, trailing comma style.

```ini
[sqlfluff]
dialect = bigquery
templater = dbt
max_line_length = 120

[sqlfluff:indentation]
indent_unit = space
tab_space_size = 4
```

**Alternatives considered**: Default line length of 80 (too restrictive for BigQuery's verbose function names).

---

## 11. Cron Job Design

**Decision**: Single shell script wrapper that activates the virtualenv, runs ingestion, runs `dbt build`, then `dbt docs generate`.

```bash
#!/bin/bash
set -euo pipefail
source /path/to/venv/bin/activate
export PYTHONPATH=/path/to/project
python -m ingestion.main
dbt build --project-dir /path/to/transform --profiles-dir /path/to/profiles
dbt docs generate --project-dir /path/to/transform
```

**Rationale**: `set -euo pipefail` ensures any step failure stops the script and returns a non-zero exit code, which cron captures. Combined with structured logging in the Python code, this satisfies FR-018, FR-019, and FR-022.
