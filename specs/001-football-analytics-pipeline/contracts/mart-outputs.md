# Contract: Mart Output Schemas

**Interface type**: BigQuery tables consumed by Looker Studio
**Dataset**: `football_analytics`
**Date**: 2026-04-03

This contract defines the stable output schemas that Looker Studio and any other downstream consumer may depend on. Column names and types here must not change without a migration plan.

---

## `football_analytics.dim_areas`

| Column | Type | Nullable | Description |
|--------|------|----------|-------------|
| `area_id` | INTEGER | NO | Stable area identifier (API source) |
| `name` | STRING | NO | Area name (e.g., "England") |
| `code` | STRING | YES | ISO-style code (e.g., "ENG") |
| `parent_area_id` | INTEGER | YES | ID of parent geographic area |

**Grain**: One row per area.

---

## `football_analytics.dim_competitions`

| Column | Type | Nullable | Description |
|--------|------|----------|-------------|
| `competition_id` | INTEGER | NO | Stable competition identifier |
| `name` | STRING | NO | Full competition name |
| `code` | STRING | NO | Short code (e.g., "PL", "BL1") |
| `type` | STRING | NO | LEAGUE or CUP |
| `area_id` | INTEGER | NO | FK → dim_areas |
| `area_name` | STRING | NO | Denormalized for convenience |

**Grain**: One row per competition.

---

## `football_analytics.dim_teams`

| Column | Type | Nullable | Description |
|--------|------|----------|-------------|
| `team_id` | INTEGER | NO | Stable team identifier |
| `name` | STRING | NO | Full team name |
| `short_name` | STRING | YES | Abbreviated name |
| `tla` | STRING | YES | 3-letter abbreviation |
| `area_id` | INTEGER | YES | FK → dim_areas |
| `founded` | INTEGER | YES | Year of founding |
| `club_colors` | STRING | YES | Primary colors |
| `venue` | STRING | YES | Home stadium name |

**Grain**: One row per team.

---

## `football_analytics.dim_persons`

| Column | Type | Nullable | Description |
|--------|------|----------|-------------|
| `person_id` | INTEGER | NO | Stable person identifier |
| `name` | STRING | NO | Full name |
| `date_of_birth` | DATE | YES | |
| `nationality` | STRING | YES | Nationality string |
| `position` | STRING | YES | Goalkeeper, Defence, Midfield, Offence |

**Grain**: One row per person (player, coach, or referee).

---

## `football_analytics.dim_seasons`

| Column | Type | Nullable | Description |
|--------|------|----------|-------------|
| `season_key` | STRING | NO | Surrogate key: "{competition_code}-{season_year}" |
| `competition_id` | INTEGER | NO | FK → dim_competitions |
| `season_year` | INTEGER | NO | Start year of season (e.g., 2023) |
| `start_date` | DATE | YES | Season start date |
| `end_date` | DATE | YES | Season end date |

**Grain**: One row per (competition, season).

---

## `football_analytics.fct_matches`

| Column | Type | Nullable | Description |
|--------|------|----------|-------------|
| `match_id` | INTEGER | NO | Stable match identifier (PK) |
| `competition_id` | INTEGER | NO | FK → dim_competitions |
| `season_year` | INTEGER | NO | FK ref to dim_seasons |
| `matchday` | INTEGER | YES | Matchday number |
| `stage` | STRING | NO | Match stage (GROUP_STAGE, FINAL, etc.) |
| `status` | STRING | NO | SCHEDULED, FINISHED, POSTPONED, etc. |
| `utc_date` | TIMESTAMP | NO | Match kick-off in UTC |
| `home_team_id` | INTEGER | NO | FK → dim_teams |
| `away_team_id` | INTEGER | NO | FK → dim_teams |
| `home_score_full` | INTEGER | YES | Full-time score, home team |
| `away_score_full` | INTEGER | YES | Full-time score, away team |
| `home_score_half` | INTEGER | YES | Half-time score, home team |
| `away_score_half` | INTEGER | YES | Half-time score, away team |
| `winner` | STRING | YES | HOME_TEAM, AWAY_TEAM, DRAW, or null |

**Grain**: One row per match. **Incremental key**: `match_id`.

---

## `football_analytics.fct_standings`

| Column | Type | Nullable | Description |
|--------|------|----------|-------------|
| `standing_id` | STRING | NO | Surrogate PK |
| `competition_id` | INTEGER | NO | FK → dim_competitions |
| `season_year` | INTEGER | NO | |
| `matchday` | INTEGER | NO | Matchday snapshot |
| `type` | STRING | NO | TOTAL, HOME, or AWAY |
| `team_id` | INTEGER | NO | FK → dim_teams |
| `position` | INTEGER | NO | League position at this matchday |
| `points` | INTEGER | NO | |
| `played_games` | INTEGER | NO | |
| `won` | INTEGER | NO | |
| `drawn` | INTEGER | NO | |
| `lost` | INTEGER | NO | |
| `goals_for` | INTEGER | NO | |
| `goals_against` | INTEGER | NO | |
| `goal_difference` | INTEGER | NO | |

**Grain**: One row per (competition, season, matchday, type, team). **Incremental key**: `standing_id`.

---

## `football_analytics.fct_top_scorers`

| Column | Type | Nullable | Description |
|--------|------|----------|-------------|
| `scorer_id` | STRING | NO | Surrogate PK |
| `competition_id` | INTEGER | NO | FK → dim_competitions |
| `season_year` | INTEGER | NO | |
| `person_id` | INTEGER | NO | FK → dim_persons |
| `team_id` | INTEGER | YES | FK → dim_teams |
| `goals` | INTEGER | NO | |
| `assists` | INTEGER | YES | |
| `penalties` | INTEGER | YES | |

**Grain**: One row per (competition, season, person). **Incremental key**: `scorer_id`.

---

## `football_analytics.fct_match_events`

| Column | Type | Nullable | Description |
|--------|------|----------|-------------|
| `event_id` | STRING | NO | Surrogate PK |
| `match_id` | INTEGER | NO | FK → fct_matches |
| `event_type` | STRING | NO | GOAL, BOOKING, SUBSTITUTION |
| `minute` | INTEGER | YES | Match minute |
| `person_id` | INTEGER | YES | FK → dim_persons |
| `team_id` | INTEGER | YES | FK → dim_teams |
| `detail` | STRING | YES | e.g., Regular, Penalty, Yellow Card, Red Card |
| `additional_person_id` | INTEGER | YES | Assist provider (goals) or player out (substitutions) |

**Grain**: One row per match event. **Incremental key**: `event_id`.
