# Data Model: End-to-End Football Analytics Data Pipeline

**Phase**: 1 — Design & Contracts
**Date**: 2026-04-03

---

## Layer Overview

```
football-data.org API v4
        │
        ▼
┌─────────────────────┐
│    RAW LAYER        │  BigQuery dataset: raw
│  (Python ingestion) │  Append-only; faithful API mirror
└─────────────────────┘
        │
        ▼
┌─────────────────────┐
│   STAGING LAYER     │  BigQuery dataset: staging
│  (dbt views)        │  snake_case, typed, flattened
└─────────────────────┘
        │
        ▼
┌─────────────────────┐
│ INTERMEDIATE LAYER  │  BigQuery dataset: intermediate
│  (dbt views)        │  Business logic, joins, unnesting
└─────────────────────┘
        │
        ▼
┌─────────────────────┐
│    MARTS LAYER      │  BigQuery dataset: football_analytics
│  (dbt tables)       │  Star schema — dimensions + facts
└─────────────────────┘
        │
        ▼
  Looker Studio
```

---

## Raw Layer

> One BigQuery table per API resource. All nested fields stored as `STRING` (JSON-serialized). Append-only. Never updated or deleted by automated pipeline.

### `raw.areas`

| Column | BigQuery Type | Source | Notes |
|--------|--------------|--------|-------|
| `id` | INTEGER | `id` | Stable area ID |
| `name` | STRING | `name` | |
| `code` | STRING | `code` | ISO 3166 or null |
| `parent_area` | STRING | `parentArea` | JSON object |
| `child_areas` | STRING | `childAreas` | JSON array |
| `_ingested_at` | TIMESTAMP | pipeline | Partition column |

**PK**: `id` | **Partition**: `DATE(_ingested_at)` | **Cluster**: `id`

---

### `raw.competitions`

| Column | BigQuery Type | Source | Notes |
|--------|--------------|--------|-------|
| `id` | INTEGER | `id` | |
| `name` | STRING | `name` | |
| `code` | STRING | `code` | e.g., PL, BL1 |
| `type` | STRING | `type` | LEAGUE or CUP |
| `emblem` | STRING | `emblem` | URL (not fetched) |
| `last_updated` | TIMESTAMP | `lastUpdated` | |
| `area` | STRING | `area` | JSON object |
| `seasons` | STRING | `seasons` | JSON array |
| `current_season` | STRING | `currentSeason` | JSON object |
| `_ingested_at` | TIMESTAMP | pipeline | |

**PK**: `id` | **Partition**: `DATE(_ingested_at)` | **Cluster**: `id`

---

### `raw.matches`

| Column | BigQuery Type | Source | Notes |
|--------|--------------|--------|-------|
| `id` | INTEGER | `id` | |
| `utc_date` | TIMESTAMP | `utcDate` | |
| `status` | STRING | `status` | Enum: SCHEDULED, LIVE, IN_PLAY, PAUSED, FINISHED, POSTPONED, SUSPENDED, CANCELLED |
| `matchday` | INTEGER | `matchday` | |
| `stage` | STRING | `stage` | Enum: GROUP_STAGE, LAST_16, QUARTER_FINALS, SEMI_FINALS, FINAL, etc. |
| `last_updated` | TIMESTAMP | `lastUpdated` | |
| `attendance` | INTEGER | `attendance` | Nullable |
| `venue` | STRING | `venue` | Nullable |
| `area` | STRING | `area` | JSON object |
| `competition` | STRING | `competition` | JSON object |
| `season` | STRING | `season` | JSON object |
| `home_team` | STRING | `homeTeam` | JSON object |
| `away_team` | STRING | `awayTeam` | JSON object |
| `score` | STRING | `score` | JSON object |
| `goals` | STRING | `goals` | JSON array |
| `bookings` | STRING | `bookings` | JSON array |
| `substitutions` | STRING | `substitutions` | JSON array |
| `penalties` | STRING | `penalties` | JSON array |
| `referees` | STRING | `referees` | JSON array |
| `odds` | STRING | `odds` | JSON object |
| `_ingested_at` | TIMESTAMP | pipeline | |

**PK**: `id` | **Partition**: `DATE(utc_date)` | **Cluster**: `id`, `status`

---

### `raw.teams`

