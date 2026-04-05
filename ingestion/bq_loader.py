import logging
import os
from typing import Any

from google.cloud import bigquery
from google.cloud.exceptions import NotFound

logger = logging.getLogger(__name__)


class BigQueryLoader:
    """Helpers for append-only writes to the raw BigQuery layer.

    All query methods return empty sets when the target table is empty or does
    not yet exist, so resource ingestors can safely call them on first run.
    """

    def __init__(self, project: str | None = None):
        self._project = project or os.environ["BQ_PROJECT"]
        self._client = bigquery.Client(project=self._project)

    # ------------------------------------------------------------------
    # Write
    # ------------------------------------------------------------------

    def append_rows(self, table_id: str, rows: list[dict[str, Any]]) -> int:
        """Insert *rows* into *table_id* (dataset.table). Returns inserted count."""
        if not rows:
            return 0
        full_table = f"{self._project}.{table_id}"
        errors = self._client.insert_rows_json(full_table, rows)
        if errors:
            logger.error("BigQuery insert errors for %s: %s", full_table, errors)
        inserted = len(rows) - len(errors)
        logger.debug("Appended %d rows to %s", inserted, full_table)
        return inserted

    # ------------------------------------------------------------------
    # Idempotency checks — safe on empty / non-existent tables
    # ------------------------------------------------------------------

    def query_existing_ids(self, table_id: str, id_column: str) -> frozenset:
        """Return the set of already-ingested scalar PKs in *table_id*.

        Returns an empty frozenset if the table is empty, does not exist, or
        is not yet queryable.
        """
        full_table = f"{self._project}.{table_id}"
        query = f"SELECT DISTINCT {id_column} FROM `{full_table}`"
        try:
            rows = self._client.query(query).result()
            return frozenset(row[id_column] for row in rows)
        except NotFound:
            logger.debug("Table %s not found; returning empty id set", full_table)
            return frozenset()
        except Exception as exc:
            logger.warning("Could not query existing ids from %s: %s", full_table, exc)
            return frozenset()

    def query_existing_composite_keys(
        self, table_id: str, columns: list[str]
    ) -> frozenset[tuple]:
        """Return frozenset of tuples for the given composite PK columns.

        Returns an empty frozenset on empty / non-existent tables.
        """
        full_table = f"{self._project}.{table_id}"
        cols = ", ".join(columns)
        query = f"SELECT DISTINCT {cols} FROM `{full_table}`"
        try:
            rows = self._client.query(query).result()
            return frozenset(tuple(row[c] for c in columns) for row in rows)
        except NotFound:
            logger.debug("Table %s not found; returning empty composite key set", full_table)
            return frozenset()
        except Exception as exc:
            logger.warning(
                "Could not query existing composite keys from %s: %s", full_table, exc
            )
            return frozenset()

    def get_max_season_ingested(self, table_id: str, competition_id: int) -> int | None:
        """Return the most recently ingested season_year for a competition, or None."""
        full_table = f"{self._project}.{table_id}"
        query = (
            f"SELECT MAX(season_year) AS max_season "
            f"FROM `{full_table}` "
            f"WHERE competition_id = {competition_id}"
        )
        try:
            rows = list(self._client.query(query).result())
            if rows:
                return rows[0]["max_season"]
            return None
        except Exception as exc:
            logger.warning("Could not query max season from %s: %s", full_table, exc)
            return None

    # ------------------------------------------------------------------
    # Full-refresh helpers
    # ------------------------------------------------------------------

    def delete_competition_rows(
        self,
        table_id: str,
        competition_id: int,
        season_year: int | None = None,
        competition_id_column: str = "competition_id",
    ) -> None:
        """Delete raw rows for a competition (and optionally a season) from *table_id*."""
        full_table = f"{self._project}.{table_id}"
        where = f"{competition_id_column} = {competition_id}"
        if season_year is not None:
            where += f" AND season_year = {season_year}"
        dml = f"DELETE FROM `{full_table}` WHERE {where}"
        try:
            self._client.query(dml).result()
            logger.info("Deleted rows from %s where %s", full_table, where)
        except NotFound:
            logger.debug("Table %s not found; nothing to delete", full_table)
        except Exception as exc:
            logger.error("Failed to delete from %s: %s", full_table, exc)
            raise
