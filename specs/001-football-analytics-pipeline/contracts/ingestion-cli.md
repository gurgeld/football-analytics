# Contract: Ingestion CLI

**Interface type**: Command-line tool (Python module invocation)
**Date**: 2026-04-03

---

## Invocation

```bash
python -m ingestion.main [OPTIONS]
```

---

## Options

| Flag | Type | Default | Description |
|------|------|---------|-------------|
| `--resource` | STRING | all | Resource to ingest: `areas`, `competitions`, `matches`, `teams`, `persons`, `standings`, `top_scorers`, or `all` |
| `--competition` | STRING | — | Competition code (e.g., `PL`, `BL1`). Required when `--full-refresh` is used. |
| `--season` | INTEGER | — | Season start year (e.g., `2023` for 2023/24). Optional filter for `--full-refresh`. |
| `--full-refresh` | FLAG | false | Triggers re-ingestion and replacement of raw records for the specified competition (and optionally season). Requires `--competition`. |
| `--log-level` | STRING | `INFO` | Logging verbosity: `DEBUG`, `INFO`, `WARNING`, `ERROR` |

---

## Behavior

### Default (incremental mode)
```bash
python -m ingestion.main
# Runs incremental ingestion for all resources and all competitions on the free plan.
# Only fetches records not already present in BigQuery raw tables.
```

### Single resource incremental
```bash
python -m ingestion.main --resource matches
# Incremental ingestion for matches only.
```

### Full refresh — competition scope
```bash
python -m ingestion.main --full-refresh --competition PL
# Deletes and re-ingests all raw records for Premier League, all seasons.
```

### Full refresh — competition + season scope
```bash
python -m ingestion.main --full-refresh --competition PL --season 2023
# Deletes and re-ingests all raw records for Premier League 2023/24 season only.
```

---

## Exit Codes

| Code | Meaning |
|------|---------|
| `0` | All records processed successfully (no errors) |
| `1` | One or more records skipped due to persistent API errors (logged; pipeline continued) |
| `2` | Fatal error — pipeline aborted (e.g., BigQuery auth failure, invalid arguments) |

---

## Output

- **stdout**: none (structured logs go to log file only)
- **stderr**: fatal errors only
- **log file**: `logs/ingestion_YYYYMMDD_HHMMSS.log` (structured JSON lines)

### Log line format
```json
{"timestamp": "2026-04-03T06:00:01Z", "level": "INFO", "resource": "matches", "competition": "PL", "season": 2023, "record_id": 12345, "action": "skipped", "reason": "already_exists"}
```

---

## Constraints

- Rate limit: ≤10 API requests/minute (enforced internally; caller does not control this)
- Retry: up to 3 attempts with exponential backoff per request; failed requests are logged and skipped
- `--full-refresh` without `--competition` is a fatal error (exit code 2)
- `--season` without `--full-refresh` is silently ignored (no effect on incremental mode)
