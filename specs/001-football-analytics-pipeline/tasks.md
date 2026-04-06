# Tasks: End-to-End Football Analytics Data Pipeline

**Input**: Design documents from `/specs/001-football-analytics-pipeline/`
**Prerequisites**: plan.md ✓, spec.md ✓, data-model.md ✓, contracts/ ✓, research.md ✓, quickstart.md ✓

**Organization**: Tasks grouped by user story (US1→US5) in priority order. Each story is independently implementable and testable.

## Format: `[ID] [P?] [Story] Description`

- **[P]**: Can run in parallel (different files, no conflicting dependencies)
- **[Story]**: User story label (US1–US5)
- All paths relative to repo root

---

## Phase 1: Setup (Shared Infrastructure)

**Purpose**: Repository skeleton, tooling, and environment configuration.

- [x] T001 Create directory structure: `ingestion/resources/`, `dbt/models/staging/football_data_api/`, `dbt/models/intermediate/`, `dbt/models/marts/football_analytics/`, `dbt/macros/`, `dbt/tests/`, `dbt/analyses/`, `scripts/`, `.github/workflows/`, `logs/`
- [x] T002 Create `requirements.txt` with `requests`, `google-cloud-bigquery`, `tenacity`, `python-dotenv`; create `requirements-dev.txt` adding `sqlfluff`, `dbt-core`, `dbt-bigquery`, `pytest`
- [x] T003 [P] Create `.env.example` with `FOOTBALL_DATA_API_KEY`, `GOOGLE_APPLICATION_CREDENTIALS`, `BQ_PROJECT`; create `.gitignore` covering `.env`, `logs/`, `dbt/target/`, `dbt/dbt_packages/`, `__pycache__/`, `*.pyc`
- [x] T004 [P] Create `dbt/.sqlfluff` configured for `dialect = bigquery`, `templater = dbt`, `max_line_length = 120`, 4-space indent
- [x] T005 Create `dbt/dbt_project.yml` with project name `football_analytics`, model paths, and dataset routing: staging→`staging`, intermediate→`intermediate`, marts/football_analytics→`football_analytics`; create `dbt/profiles.yml.example` for BigQuery oauth/service-account auth; create `dbt/packages.yml` requiring `dbt-utils`

**Checkpoint**: Repo skeleton and config files in place; `pip install -r requirements-dev.txt && cd dbt && dbt deps` runs without errors.

---

## Phase 2: Foundational (Blocking Prerequisites)

**Purpose**: Core infrastructure required by every user story. No story work begins until this phase is complete.

**⚠️ CRITICAL**: All user story phases depend on this phase completing successfully.

- [x] T006 Create `ingestion/__init__.py` (empty); implement `ingestion/client.py` — `FootballDataClient` class with: `X-Auth-Token` header injection, sliding-window rate limiter (max 10 req/min via deque of timestamps + `time.sleep`), `tenacity`-based retry (exponential backoff, 3 attempts) for HTTP 5xx and `ConnectionError`/`Timeout`, structured `logging` output, `get(endpoint, params)` method returning parsed JSON
- [x] T007 [P] Implement `ingestion/bq_loader.py` — `BigQueryLoader` class with: `client` (google-cloud-bigquery), `append_rows(table_id, rows)` method using `insert_rows_json` for append-only writes, `query_existing_ids(table_id, id_column)` returning a set of already-ingested PKs (**must return empty set without error when the table is empty or does not yet have rows**), `query_existing_composite_keys(table_id, columns)` returning a frozenset of tuples (likewise safe on empty tables)
- [x] T008 Implement `ingestion/setup_bq.py` — creates datasets `raw`, `staging`, `intermediate`, `football_analytics` in the configured GCP project if they don't exist; creates all 7 raw tables with schema from `data-model.md` (partitioning + clustering per spec); invocable as `python -m ingestion.setup_bq`
- [x] T009 [P] Create `dbt/models/staging/football_data_api/_football_data_api.yml` — declare dbt `sources` block pointing to `raw` dataset with all 7 source tables (`areas`, `competitions`, `matches`, `teams`, `persons`, `standings`, `top_scorers`); include column-level descriptions for each source
- [x] T010 Create `dbt/macros/generate_schema_name.sql` — override default dbt macro to route models to the correct BigQuery datasets (`staging`, `intermediate`, `football_analytics`) based on the model's folder path, ignoring the dbt profile's default schema

