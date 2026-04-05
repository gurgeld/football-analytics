"""One-time BigQuery dataset and raw table setup.

Usage:
    python -m ingestion.setup_bq
"""
import logging
import os

from dotenv import load_dotenv
from google.cloud import bigquery

load_dotenv()
from google.cloud.exceptions import Conflict

logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
logger = logging.getLogger(__name__)

PROJECT = os.environ["BQ_PROJECT"]
LOCATION = "US"

DATASETS = ["raw", "staging", "intermediate", "football_analytics"]

RAW_TABLES: dict[str, list[bigquery.SchemaField]] = {
    "areas": [
        bigquery.SchemaField("id", "INTEGER"),
        bigquery.SchemaField("name", "STRING"),
        bigquery.SchemaField("code", "STRING"),
        bigquery.SchemaField("parent_area", "STRING"),
        bigquery.SchemaField("child_areas", "STRING"),
        bigquery.SchemaField("_ingested_at", "TIMESTAMP"),
    ],
    "competitions": [
        bigquery.SchemaField("id", "INTEGER"),
        bigquery.SchemaField("name", "STRING"),
        bigquery.SchemaField("code", "STRING"),
        bigquery.SchemaField("type", "STRING"),
        bigquery.SchemaField("emblem", "STRING"),
        bigquery.SchemaField("last_updated", "TIMESTAMP"),
        bigquery.SchemaField("area", "STRING"),
        bigquery.SchemaField("seasons", "STRING"),
        bigquery.SchemaField("current_season", "STRING"),
        bigquery.SchemaField("_ingested_at", "TIMESTAMP"),
    ],
    "matches": [
        bigquery.SchemaField("id", "INTEGER"),
        bigquery.SchemaField("utc_date", "TIMESTAMP"),
        bigquery.SchemaField("status", "STRING"),
        bigquery.SchemaField("matchday", "INTEGER"),
        bigquery.SchemaField("stage", "STRING"),
        bigquery.SchemaField("last_updated", "TIMESTAMP"),
        bigquery.SchemaField("attendance", "INTEGER"),
        bigquery.SchemaField("venue", "STRING"),
        bigquery.SchemaField("area", "STRING"),
        bigquery.SchemaField("competition", "STRING"),
        bigquery.SchemaField("season", "STRING"),
        bigquery.SchemaField("home_team", "STRING"),
        bigquery.SchemaField("away_team", "STRING"),
        bigquery.SchemaField("score", "STRING"),
        bigquery.SchemaField("goals", "STRING"),
        bigquery.SchemaField("bookings", "STRING"),
        bigquery.SchemaField("substitutions", "STRING"),
        bigquery.SchemaField("penalties", "STRING"),
        bigquery.SchemaField("referees", "STRING"),
        bigquery.SchemaField("odds", "STRING"),
        bigquery.SchemaField("_ingested_at", "TIMESTAMP"),
    ],
    "teams": [
        bigquery.SchemaField("id", "INTEGER"),
        bigquery.SchemaField("name", "STRING"),
        bigquery.SchemaField("short_name", "STRING"),
        bigquery.SchemaField("tla", "STRING"),
        bigquery.SchemaField("address", "STRING"),
        bigquery.SchemaField("website", "STRING"),
        bigquery.SchemaField("founded", "INTEGER"),
        bigquery.SchemaField("club_colors", "STRING"),
        bigquery.SchemaField("venue", "STRING"),
        bigquery.SchemaField("last_updated", "TIMESTAMP"),
        bigquery.SchemaField("area", "STRING"),
        bigquery.SchemaField("coach", "STRING"),
        bigquery.SchemaField("running_competitions", "STRING"),
        bigquery.SchemaField("squad", "STRING"),
        bigquery.SchemaField("staff", "STRING"),
        bigquery.SchemaField("_ingested_at", "TIMESTAMP"),
    ],
    "persons": [
        bigquery.SchemaField("id", "INTEGER"),
        bigquery.SchemaField("name", "STRING"),
        bigquery.SchemaField("first_name", "STRING"),
        bigquery.SchemaField("last_name", "STRING"),
        bigquery.SchemaField("date_of_birth", "DATE"),
        bigquery.SchemaField("nationality", "STRING"),
        bigquery.SchemaField("position", "STRING"),
        bigquery.SchemaField("shirt_number", "INTEGER"),
        bigquery.SchemaField("last_updated", "TIMESTAMP"),
        bigquery.SchemaField("current_team", "STRING"),
        bigquery.SchemaField("_ingested_at", "TIMESTAMP"),
    ],
    "standings": [
        bigquery.SchemaField("competition_id", "INTEGER"),
        bigquery.SchemaField("season_year", "INTEGER"),
        bigquery.SchemaField("matchday", "INTEGER"),
        bigquery.SchemaField("type", "STRING"),
        bigquery.SchemaField("stage", "STRING"),
        bigquery.SchemaField("group", "STRING"),
        bigquery.SchemaField("table", "STRING"),
        bigquery.SchemaField("_ingested_at", "TIMESTAMP"),
    ],
    "top_scorers": [
        bigquery.SchemaField("competition_id", "INTEGER"),
        bigquery.SchemaField("season_year", "INTEGER"),
        bigquery.SchemaField("player_id", "INTEGER"),
        bigquery.SchemaField("goals", "INTEGER"),
        bigquery.SchemaField("assists", "INTEGER"),
        bigquery.SchemaField("penalties", "INTEGER"),
        bigquery.SchemaField("player", "STRING"),
        bigquery.SchemaField("team", "STRING"),
        bigquery.SchemaField("_ingested_at", "TIMESTAMP"),
    ],
}

TABLE_PARTITIONING = {
    "matches": bigquery.TimePartitioning(field="utc_date"),
    "areas": bigquery.TimePartitioning(field="_ingested_at"),
    "competitions": bigquery.TimePartitioning(field="_ingested_at"),
    "teams": bigquery.TimePartitioning(field="_ingested_at"),
    "persons": bigquery.TimePartitioning(field="_ingested_at"),
    "standings": bigquery.TimePartitioning(field="_ingested_at"),
    "top_scorers": bigquery.TimePartitioning(field="_ingested_at"),
}

TABLE_CLUSTERING = {
    "areas": ["id"],
    "competitions": ["id"],
    "matches": ["id", "status"],
    "teams": ["id"],
    "persons": ["id"],
}


def main() -> None:
    client = bigquery.Client(project=PROJECT)

    for dataset_id in DATASETS:
        ref = bigquery.Dataset(f"{PROJECT}.{dataset_id}")
        ref.location = LOCATION
        try:
            client.create_dataset(ref)
            logger.info("Created dataset %s.%s", PROJECT, dataset_id)
        except Conflict:
            logger.info("Dataset %s.%s already exists", PROJECT, dataset_id)

    for table_name, schema in RAW_TABLES.items():
        table_ref = bigquery.Table(f"{PROJECT}.raw.{table_name}", schema=schema)
        table_ref.time_partitioning = TABLE_PARTITIONING.get(table_name)
        if table_name in TABLE_CLUSTERING:
            table_ref.clustering_fields = TABLE_CLUSTERING[table_name]
        try:
            client.create_table(table_ref)
            logger.info("Created raw table: %s", table_name)
        except Conflict:
            logger.info("Raw table already exists: %s", table_name)


if __name__ == "__main__":
    main()
