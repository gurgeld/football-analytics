"""Ingestão de classificação da API Football-Data.org para o BigQuery.

Para cada competição em raw.competicoes, chama GET /v4/competitions/{id}/standings,
itera sobre os tipos de tabela (TOTAL, HOME, AWAY) e gera uma linha por
(competição, tipo, grupo, time) em raw.classificacao com WRITE_TRUNCATE.

Uso:
    source .venv/bin/activate
    python ingestion/ingest_standings.py
"""

import logging
import os
import sys
import time

import requests
from dotenv import load_dotenv
from google.cloud import bigquery

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
)
logger = logging.getLogger(__name__)

API_BASE_URL = "https://api.football-data.org/v4"
RATE_LIMIT_SLEEP = 7  # segundos entre requests (rate limit: 10 req/min)

SCHEMA = [
    bigquery.SchemaField("competition_id", "INTEGER"),
    bigquery.SchemaField("competition_name", "STRING"),
    bigquery.SchemaField("competition_code", "STRING"),
    bigquery.SchemaField("season_id", "INTEGER"),
    bigquery.SchemaField("season_start_date", "DATE"),
    bigquery.SchemaField("season_end_date", "DATE"),
    bigquery.SchemaField("season_current_matchday", "INTEGER"),
    bigquery.SchemaField("stage", "STRING"),
    bigquery.SchemaField("type", "STRING"),
    bigquery.SchemaField("group", "STRING"),
    bigquery.SchemaField("position", "INTEGER"),
    bigquery.SchemaField("team_id", "INTEGER"),
    bigquery.SchemaField("team_name", "STRING"),
    bigquery.SchemaField("team_short_name", "STRING"),
    bigquery.SchemaField("team_tla", "STRING"),
    bigquery.SchemaField("team_crest", "STRING"),
    bigquery.SchemaField("played_games", "INTEGER"),
    bigquery.SchemaField("form", "STRING"),
    bigquery.SchemaField("won", "INTEGER"),
    bigquery.SchemaField("draw", "INTEGER"),
    bigquery.SchemaField("lost", "INTEGER"),
    bigquery.SchemaField("points", "INTEGER"),
    bigquery.SchemaField("goals_for", "INTEGER"),
    bigquery.SchemaField("goals_against", "INTEGER"),
    bigquery.SchemaField("goal_difference", "INTEGER"),
]


def fetch_competition_ids(project_id: str, dataset: str) -> list[int]:
    """Lê os IDs das competições disponíveis em raw.competicoes no BigQuery.

    Args:
        project_id: ID do projeto GCP.
        dataset: Nome do dataset (ex: raw).

    Returns:
        Lista de IDs de competições.
    """
    client = bigquery.Client(project=project_id)
    query = f"SELECT id FROM `{project_id}.{dataset}.competicoes` ORDER BY id"
    rows = client.query(query).result()
    ids = [row["id"] for row in rows]
    logger.info("%d competições encontradas em raw.competicoes.", len(ids))
    return ids


def fetch_standings(api_key: str, competition_id: int) -> dict:
    """Busca a classificação de uma competição na API.

    Args:
        api_key: Token de autenticação da Football-Data.org.
        competition_id: ID da competição.

    Returns:
        JSON completo da resposta da API.

    Raises:
        requests.HTTPError: Se a API retornar status de erro.
    """
    url = f"{API_BASE_URL}/competitions/{competition_id}/standings"
    headers = {"X-Auth-Token": api_key}

    logger.info("Chamando %s", url)
    response = requests.get(url, headers=headers, timeout=30)
    response.raise_for_status()
    return response.json()


