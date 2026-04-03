import json
import logging
from datetime import datetime, timezone

from ingestion.bq_loader import BigQueryLoader
from ingestion.client import FootballDataClient

logger = logging.getLogger(__name__)

TABLE = "raw.matches"


def ingest_matches(
    client: FootballDataClient,
    loader: BigQueryLoader,
    competition_code: str,
    season_year: int,
) -> int:
    data = client.get(
        f"/competitions/{competition_code}/matches",
        params={"season": season_year},
    )
    if data is None:
        logger.warning("No match data for %s/%s", competition_code, season_year)
        return 0

    existing = loader.query_existing_ids(TABLE, "id")
    ingested_at = datetime.now(timezone.utc).isoformat()

    rows = []
    for match in data.get("matches", []):
        if match["id"] in existing:
            continue
        rows.append({
            "id": match["id"],
            "utc_date": match.get("utcDate"),
            "status": match.get("status"),
            "matchday": match.get("matchday"),
            "stage": match.get("stage"),
            "last_updated": match.get("lastUpdated"),
            "attendance": match.get("attendance"),
            "venue": match.get("venue"),
            "area": json.dumps(match.get("area")),
            "competition": json.dumps(match.get("competition")),
            "season": json.dumps(match.get("season")),
            "home_team": json.dumps(match.get("homeTeam")),
            "away_team": json.dumps(match.get("awayTeam")),
            "score": json.dumps(match.get("score")),
            "goals": json.dumps(match.get("goals", [])),
            "bookings": json.dumps(match.get("bookings", [])),
            "substitutions": json.dumps(match.get("substitutions", [])),
            "penalties": json.dumps(match.get("penalties", [])),
            "referees": json.dumps(match.get("referees", [])),
            "odds": json.dumps(match.get("odds")),
            "_ingested_at": ingested_at,
        })

    if rows:
        loader.append_rows(TABLE, rows)
        logger.info(
            "Ingested %d new matches for %s/%s", len(rows), competition_code, season_year
        )
    return len(rows)
