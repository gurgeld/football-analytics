"""Football Analytics ingestion CLI.

Usage
-----
# Incremental ingestion (all resources, all competitions)
python -m ingestion.main

# Incremental, matches only
python -m ingestion.main --resource matches

# Full refresh for Premier League, all seasons
python -m ingestion.main --full-refresh --competition PL

# Full refresh for Premier League 2023/24
python -m ingestion.main --full-refresh --competition PL --season 2023
"""
import argparse
import logging
import os
import sys
from datetime import datetime

from dotenv import load_dotenv

load_dotenv()

from ingestion.bq_loader import BigQueryLoader
from ingestion.client import FootballDataClient
from ingestion.resources.areas import ingest_areas
from ingestion.resources.competitions import ingest_competitions, get_competition_seasons, FREE_PLAN_CODES
from ingestion.resources.matches import ingest_matches
from ingestion.resources.persons import ingest_persons
from ingestion.resources.standings import ingest_standings
from ingestion.resources.teams import ingest_teams
from ingestion.resources.top_scorers import ingest_top_scorers

ALL_RESOURCES = ["areas", "competitions", "matches", "teams", "persons", "standings", "top_scorers"]

# Raw tables that carry competition_id (used in full-refresh delete scope)
COMPETITION_TABLES = ["raw.matches", "raw.standings", "raw.top_scorers"]
# Tables keyed by team/person id — full-refresh re-fetches via competition teams
TEAM_PERSON_TABLES = ["raw.teams", "raw.persons"]


def _setup_logging(log_level: str) -> None:
    log_dir = "logs"
    os.makedirs(log_dir, exist_ok=True)
    timestamp = datetime.utcnow().strftime("%Y%m%d_%H%M%S")
    log_file = os.path.join(log_dir, f"ingestion_{timestamp}.log")

    logging.basicConfig(
        level=getattr(logging, log_level.upper(), logging.INFO),
        format='{"timestamp": "%(asctime)s", "level": "%(levelname)s", "logger": "%(name)s", "message": "%(message)s"}',
        handlers=[
            logging.FileHandler(log_file),
            logging.StreamHandler(sys.stderr),
        ],
    )


def _full_refresh_delete(
    loader: BigQueryLoader,
    competition_code: str,
    competition_id: int,
    season_year: int | None,
) -> None:
    """Delete all raw rows for a competition (and optionally season) before re-ingesting."""
    for table in COMPETITION_TABLES:
        loader.delete_competition_rows(table, competition_id, season_year)


def _ingest_competition_season(
    client: FootballDataClient,
    loader: BigQueryLoader,
    competition_code: str,
    competition_id: int,
    season_year: int,
    resource: str,
) -> bool:
    """Ingest a single competition/season for one resource. Returns False on skip."""
    skipped = False
    if resource in ("all", "matches"):
        ingest_matches(client, loader, competition_code, season_year)
    if resource in ("all", "teams", "persons"):
        _, squad_members = ingest_teams(client, loader, competition_code, season_year)
        if resource in ("all", "persons"):
            ingest_persons(client, loader, squad_members)
    if resource in ("all", "standings"):
        ingest_standings(client, loader, competition_code, competition_id, season_year)
    if resource in ("all", "top_scorers"):
        ingest_top_scorers(client, loader, competition_code, competition_id, season_year)
    return not skipped


def run(args: argparse.Namespace) -> int:
    """Execute ingestion. Returns exit code (0=clean, 1=skips, 2=fatal)."""
    _setup_logging(args.log_level)
    logger = logging.getLogger("ingestion.main")

    if args.full_refresh and not args.competition:
        logger.error("--full-refresh requires --competition")
        return 2

    client = FootballDataClient()
    loader = BigQueryLoader()
    had_skips = False

    # Areas and competitions (global, not per-competition)
    if args.resource in ("all", "areas"):
        ingest_areas(client, loader)
    if args.resource in ("all", "competitions"):
        ingest_competitions(client, loader)

    # Determine which competitions to process
    codes_to_process = (
        [args.competition] if args.competition else sorted(FREE_PLAN_CODES)
    )

    # Resolve competition ID → needed for composite-key tables
    comp_data = client.get("/competitions")
    comp_id_map: dict[str, int] = {}
    if comp_data:
        for c in comp_data.get("competitions", []):
            if c.get("code") in FREE_PLAN_CODES:
                comp_id_map[c["code"]] = c["id"]

    for code in codes_to_process:
        competition_id = comp_id_map.get(code)
        if competition_id is None:
            logger.warning("Unknown competition code %s; skipping", code)
            had_skips = True
            continue

        if args.full_refresh:
            _full_refresh_delete(loader, code, competition_id, args.season)

        seasons_to_process = (
            [args.season] if args.season else get_competition_seasons(client, code)
        )

        for season_year in seasons_to_process:
            logger.info("Processing %s / %s", code, season_year)
            try:
                _ingest_competition_season(
                    client, loader, code, competition_id, season_year, args.resource
                )
            except Exception as exc:
                logger.error("Error processing %s/%s: %s", code, season_year, exc)
                had_skips = True

    logger.info("Ingestion complete")
    return 1 if had_skips else 0


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Football Analytics ingestion pipeline"
    )
    parser.add_argument(
        "--resource",
        default="all",
        choices=ALL_RESOURCES + ["all"],
        help="Resource to ingest (default: all)",
    )
    parser.add_argument("--competition", help="Competition code, e.g. PL, BL1")
    parser.add_argument("--season", type=int, help="Season start year, e.g. 2023")
    parser.add_argument(
        "--full-refresh",
        action="store_true",
        help="Delete and re-ingest raw data for the specified competition (requires --competition)",
    )
    parser.add_argument(
        "--log-level",
        default="INFO",
        choices=["DEBUG", "INFO", "WARNING", "ERROR"],
    )
    args = parser.parse_args()
    sys.exit(run(args))


if __name__ == "__main__":
    main()