**Checkpoint**: `python -m ingestion.setup_bq` creates all 4 BigQuery datasets and 7 raw tables; `cd dbt && dbt compile` resolves all source references without errors.

---

## Phase 3: User Story 1 — Historical Backfill (Priority: P1) 🎯 MVP

**Goal**: Ingest all available historical data for all 12 free-plan competitions into the raw BigQuery layer, faithfully mirroring the API with all nested fields intact.

**Independent Test**: Run `python -m ingestion.main` against a fresh BigQuery project; verify all 7 raw tables are populated, running twice produces identical row counts, and no nested fields are null or missing.

- [x] T011 [P] [US1] Implement `ingestion/resources/areas.py` — `ingest_areas(client, loader)`: fetch `GET /v4/areas`, serialize `parentArea` and `childAreas` to JSON string, check existing IDs via `loader.query_existing_ids('raw.areas', 'id')`, append only new rows with `_ingested_at = datetime.utcnow()`
- [x] T012 [P] [US1] Implement `ingestion/resources/competitions.py` — `ingest_competitions(client, loader)`: fetch `GET /v4/competitions` filtered to the 12 free-plan codes (PL, ELC, BL1, PD, SA, FL1, DED, PPL, SB, CL, EC, WC), serialize `area`, `seasons`, `currentSeason` to JSON strings, check existing IDs, append new rows
- [x] T013 [P] [US1] Implement `ingestion/resources/matches.py` — `ingest_matches(client, loader, competition_code, season_year)`: fetch `GET /v4/competitions/{code}/matches?season={year}`, serialize all nested objects/arrays (`area`, `competition`, `season`, `homeTeam`, `awayTeam`, `score`, `goals`, `bookings`, `substitutions`, `penalties`, `referees`, `odds`) to JSON strings, check existing match IDs, append new rows
- [x] T014 [P] [US1] Implement `ingestion/resources/teams.py` — `ingest_teams(client, loader, competition_code, season_year)`: fetch `GET /v4/competitions/{code}/teams?season={year}`, serialize `area`, `coach`, `runningCompetitions`, `squad`, `staff` to JSON strings, check existing team IDs, append new rows
- [x] T015 [US1] Implement `ingestion/resources/persons.py` — `ingest_persons(client, loader, team_ids)`: fetch `GET /v4/persons/{id}` for each person found in squad data, serialize `currentTeam` to JSON string, check existing person IDs, append new rows; deduplicate person IDs across teams before fetching. **Depends on T014** — person IDs are discovered by iterating squad arrays from ingested team records.
- [x] T016 [P] [US1] Implement `ingestion/resources/standings.py` — `ingest_standings(client, loader, competition_code, season_year)`: fetch `GET /v4/competitions/{code}/standings?season={year}`, expand each standings group (TOTAL/HOME/AWAY) into individual rows with `competition_id`, `season_year`, `matchday`, `type`, `stage`, `group`, serialize `table` array to JSON string, check existing composite keys `(competition_id, season_year, matchday, type)`, append new rows
- [x] T017 [P] [US1] Implement `ingestion/resources/top_scorers.py` — `ingest_top_scorers(client, loader, competition_code, season_year)`: fetch `GET /v4/competitions/{code}/scorers?season={year}&limit=50`, extract `player_id` scalar from `player.id`, serialize `player` and `team` JSON objects, check existing composite keys `(competition_id, season_year, player_id)`, append new rows
- [x] T018 [US1] Implement `ingestion/main.py` — CLI entrypoint using `argparse` per `contracts/ingestion-cli.md`: `--resource` (default `all`), `--competition`, `--season`, `--full-refresh`, `--log-level`; orchestrate full backfill by iterating all 12 competition codes × all available seasons × all resource ingestors; validate `--full-refresh` requires `--competition` (exit code 2 if violated); log progress as structured JSON to `logs/ingestion_YYYYMMDD_HHMMSS.log`; exit 0 on clean run, exit 1 if any records were skipped
- [x] T019 [US1] Implement `--full-refresh` logic in `ingestion/main.py` — when flag is set, delete raw rows for the specified `competition_id` (and `season_year` if provided) from all applicable tables before re-ingesting; use BigQuery DML `DELETE` statement scoped to the competition/season; preserve records from other competitions
- [x] T020 [US1] Run full backfill per `quickstart.md` step 4 and verify: all 7 raw tables have rows, `SELECT COUNT(*) FROM raw.matches` returns > 0, second run produces same row counts (idempotency check), log file shows structured JSON lines