| Column | BigQuery Type | Source | Notes |
|--------|--------------|--------|-------|
| `id` | INTEGER | `id` | |
| `name` | STRING | `name` | |
| `short_name` | STRING | `shortName` | |
| `tla` | STRING | `tla` | 3-letter abbreviation |
| `address` | STRING | `address` | Nullable |
| `website` | STRING | `website` | Nullable |
| `founded` | INTEGER | `founded` | Year |
| `club_colors` | STRING | `clubColors` | |
| `venue` | STRING | `venue` | |
| `last_updated` | TIMESTAMP | `lastUpdated` | |
| `area` | STRING | `area` | JSON object |
| `coach` | STRING | `coach` | JSON object |
| `running_competitions` | STRING | `runningCompetitions` | JSON array |
| `squad` | STRING | `squad` | JSON array of persons |
| `staff` | STRING | `staff` | JSON array |
| `_ingested_at` | TIMESTAMP | pipeline | |

**PK**: `id` | **Partition**: `DATE(_ingested_at)` | **Cluster**: `id`

---

### `raw.persons`

| Column | BigQuery Type | Source | Notes |
|--------|--------------|--------|-------|
| `id` | INTEGER | `id` | |
| `name` | STRING | `name` | |
| `first_name` | STRING | `firstName` | Nullable |
| `last_name` | STRING | `lastName` | Nullable |
| `date_of_birth` | DATE | `dateOfBirth` | |
| `nationality` | STRING | `nationality` | |
| `position` | STRING | `position` | Enum: Goalkeeper, Defence, Midfield, Offence |
| `shirt_number` | INTEGER | `shirtNumber` | Nullable |
| `last_updated` | TIMESTAMP | `lastUpdated` | |
| `current_team` | STRING | `currentTeam` | JSON object |
| `_ingested_at` | TIMESTAMP | pipeline | |

**PK**: `id` | **Partition**: `DATE(_ingested_at)` | **Cluster**: `id`

---

### `raw.standings`

> Ingested per competition + season. Each row represents a full standings table at a given matchday.

| Column | BigQuery Type | Source | Notes |
|--------|--------------|--------|-------|
| `competition_id` | INTEGER | envelope | Extracted from request context |
| `season_year` | INTEGER | envelope | e.g., 2023 for 2023/24 |
| `matchday` | INTEGER | envelope | |
| `type` | STRING | `type` | TOTAL, HOME, AWAY |
| `stage` | STRING | `stage` | |
| `group` | STRING | `group` | Nullable (used in tournaments) |
| `table` | STRING | `table` | JSON array of standing rows |
| `_ingested_at` | TIMESTAMP | pipeline | |

**Composite PK**: `(competition_id, season_year, matchday, type)` | **Partition**: `DATE(_ingested_at)`

---

### `raw.top_scorers`

> Ingested per competition + season. Each row is one player's entry in the season scorer list.

| Column | BigQuery Type | Source | Notes |
|--------|--------------|--------|-------|
| `competition_id` | INTEGER | envelope | |
| `season_year` | INTEGER | envelope | |
| `player_id` | INTEGER | `player.id` | Extracted scalar for PK check |
| `goals` | INTEGER | `goals` | |
| `assists` | INTEGER | `assists` | Nullable |
| `penalties` | INTEGER | `penalties` | Nullable |
| `player` | STRING | `player` | JSON object |
| `team` | STRING | `team` | JSON object |
| `_ingested_at` | TIMESTAMP | pipeline | |

**Composite PK**: `(competition_id, season_year, player_id)` | **Partition**: `DATE(_ingested_at)`

---

## Staging Layer

> dbt views materialized in `staging`. One model per raw table. No business logic — only renaming, type casting, and JSON flattening for analytical use.

### `stg_areas`
- `area_id` (INTEGER) — from `id`
- `name` (STRING)
- `code` (STRING)
- `parent_area_id` (INTEGER) — extracted from `parent_area` JSON
- `parent_area_name` (STRING) — extracted from `parent_area` JSON

**PK**: `area_id` | Tests: `unique`, `not_null`

---

### `stg_competitions`
- `competition_id` (INTEGER)
- `name` (STRING)
- `code` (STRING)
- `type` (STRING) — accepted_values: `LEAGUE`, `CUP`
- `area_id` (INTEGER) — from `area` JSON
- `area_name` (STRING) — from `area` JSON
- `current_season_id` (INTEGER) — from `current_season` JSON
- `current_season_start_date` (DATE)
- `current_season_end_date` (DATE)
- `last_updated` (TIMESTAMP)

**PK**: `competition_id` | Tests: `unique`, `not_null`, `accepted_values(type)`

---