def flatten_standings(data: dict) -> list[dict]:
    """Gera linhas achatadas a partir da resposta de standings.

    Itera sobre o array standings (um por tipo: TOTAL, HOME, AWAY) e depois
    sobre o array table dentro de cada um, produzindo uma linha por
    (competition, season, stage, type, group, team).

    Args:
        data: JSON completo retornado pelo endpoint /standings.

    Returns:
        Lista de dicionários prontos para carga no BigQuery.
    """
    competition = data.get("competition") or {}
    season = data.get("season") or {}

    competition_id = competition.get("id")
    competition_name = competition.get("name")
    competition_code = competition.get("code")
    season_id = season.get("id")
    season_start_date = season.get("startDate")
    season_end_date = season.get("endDate")
    season_current_matchday = season.get("currentMatchday")

    rows = []
    for standing in data.get("standings", []):
        stage = standing.get("stage")
        standing_type = standing.get("type")
        group = standing.get("group")

        for entry in standing.get("table", []):
            team = entry.get("team") or {}
            rows.append({
                "competition_id": competition_id,
                "competition_name": competition_name,
                "competition_code": competition_code,
                "season_id": season_id,
                "season_start_date": season_start_date,
                "season_end_date": season_end_date,
                "season_current_matchday": season_current_matchday,
                "stage": stage,
                "type": standing_type,
                "group": group,
                "position": entry.get("position"),
                "team_id": team.get("id"),
                "team_name": team.get("name"),
                "team_short_name": team.get("shortName"),
                "team_tla": team.get("tla"),
                "team_crest": team.get("crest"),
                "played_games": entry.get("playedGames"),
                "form": entry.get("form"),
                "won": entry.get("won"),
                "draw": entry.get("draw"),
                "lost": entry.get("lost"),
                "points": entry.get("points"),
                "goals_for": entry.get("goalsFor"),
                "goals_against": entry.get("goalsAgainst"),
                "goal_difference": entry.get("goalDifference"),
            })

    return rows


def load_to_bigquery(
    rows: list[dict],
    project_id: str,
    dataset: str,
    location: str,
    table: str = "classificacao",
) -> None:
    """Carrega a classificação na tabela BigQuery com substituição total.

    Usa WRITE_TRUNCATE para garantir idempotência.

    Args:
        rows: Lista de dicionários a serem carregados.
        project_id: ID do projeto GCP.
        dataset: Nome do dataset BigQuery (ex: raw).
        location: Região do BigQuery (ex: US).
        table: Nome da tabela de destino.
    """
    client = bigquery.Client(project=project_id)
    table_ref = f"{project_id}.{dataset}.{table}"

    job_config = bigquery.LoadJobConfig(
        schema=SCHEMA,
        write_disposition=bigquery.WriteDisposition.WRITE_TRUNCATE,
        source_format=bigquery.SourceFormat.NEWLINE_DELIMITED_JSON,
    )

    logger.info("Carregando %d linhas em %s.", len(rows), table_ref)
    job = client.load_table_from_json(rows, table_ref, job_config=job_config, location=location)
    job.result()

    tabela = client.get_table(table_ref)
    logger.info("Carga concluída. Total de linhas na tabela: %d.", tabela.num_rows)


def main() -> None:
    """Orquestra a ingestão de classificação: raw.competicoes → API → raw.classificacao."""
    load_dotenv()

    api_key = os.getenv("FOOTBALL_DATA_API_KEY", "")
    project_id = os.getenv("GCP_PROJECT_ID", "")
    dataset = os.getenv("BIGQUERY_DATASET_RAW", "raw")
    location = os.getenv("BIGQUERY_LOCATION", "US")

    ausentes = [v for v, k in [("FOOTBALL_DATA_API_KEY", api_key), ("GCP_PROJECT_ID", project_id)] if not k]
    if ausentes:
        logger.error("Variáveis de ambiente obrigatórias não definidas: %s", ausentes)
        sys.exit(1)

    competition_ids = fetch_competition_ids(project_id, dataset)

    dedup: dict[tuple, dict] = {}
    for i, competition_id in enumerate(competition_ids):
        try:
            data = fetch_standings(api_key, competition_id)
            linhas = flatten_standings(data)
            for row in linhas:
                chave = (
                    row["competition_id"],
                    row["season_id"],
                    row["stage"],
                    row["type"],
                    row["group"],
                    row["team_id"],
                )
                dedup[chave] = row
            logger.info("  %d linhas extraídas para competição %d.", len(linhas), competition_id)
        except requests.HTTPError as exc:
            logger.warning("Erro ao buscar standings da competição %d: %s", competition_id, exc)

        if i < len(competition_ids) - 1:
            logger.info("Aguardando %ds (rate limit)...", RATE_LIMIT_SLEEP)
            time.sleep(RATE_LIMIT_SLEEP)

    rows = list(dedup.values())
    logger.info("Total de linhas únicas após deduplicação: %d.", len(rows))

    load_to_bigquery(rows, project_id, dataset, location)


if __name__ == "__main__":
    main()