**Checkpoint**: US1 complete — `python -m ingestion.main` produces a populated raw layer. Running it twice produces identical counts in all raw tables.

---

## Phase 4: User Story 2 — Daily Incremental Refresh (Priority: P2)

**Goal**: Automated daily job fetches only new/missing records, activates the correct virtualenv, and completes within 2 hours.

**Independent Test**: After full backfill, manually add a new mock match record to the API response fixture, run `python -m ingestion.main`, and confirm only that one record is appended. Run again immediately — confirm zero new rows.

- [x] T021 [US2] Extend `ingestion/bq_loader.py` — add `get_max_season_ingested(table_id, competition_id)` helper that returns the most recently ingested season year for a competition (useful for future partial-season incremental logic); verify all existing methods handle empty tables gracefully (covered by T007)
- [x] T022 [US2] Create `scripts/run_pipeline.sh` — bash script with `set -euo pipefail`; activates virtualenv at configurable `$VENV_PATH`; exports required env vars from `.env` if present; runs `python -m ingestion.main` (incremental by default); runs `cd dbt && dbt build --profiles-dir $PROFILES_DIR`; runs `dbt docs generate`; logs start/end timestamps; exits non-zero on any step failure
- [x] T023 [P] [US2] Create `scripts/setup_venv.sh` — creates virtualenv at `$VENV_PATH`, installs `requirements.txt`, installs `requirements-dev.txt`; idempotent (checks if venv exists before creating)
- [x] T024 [US2] Verify and update `quickstart.md` section 6 — confirm the existing cron example references `$VENV_PATH` and `$PROFILES_DIR` env vars consistent with `run_pipeline.sh` (T022); add a note that the script must be made executable (`chmod +x scripts/run_pipeline.sh`) before scheduling; verify the script runs end-to-end manually before activating the cron entry

**Checkpoint**: US2 complete — `scripts/run_pipeline.sh` executes without errors; running it twice on the same day produces no new raw rows.

---

## Phase 5: User Story 3 — Analytical Data Exploration via Dashboard (Priority: P3)

**Goal**: Full dbt transformation stack (staging → intermediate → marts) producing a queryable star schema in `football_analytics` dataset, ready for Looker Studio connection.

**Independent Test**: Run `dbt build --select staging` then `dbt build --select marts`, connect Looker Studio to `football_analytics.fct_matches`, and verify that filtering by competition and season returns accurate match results.

### Staging Models

