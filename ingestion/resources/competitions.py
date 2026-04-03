import json
import logging
from datetime import datetime, timezone

from ingestion.bq_loader import BigQueryLoader
from ingestion.client import FootballDataClient

logger = logging.getLogger(__name__)

TABLE = "raw.competitions"

FREE_PLAN_CODES = frozenset(
    ["PL", "ELC", "BL1", "PD", "SA", "FL1", "DED", "PPL", "SB", "CL", "EC", "WC"]
)


def ingest_competitions(client: FootballDataClient, loader: BigQueryLoader) -> int:
    data = client.get("/competitions")
    if data is None:
        logger.error("Failed to fetch competitions")
        return 0

    existing = loader.query_existing_ids(TABLE, "id")
    ingested_at = datetime.now(timezone.utc).isoformat()

    rows = []
    for comp in data.get("competitions", []):
        if comp.get("code") not in FREE_PLAN_CODES:
            continue
        if comp["id"] in existing:
            continue
        rows.append({
            "id": comp["id"],
            "name": comp.get("name"),
            "code": comp.get("code"),
            "type": comp.get("type"),
            "emblem": comp.get("emblem"),
            "last_updated": comp.get("lastUpdated"),
            "area": json.dumps(comp.get("area")),
            "seasons": json.dumps(comp.get("seasons", [])),
            "current_season": json.dumps(comp.get("currentSeason")),
            "_ingested_at": ingested_at,
        })

    if rows:
        loader.append_rows(TABLE, rows)
        logger.info("Ingested %d new competitions", len(rows))
    return len(rows)


def get_competition_seasons(client: FootballDataClient, competition_code: str) -> list[int]:
    """Return list of season start years available for a competition."""
    data = client.get(f"/competitions/{competition_code}")
    if data is None:
        return []
    seasons = data.get("seasons", [])
    return sorted({s["startDate"][:4] for s in seasons if s.get("startDate")}, key=int)
