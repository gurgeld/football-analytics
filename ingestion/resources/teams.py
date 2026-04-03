import json
import logging
from datetime import datetime, timezone

from ingestion.bq_loader import BigQueryLoader
from ingestion.client import FootballDataClient

logger = logging.getLogger(__name__)

TABLE = "raw.teams"


def ingest_teams(
    client: FootballDataClient,
    loader: BigQueryLoader,
    competition_code: str,
    season_year: int,
) -> tuple[int, list[dict]]:
    """Ingest teams for a competition/season. Returns (count_inserted, squad_members)."""
    data = client.get(
        f"/competitions/{competition_code}/teams",
        params={"season": season_year},
    )
    if data is None:
        logger.warning("No team data for %s/%s", competition_code, season_year)
        return 0, []

    existing = loader.query_existing_ids(TABLE, "id")
    ingested_at = datetime.now(timezone.utc).isoformat()

    rows = []
    all_squad_members: list[dict] = []

    for team in data.get("teams", []):
        squad = team.get("squad", [])
        all_squad_members.extend(squad)

        if team["id"] in existing:
            continue
        rows.append({
            "id": team["id"],
            "name": team.get("name"),
            "short_name": team.get("shortName"),
            "tla": team.get("tla"),
            "address": team.get("address"),
            "website": team.get("website"),
            "founded": team.get("founded"),
            "club_colors": team.get("clubColors"),
            "venue": team.get("venue"),
            "last_updated": team.get("lastUpdated"),
            "area": json.dumps(team.get("area")),
            "coach": json.dumps(team.get("coach")),
            "running_competitions": json.dumps(team.get("runningCompetitions", [])),
            "squad": json.dumps(squad),
            "staff": json.dumps(team.get("staff", [])),
            "_ingested_at": ingested_at,
        })

    if rows:
        loader.append_rows(TABLE, rows)
        logger.info(
            "Ingested %d new teams for %s/%s", len(rows), competition_code, season_year
        )
    return len(rows), all_squad_members