- [x] T025 [P] [US3] Create `dbt/models/staging/football_data_api/stg_areas.sql` — select from `{{ source('raw', 'areas') }}`, rename `id→area_id`, extract `parent_area_id` and `parent_area_name` from `JSON_VALUE(parent_area, '$.id')` and `JSON_VALUE(parent_area, '$.name')`; materialize as view
- [x] T026 [P] [US3] Create `dbt/models/staging/football_data_api/stg_competitions.sql` — select from source, rename `id→competition_id`, extract `area_id`, `area_name`, `current_season_id`, `current_season_start_date` (CAST to DATE), `current_season_end_date` from JSON fields; materialize as view
- [x] T027 [P] [US3] Create `dbt/models/staging/football_data_api/stg_matches.sql` — select from source, rename `id→match_id`, extract `competition_id`, `competition_code`, `season_year`, `home_team_id`, `home_team_name`, `away_team_id`, `away_team_name` from JSON fields; extract `home_score_full`, `away_score_full`, `home_score_half`, `away_score_half`, `winner` from `score` JSON; preserve `goals`, `bookings`, `substitutions`, `referees` as STRING for int layer; CAST `utc_date` to TIMESTAMP; materialize as view
- [x] T028 [P] [US3] Create `dbt/models/staging/football_data_api/stg_teams.sql` — select from source, rename `id→team_id`, extract `area_id` and `area_name` from `area` JSON; CAST `founded` to INTEGER; include `_ingested_at` passthrough column (required by `dim_teams` for latest-snapshot deduplication); materialize as view
- [x] T029 [P] [US3] Create `dbt/models/staging/football_data_api/stg_persons.sql` — select from source, rename `id→person_id`, extract `current_team_id` from `current_team` JSON; CAST `date_of_birth` to DATE; include `_ingested_at` passthrough column (required by `dim_persons` for latest-snapshot deduplication); materialize as view
- [x] T030 [P] [US3] Create `dbt/models/staging/football_data_api/stg_standings.sql` — unnest `table` JSON array using `JSON_EXTRACT_ARRAY` + `CROSS JOIN UNNEST`; extract per-row: `position`, `team_id` (`JSON_VALUE(row, '$.team.id')`), `team_name`, `points`, `played_games`, `won`, `drawn`, `lost`, `goals_for`, `goals_against`, `goal_difference`; preserve `competition_id`, `season_year`, `matchday`, `type`, `stage`, `group` from parent row; materialize as view
- [x] T031 [P] [US3] Create `dbt/models/staging/football_data_api/stg_top_scorers.sql` — select from source, extract `person_id` (`CAST(JSON_VALUE(player, '$.id') AS INTEGER)`), `person_name`, `team_id`, `team_name` from JSON fields; CAST `goals`, `assists`, `penalties` to INTEGER; materialize as view

### Intermediate Models

- [x] T032 [P] [US3] Create `dbt/models/intermediate/int_match_events.sql` — unnest `goals`, `bookings`, `substitutions` from `stg_matches` using `JSON_EXTRACT_ARRAY`; produce one row per event with `match_id`, `event_type` (GOAL/BOOKING/SUBSTITUTION), `minute`, `person_id`, `team_id`, `detail`, `additional_person_id`; generate surrogate key via `{{ dbt_utils.generate_surrogate_key(['match_id', 'event_type', 'minute', 'person_id']) }}`; materialize as view
- [x] T033 [P] [US3] Create `dbt/models/intermediate/int_competition_seasons.sql` — join `stg_competitions` with `stg_matches` to produce all observed `(competition_id, season_year)` pairs with `competition_name`, `competition_code`, `area_id`, `season_start_date`, `season_end_date`, `match_count`; materialize as view

### Mart Dimensions

- [x] T034 [P] [US3] Create `dbt/models/marts/football_analytics/dim_areas.sql` — select distinct `area_id`, `name`, `code`, `parent_area_id` from `stg_areas`; materialize as table
- [x] T035 [P] [US3] Create `dbt/models/marts/football_analytics/dim_competitions.sql` — select `competition_id`, `name`, `code`, `type`, `area_id`, `area_name` from `stg_competitions`; materialize as table
- [x] T036 [P] [US3] Create `dbt/models/marts/football_analytics/dim_teams.sql` — select latest snapshot of each team from `stg_teams` (deduplicate by `team_id`, pick most recent `_ingested_at`); include `team_id`, `name`, `short_name`, `tla`, `area_id`, `founded`, `club_colors`, `venue`; materialize as table
- [x] T037 [P] [US3] Create `dbt/models/marts/football_analytics/dim_persons.sql` — select latest snapshot of each person from `stg_persons` (deduplicate by `person_id`); include `person_id`, `name`, `date_of_birth`, `nationality`, `position`; materialize as table
- [x] T038 [P] [US3] Create `dbt/models/marts/football_analytics/dim_seasons.sql` — select `(competition_code || '-' || CAST(season_year AS STRING)) AS season_key`, `competition_id`, `season_year`, `start_date`, `end_date` from `int_competition_seasons`; materialize as table

