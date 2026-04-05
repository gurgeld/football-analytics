import json
import logging
from datetime import datetime, timezone

from ingestion.bq_loader import BigQueryLoader
from ingestion.client import FootballDataClient

logger = logging.getLogger(__name__)

TABLE = "raw.persons"


def ingest_persons(
    client: FootballDataClient,
    loader: BigQueryLoader,
    squad_members: list[dict],
) -> int:
    """Ingest person detail records discovered via squad data from teams ingestion.

    *squad_members* is the flat list of player dicts collected across all teams
    for a competition/season. Person IDs are deduplicated before fetching.
    Depends on teams ingestion completing first.
    """
    person_ids = {m["id"] for m in squad_members if m.get("id")}
    if not person_ids:
        return 0

    existing = loader.query_existing_ids(TABLE, "id")
    new_ids = person_ids - existing

    ingested_at = datetime.now(timezone.utc).isoformat()
    count = 0

    for person_id in new_ids:
        data = client.get(f"/persons/{person_id}")
        if data is None:
            logger.warning("Failed to fetch person %s", person_id)
            continue
        row = {
            "id": data.get("id"),
            "name": data.get("name"),
            "first_name": data.get("firstName"),
            "last_name": data.get("lastName"),
            "date_of_birth": data.get("dateOfBirth"),
            "nationality": data.get("nationality"),
            "position": data.get("position"),
            "shirt_number": data.get("shirtNumber"),
            "last_updated": data.get("lastUpdated"),
            "current_team": json.dumps(data.get("currentTeam")),
            "_ingested_at": ingested_at,
        }
        loader.append_rows(TABLE, [row])
        count += 1

    logger.info("Ingested %d new persons", count)
    return count