### `stg_matches`
- `match_id` (INTEGER)
- `competition_id` (INTEGER) — from `competition` JSON
- `competition_code` (STRING)
- `season_year` (INTEGER) — from `season` JSON
- `matchday` (INTEGER)
- `stage` (STRING) — accepted_values: GROUP_STAGE, LAST_16, QUARTER_FINALS, SEMI_FINALS, THIRD_PLACE, FINAL, REGULAR_SEASON, PLAYOFFS
- `status` (STRING) — accepted_values: SCHEDULED, LIVE, IN_PLAY, PAUSED, FINISHED, POSTPONED, SUSPENDED, CANCELLED
- `utc_date` (TIMESTAMP)
- `home_team_id` (INTEGER) — from `home_team` JSON
- `home_team_name` (STRING)
- `away_team_id` (INTEGER) — from `away_team` JSON
- `away_team_name` (STRING)
- `home_score_full` (INTEGER) — from `score.fullTime.home`
- `away_score_full` (INTEGER) — from `score.fullTime.away`
- `home_score_half` (INTEGER) — from `score.halfTime.home`
- `away_score_half` (INTEGER) — from `score.halfTime.away`
- `winner` (STRING) — accepted_values: HOME_TEAM, AWAY_TEAM, DRAW, null
- `goals` (STRING) — JSON array, preserved for int layer
- `bookings` (STRING) — JSON array, preserved for int layer
- `substitutions` (STRING) — JSON array, preserved for int layer
- `referees` (STRING) — JSON array, preserved for int layer

**PK**: `match_id` | Tests: `unique`, `not_null`, `accepted_values(status, stage, winner)`

---

### `stg_teams`
- `team_id` (INTEGER)
- `name` (STRING)
- `short_name` (STRING)
- `tla` (STRING)
- `area_id` (INTEGER) — from `area` JSON
- `area_name` (STRING)
- `founded` (INTEGER)
- `club_colors` (STRING)
- `venue` (STRING)
- `last_updated` (TIMESTAMP)

**PK**: `team_id` | Tests: `unique`, `not_null`

---

### `stg_persons`
- `person_id` (INTEGER)
- `name` (STRING)
- `first_name` (STRING)
- `last_name` (STRING)
- `date_of_birth` (DATE)
- `nationality` (STRING)
- `position` (STRING) — accepted_values: Goalkeeper, Defence, Midfield, Offence
- `current_team_id` (INTEGER) — from `current_team` JSON

**PK**: `person_id` | Tests: `unique`, `not_null`, `accepted_values(position)`

---

### `stg_standings`
- `competition_id` (INTEGER)
- `season_year` (INTEGER)
- `matchday` (INTEGER)
- `type` (STRING) — accepted_values: `TOTAL`, `HOME`, `AWAY`
- `stage` (STRING)
- `group` (STRING)
- `position` (INTEGER) — from `table` JSON array row
- `team_id` (INTEGER) — from `table[].team.id`
- `team_name` (STRING)
- `points` (INTEGER)
- `played_games` (INTEGER)
- `won` (INTEGER)
- `drawn` (INTEGER)
- `lost` (INTEGER)
- `goals_for` (INTEGER)
- `goals_against` (INTEGER)
- `goal_difference` (INTEGER)

**PK**: `(competition_id, season_year, matchday, type, team_id)` | Tests: `unique`, `not_null`, `accepted_values(type)`

---

### `stg_top_scorers`
- `competition_id` (INTEGER)
- `season_year` (INTEGER)
- `person_id` (INTEGER) — from `player.id`
- `person_name` (STRING) — from `player.name`
- `team_id` (INTEGER) — from `team.id`
- `team_name` (STRING) — from `team.name`
- `goals` (INTEGER)
- `assists` (INTEGER)
- `penalties` (INTEGER)

**PK**: `(competition_id, season_year, person_id)` | Tests: `unique`, `not_null`

---

## Intermediate Layer

> dbt views in `intermediate`. Apply business logic: unnesting, enrichment, derived metrics.

### `int_match_events`

Unnests `goals`, `bookings`, and `substitutions` from `stg_matches` into individual event rows.

| Column | Type | Notes |
|--------|------|-------|
| `match_id` | INTEGER | FK → stg_matches |
| `event_type` | STRING | GOAL, BOOKING, SUBSTITUTION |
| `minute` | INTEGER | Match minute of event |
| `person_id` | INTEGER | From event JSON |
| `team_id` | INTEGER | From event JSON |
| `detail` | STRING | e.g., Regular, Penalty, Yellow Card, Red Card |
| `additional_person_id` | INTEGER | Assist (goals), player out (substitutions) |

**Surrogate PK**: `{{ dbt_utils.generate_surrogate_key(['match_id', 'event_type', 'minute', 'person_id']) }}`

---

### `int_competition_seasons`

