# Quickstart: Football Analytics Pipeline

**Date**: 2026-04-03

---

## Prerequisites

- Python 3.11+
- A football-data.org API key (free plan)
- A Google Cloud project with BigQuery enabled
- A service account with `BigQuery Data Editor` and `BigQuery Job User` roles
- `dbt-bigquery` and `sqlfluff` installed in the Python virtual environment
- Ubuntu 22.04 LTS (for production cron scheduling)
- Git

---

## 1. Clone and Set Up the Environment

```bash
git clone <repo-url>
cd football-analytics

python3.11 -m venv .venv
source .venv/bin/activate

pip install -r requirements.txt
```

---

## 2. Configure Credentials

```bash
# Set the API key
export FOOTBALL_DATA_API_KEY="1b7ffdcec74548d7ae0046e1402e53b2"

# Set the path to your BigQuery service account JSON key
export GOOGLE_APPLICATION_CREDENTIALS="/path/to/service-account.json"

# Set BigQuery project and dataset
export BQ_PROJECT="football-analytics-prod-492213"
export BQ_RAW_DATASET="raw"
```

> Store these in a `.env` file (git-ignored) and source it: `source .env`

---

## 3. Create BigQuery Datasets

Run once to create all required datasets:

```bash
python -m ingestion.setup_bq
```

This creates (if not already present):
- `raw` — raw API mirror
- `staging` — dbt staging layer
- `intermediate` — dbt intermediate layer
- `football_analytics` — dbt star schema output

---

## 4. Run the Initial Full Backfill

> **Expected duration**: several hours (rate-limited to 10 req/min across ~12 competitions × all seasons × multiple resources). Safe to interrupt and resume — re-running will skip already-ingested records.

```bash
python -m ingestion.main
```

Monitor progress in the log file:
```bash
tail -f logs/ingestion_$(date +%Y%m%d)*.log | python -m json.tool
```

---

## 5. Run dbt Transformations

After ingestion completes:

```bash
cd dbt
dbt deps                          # Install dbt packages
dbt build                         # Run all models + tests
dbt docs generate && dbt docs serve  # Browse docs at localhost:8080
```

---

## 6. Set Up the Daily Cron Job

Edit your crontab:
```bash
crontab -e
```

Add the following line (runs daily at 06:00 UTC):
```
0 6 * * * /home/user/football-analytics/scripts/run_pipeline.sh >> /home/user/football-analytics/logs/cron.log 2>&1
```

The `run_pipeline.sh` script:
1. Activates the virtual environment
2. Runs incremental ingestion (`python -m ingestion.main`)
3. Runs `dbt build` (transformations + tests)
4. Runs `dbt docs generate`

---

## 7. Run a Full Refresh for a Specific Competition

If you need to re-ingest all data for one competition (e.g., after a data issue):

```bash
# Full refresh for Premier League, all seasons
python -m ingestion.main --full-refresh --competition PL

# Full refresh for Premier League 2023/24 season only
python -m ingestion.main --full-refresh --competition PL --season 2023
```

---

## 8. CI Pipeline (GitHub Actions)

On every pull request, CI automatically runs:
1. `dbt compile` — validates model references and DAG integrity
2. `sqlfluff lint models/` — checks SQL style against BigQuery dialect rules

### CI Secrets

Configure these secrets in your repository under **Settings → Secrets and variables → Actions**:

| Secret | Description |
|--------|-------------|
| `GOOGLE_APPLICATION_CREDENTIALS_JSON` | Base64-encoded service account JSON key. **Different from the local `GOOGLE_APPLICATION_CREDENTIALS` variable**, which is a file path. The CI workflow decodes this secret and writes it to a temp file. |
| `BQ_PROJECT` | Your GCP project ID (e.g. `football-analytics-prod-492213`) |
| `FOOTBALL_DATA_API_KEY` | football-data.org API key (required only if adding ingestion to CI in the future) |

To encode your service account key for `GOOGLE_APPLICATION_CREDENTIALS_JSON`:

```bash
base64 -w 0 /path/to/service-account.json
```

The CI workflow (`.github/workflows/ci.yml`) automatically decodes the secret and writes it to `/tmp/sa_key.json` before running `dbt compile`. The `dbt/ci_profiles/profiles.yml` file points to this path via the `GOOGLE_APPLICATION_CREDENTIALS` env var.

> **Note**: The script must be executable before scheduling the cron job. Run `chmod +x scripts/run_pipeline.sh` once after cloning.

---

## 9. Connect Looker Studio

1. Open [Looker Studio](https://lookerstudio.google.com)
2. Create a new data source → BigQuery
3. Select project: `your-gcp-project`, dataset: `football_analytics`
4. Connect to the desired mart table (e.g., `fct_matches`, `dim_competitions`)
5. Build your reports from the mart layer — do not connect directly to raw or staging tables

---

## Common Commands Reference

```bash
# Incremental ingestion (default, all resources)
python -m ingestion.main

# Incremental ingestion, matches only
python -m ingestion.main --resource matches

# Full refresh for a competition
python -m ingestion.main --full-refresh --competition PL

# dbt build (all models + tests)
cd dbt && dbt build

# dbt build, staging only
cd dbt && dbt build --select staging

# SQL lint check
sqlfluff lint dbt/models/

# SQL lint fix (auto-fix)
sqlfluff fix dbt/models/
```