### Mart Facts

- [x] T039 [P] [US3] Create `dbt/models/marts/football_analytics/fct_matches.sql` — select `match_id`, `competition_id`, `season_year`, `matchday`, `stage`, `status`, `utc_date`, `home_team_id`, `away_team_id`, `home_score_full`, `away_score_full`, `home_score_half`, `away_score_half`, `winner` from `stg_matches`; materialize as incremental with `unique_key = 'match_id'`, `incremental_strategy = 'merge'`
- [x] T040 [P] [US3] Create `dbt/models/marts/football_analytics/fct_standings.sql` — select all columns from `stg_standings` plus surrogate `standing_id` via `dbt_utils.generate_surrogate_key(['competition_id', 'season_year', 'matchday', 'type', 'team_id'])`; materialize as incremental with `unique_key = 'standing_id'`
- [x] T041 [P] [US3] Create `dbt/models/marts/football_analytics/fct_top_scorers.sql` — select all columns from `stg_top_scorers` plus surrogate `scorer_id` via `dbt_utils.generate_surrogate_key(['competition_id', 'season_year', 'person_id'])`; materialize as incremental with `unique_key = 'scorer_id'`
- [x] T042 [US3] Create `dbt/models/marts/football_analytics/fct_match_events.sql` — select all columns from `int_match_events`; materialize as incremental with `unique_key = 'event_id'` (reuse surrogate from int layer)
- [x] T043 [US3] Run `cd dbt && dbt build --select staging` then `dbt build --select marts` and verify all models materialize without errors; spot-check `football_analytics.fct_matches` row count matches `raw.matches` row count

**Checkpoint**: US3 complete — `dbt build` succeeds; all 5 dims and 4 facts are queryable in BigQuery; Looker Studio can connect to `football_analytics` dataset.

---

## Phase 6: User Story 4 — Automated Data Quality Validation (Priority: P4)

**Goal**: Every staging and mart model has schema tests (unique, not_null, accepted_values). `dbt test` catches bad data before it reaches the dashboard.

**Independent Test**: Manually insert a duplicate `match_id` into `raw.matches`, run `dbt build`, confirm the `unique` test on `stg_matches` or `fct_matches` fails with a clear error message.

- [x] T044 [US4] Add test declarations to `dbt/models/staging/football_data_api/_football_data_api.yml` for all 7 staging models: `unique` + `not_null` on each PK column; `accepted_values` for `stg_competitions.type` (LEAGUE, CUP), `stg_matches.status` (SCHEDULED, LIVE, IN_PLAY, PAUSED, FINISHED, POSTPONED, SUSPENDED, CANCELLED), `stg_matches.stage` (GROUP_STAGE, LAST_16, QUARTER_FINALS, SEMI_FINALS, THIRD_PLACE, FINAL, REGULAR_SEASON, PLAYOFFS), `stg_matches.winner` (HOME_TEAM, AWAY_TEAM, DRAW), `stg_standings.type` (TOTAL, HOME, AWAY), `stg_persons.position` (Goalkeeper, Defence, Midfield, Offence)
- [x] T045 [P] [US4] Add test declarations to `dbt/models/intermediate/_intermediate.yml` for `int_match_events` (unique + not_null on `event_id`) and `int_competition_seasons` (unique on `(competition_id, season_year)`); add `accepted_values` for `int_match_events.event_type` (GOAL, BOOKING, SUBSTITUTION)
- [x] T046 [P] [US4] Add test declarations to `dbt/models/marts/football_analytics/_football_analytics.yml` for all 5 dims and 4 facts: `unique` + `not_null` on each PK; `accepted_values` for `fct_matches.status`, `fct_matches.stage`, `fct_matches.winner`, `fct_standings.type`; `not_null` on all FK columns (e.g., `fct_matches.competition_id`, `fct_matches.home_team_id`)
- [x] T047 [US4] Run `cd dbt && dbt test` and confirm 100% of tests pass on the populated dataset; document count of tests generated in the run summary

