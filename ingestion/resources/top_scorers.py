import json
import logging
from datetime import datetime, timezone

from ingestion.bq_loader import BigQueryLoader
from ingestion.client import FootballDataClient

logger = logging.getLogger(__name__)

TABLE = "raw.top_scorers"


def ingest_top_scorers(
    client: FootballDataClient,
    loader: BigQueryLoader,
    competition_code: str,
    competition_id: int,
    season_year: int,
) -> int:
    data = client.get(
        f"/competitions/{competition_code}/scorers",
        params={"season": season_year, "limit": 50},
    )
    if data is None:
        logger.warning("No scorer data for %s/%s", competition_code, season_year)
        return 0

    existing = loader.query_existing_composite_keys(
        TABLE, ["competition_id", "season_year", "player_id"]
    )
    ingested_at = datetime.now(timezone.utc).isoformat()

    rows = []
    for scorer in data.get("scorers", []):
        player = scorer.get("player", {})
        player_id = player.get("id")
        if player_id is None:
            continue
        key = (competition_id, season_year, player_id)
        if key in existing:
            continue
        rows.append({
            "competition_id": competition_id,
            "season_year": season_year,
            "player_id": player_id,
            "goals": scorer.get("goals"),
            "assists": scorer.get("assists"),
            "penalties": scorer.get("penalties"),
            "player": json.dumps(player),
            "team": json.dumps(scorer.get("team")),
            "_ingested_at": ingested_at,
        })

    if rows:
        loader.append_rows(TABLE, rows)
        logger.info(
            "Ingested %d top scorers for %s/%s", len(rows), competition_code, season_year
        )
    return len(rows)
