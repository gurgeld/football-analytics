import json
import logging
from datetime import datetime, timezone

from ingestion.bq_loader import BigQueryLoader
from ingestion.client import FootballDataClient

logger = logging.getLogger(__name__)

TABLE = "raw.standings"


def ingest_standings(
    client: FootballDataClient,
    loader: BigQueryLoader,
    competition_code: str,
    competition_id: int,
    season_year: int,
) -> int:
    data = client.get(
        f"/competitions/{competition_code}/standings",
        params={"season": season_year},
    )
    if data is None:
        logger.warning("No standings data for %s/%s", competition_code, season_year)
        return 0

    existing = loader.query_existing_composite_keys(
        TABLE, ["competition_id", "season_year", "matchday", "type"]
    )
    ingested_at = datetime.now(timezone.utc).isoformat()
    matchday = data.get("season", {}).get("currentMatchday")

    rows = []
    for standing in data.get("standings", []):
        standing_type = standing.get("type")
        key = (competition_id, season_year, matchday, standing_type)
        if key in existing:
            continue
        rows.append({
            "competition_id": competition_id,
            "season_year": season_year,
            "matchday": matchday,
            "type": standing_type,
            "stage": standing.get("stage"),
            "group": standing.get("group"),
            "table": json.dumps(standing.get("table", [])),
            "_ingested_at": ingested_at,
        })

    if rows:
        loader.append_rows(TABLE, rows)
        logger.info(
            "Ingested %d standing rows for %s/%s", len(rows), competition_code, season_year
        )
    return len(rows)