**Checkpoint**: US4 complete — `dbt test` passes cleanly; all models have PK uniqueness, not_null, and accepted_values coverage per FR-015 and FR-016.

---

## Phase 7: User Story 5 — Continuous Integration (Priority: P5)

**Goal**: Every pull request automatically triggers dbt compile (DAG validation) and SQLFluff lint (SQL style). Broken or non-compliant SQL is caught before merge.

**Independent Test**: Open a PR with a deliberate SQL style violation (e.g., missing trailing comma, wrong indent); confirm CI fails with a line-specific SQLFluff error. Fix it; confirm CI passes.

- [x] T048 [US5] Create `.github/workflows/ci.yml` — trigger on `pull_request` to `main`; job: checkout repo, set up Python 3.11, install `requirements-dev.txt`, run `cd dbt && dbt deps && dbt compile --profiles-dir ./ci_profiles` (uses a minimal CI profiles.yml pointing to a test project or dry-run mode), run `sqlfluff lint dbt/models/ --dialect bigquery`; fail job on any non-zero exit
- [x] T049 [US5] Create `dbt/ci_profiles/profiles.yml` — minimal dbt profile for CI that uses BigQuery service account auth via `GOOGLE_APPLICATION_CREDENTIALS` env var (injected as GitHub Actions secret); target project: same GCP project used for development, or a dedicated CI project
- [x] T050 [US5] Add a "CI Secrets" subsection to `quickstart.md` section 8 — document the GitHub Actions secrets required: `GOOGLE_APPLICATION_CREDENTIALS_JSON` (base64-encoded service account JSON, written to a temp file in the CI workflow — distinct from the local `GOOGLE_APPLICATION_CREDENTIALS` file-path variable), `BQ_PROJECT`, `FOOTBALL_DATA_API_KEY`; include the workflow step that decodes and writes the JSON to `$GOOGLE_APPLICATION_CREDENTIALS`

**Checkpoint**: US5 complete — merging to main is blocked if `dbt compile` or `sqlfluff lint` fails on any PR.

---

## Phase 8: Polish & Cross-Cutting Concerns

**Purpose**: Final wiring, documentation, and end-to-end validation.

- [x] T051 Update `CLAUDE.md` with final dataset names (`raw`, `staging`, `intermediate`, `football_analytics`), dbt project path (`dbt/`), and ingestion CLI reference
- [x] T052 [P] Add `dbt/analyses/` example query — a Looker Studio-ready analytical query joining `fct_matches` with `dim_competitions` and `dim_teams` to produce a match results table with competition name and team names denormalized; file: `dbt/analyses/match_results_example.sql`
- [x] T053 Run end-to-end validation per `quickstart.md`: full backfill → `dbt build` → `dbt test` → `dbt docs generate && dbt docs serve`; confirm docs site loads and all 18 models (7 staging + 2 intermediate + 9 marts: 5 dims + 4 facts) appear in the DAG; verify SC-003 by checking log timestamps confirm incremental run completes within 2 hours

**Checkpoint**: Pipeline is end-to-end verified. Looker Studio can browse all competition and match data.

---

## Dependencies & Execution Order

### Phase Dependencies