Cross-join of all (competition, season) pairs with season metadata and match count.

| Column | Type | Notes |
|--------|------|-------|
| `competition_id` | INTEGER | |
| `competition_name` | STRING | |
| `competition_code` | STRING | |
| `season_year` | INTEGER | |
| `season_start_date` | DATE | |
| `season_end_date` | DATE | |
| `match_count` | INTEGER | Derived from stg_matches |
| `area_id` | INTEGER | |

**PK**: `(competition_id, season_year)`

---

## Marts Layer — Star Schema

> dbt tables in `football_analytics`. Kimball-style dimensions and facts. Incremental facts use `merge` strategy.

### Dimensions

#### `dim_areas`
- `area_id` (INTEGER, PK)
- `name` (STRING)
- `code` (STRING)
- `parent_area_id` (INTEGER, nullable)

#### `dim_competitions`
- `competition_id` (INTEGER, PK)
- `name` (STRING)
- `code` (STRING)
- `type` (STRING) — LEAGUE or CUP
- `area_id` (INTEGER, FK → dim_areas)
- `area_name` (STRING)

#### `dim_teams`
- `team_id` (INTEGER, PK)
- `name` (STRING)
- `short_name` (STRING)
- `tla` (STRING)
- `area_id` (INTEGER, FK → dim_areas)
- `founded` (INTEGER)
- `club_colors` (STRING)
- `venue` (STRING)

#### `dim_persons`
- `person_id` (INTEGER, PK)
- `name` (STRING)
- `date_of_birth` (DATE)
- `nationality` (STRING)
- `position` (STRING)

#### `dim_seasons`
- `season_key` (STRING, PK) — e.g., "PL-2023"
- `competition_id` (INTEGER)
- `season_year` (INTEGER)
- `start_date` (DATE)
- `end_date` (DATE)

---

### Facts

#### `fct_matches` (incremental, unique_key: `match_id`)
- `match_id` (INTEGER, PK)
- `competition_id` (INTEGER, FK → dim_competitions)
- `season_year` (INTEGER)
- `matchday` (INTEGER)
- `stage` (STRING)
- `status` (STRING)
- `utc_date` (TIMESTAMP)
- `home_team_id` (INTEGER, FK → dim_teams)
- `away_team_id` (INTEGER, FK → dim_teams)
- `home_score_full` (INTEGER)
- `away_score_full` (INTEGER)
- `home_score_half` (INTEGER)
- `away_score_half` (INTEGER)
- `winner` (STRING)

#### `fct_standings` (incremental, unique_key: surrogate on competition+season+matchday+type+team)
- `standing_id` (STRING, surrogate PK)
- `competition_id` (INTEGER)
- `season_year` (INTEGER)
- `matchday` (INTEGER)
- `type` (STRING) — TOTAL, HOME, AWAY
- `team_id` (INTEGER, FK → dim_teams)
- `position` (INTEGER)
- `points` (INTEGER)
- `played_games` (INTEGER)
- `won` (INTEGER)
- `drawn` (INTEGER)
- `lost` (INTEGER)
- `goals_for` (INTEGER)
- `goals_against` (INTEGER)
- `goal_difference` (INTEGER)

#### `fct_top_scorers` (incremental, unique_key: surrogate on competition+season+person)
- `scorer_id` (STRING, surrogate PK)
- `competition_id` (INTEGER)
- `season_year` (INTEGER)
- `person_id` (INTEGER, FK → dim_persons)
- `team_id` (INTEGER, FK → dim_teams)
- `goals` (INTEGER)
- `assists` (INTEGER)
- `penalties` (INTEGER)

#### `fct_match_events` (incremental, unique_key: surrogate on match+type+minute+person)
- `event_id` (STRING, surrogate PK)
- `match_id` (INTEGER, FK → fct_matches)
- `event_type` (STRING) — GOAL, BOOKING, SUBSTITUTION
- `minute` (INTEGER)
- `person_id` (INTEGER, FK → dim_persons)
- `team_id` (INTEGER, FK → dim_teams)
- `detail` (STRING)
- `additional_person_id` (INTEGER, nullable)

---

## Entity Relationship Summary

```
dim_areas ◄── dim_competitions ◄── fct_matches
               dim_areas ◄── dim_teams ──────► fct_matches (home/away)
                                   dim_teams ──► fct_standings
               dim_persons ────────────────────► fct_top_scorers
               dim_persons ────────────────────► fct_match_events
               fct_matches ────────────────────► fct_match_events
               dim_seasons ◄── fct_standings
               dim_seasons ◄── fct_top_scorers
```
