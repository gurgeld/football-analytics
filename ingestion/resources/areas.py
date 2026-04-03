import json
import logging
from datetime import datetime, timezone

from ingestion.bq_loader import BigQueryLoader
from ingestion.client import FootballDataClient

logger = logging.getLogger(__name__)

TABLE = "raw.areas"


def ingest_areas(client: FootballDataClient, loader: BigQueryLoader) -> int:
    data = client.get("/areas")
    if data is None:
        logger.error("Failed to fetch areas")
        return 0

    existing = loader.query_existing_ids(TABLE, "id")
    ingested_at = datetime.now(timezone.utc).isoformat()

    rows = []
    for area in data.get("areas", []):
        if area["id"] in existing:
            continue
        rows.append({
            "id": area["id"],
            "name": area.get("name"),
            "code": area.get("code"),
            "parent_area": json.dumps(area.get("parentArea")),
            "child_areas": json.dumps(area.get("childAreas", [])),
            "_ingested_at": ingested_at,
        })

    if rows:
        loader.append_rows(TABLE, rows)
        logger.info("Ingested %d new areas", len(rows))
    return len(rows)