- **Phase 1 (Setup)**: No dependencies — start immediately
- **Phase 2 (Foundational)**: Depends on Phase 1 — **blocks all user story phases**
- **Phase 3 (US1)**: Depends on Phase 2
- **Phase 4 (US2)**: Depends on Phase 3 (needs populated raw layer to test incrementality)
- **Phase 5 (US3)**: Depends on Phase 3 (needs raw data for dbt to read from sources)
- **Phase 6 (US4)**: Depends on Phase 5 (tests reference model columns defined in SQL)
- **Phase 7 (US5)**: Depends on Phase 5 (CI lints the model files created in US3)
- **Phase 8 (Polish)**: Depends on all previous phases

### User Story Dependencies

- **US1 (P1)**: Starts after Foundational — independent, no story dependencies
- **US2 (P2)**: Starts after US1 — needs populated raw layer to validate incremental behavior
- **US3 (P3)**: Starts after US1 — needs populated raw layer; can run in parallel with US2
- **US4 (P4)**: Starts after US3 — adds test declarations to models created in US3
- **US5 (P5)**: Starts after US3 — lints models created in US3; can run in parallel with US4

### Within Each Phase

- Tasks marked [P] within the same phase can run in parallel
- Resource ingestors T011–T014, T016–T017 are independent of each other; T015 (persons) depends on T014 (teams) completing first to provide squad data
- Staging models T025–T031 are fully independent of each other
- Mart dimensions T034–T038 are independent of each other
- Mart facts T039–T042 depend on their corresponding staging/intermediate models being created first

---

## Parallel Opportunities

### Phase 3: US1 — Resource ingestors (T011–T014, T016–T017 parallel; T015 after T014)
```
# Round 1 — parallel:
Task T011: ingestion/resources/areas.py
Task T012: ingestion/resources/competitions.py
Task T013: ingestion/resources/matches.py
Task T014: ingestion/resources/teams.py
Task T016: ingestion/resources/standings.py
Task T017: ingestion/resources/top_scorers.py

# Round 2 — after T014 completes (needs squad data):
Task T015: ingestion/resources/persons.py
```

### Phase 5: US3 — All 7 staging models in parallel
```
Task T025: stg_areas.sql
Task T026: stg_competitions.sql
Task T027: stg_matches.sql
Task T028: stg_teams.sql
Task T029: stg_persons.sql
Task T030: stg_standings.sql
Task T031: stg_top_scorers.sql
```

### Phase 5: US3 — All 5 mart dimensions in parallel (after staging)
```
Task T034: dim_areas.sql
Task T035: dim_competitions.sql
Task T036: dim_teams.sql
Task T037: dim_persons.sql
Task T038: dim_seasons.sql
```

### US4 + US5 in parallel (both depend on US3)
```
Task T044–T047: Schema test declarations (US4)
Task T048–T050: CI pipeline (US5)
```

---

## Implementation Strategy

### MVP First (User Story 1 + 2 Only)

1. Complete Phase 1: Setup
2. Complete Phase 2: Foundational — `python -m ingestion.setup_bq` works
3. Complete Phase 3: US1 — raw layer fully populated
4. Complete Phase 4: US2 — daily cron script operational
5. **STOP and VALIDATE**: Raw data is fresh, idempotent, and automated

### Full Delivery (Incremental)

1. MVP above → raw pipeline working
2. Phase 5 (US3) → Star schema queryable in BigQuery
3. Phase 6 (US4) → `dbt test` passing
4. Phase 7 (US5) → CI blocking bad SQL
5. Phase 8 → Docs, Looker Studio connection, end-to-end sign-off

---

## Notes

- [P] tasks operate on different files — safe to run in parallel
- All dbt models use `{{ source(...) }}` references — never hardcode dataset names in SQL
- Log file path: `logs/ingestion_YYYYMMDD_HHMMSS.log` (gitignored)
- `profiles.yml` is gitignored; `profiles.yml.example` is committed as a template
- Surrogate keys use `dbt_utils.generate_surrogate_key` — install via `dbt/packages.yml`
- The `generate_schema_name.sql` macro (T010) is the single place that controls dataset routing — all other models use folder-based convention only
