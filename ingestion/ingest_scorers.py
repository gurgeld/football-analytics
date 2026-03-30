"""Ingestão de artilheiros da API Football-Data.org para o BigQuery.

Para cada competição em raw.competicoes, chama GET /v4/competitions/{id}/scorers,
achata os campos de player e team e carrega em raw.artilheiros com WRITE_TRUNCATE.
O free tier retorna até 10 artilheiros por competição.

Uso:
    source .venv/bin/activate
    python ingestion/ingest_scorers.py
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
    bigquery.SchemaField("player_id", "INTEGER"),
    bigquery.SchemaField("player_name", "STRING"),
    bigquery.SchemaField("player_first_name", "STRING"),
    bigquery.SchemaField("player_last_name", "STRING"),
    bigquery.SchemaField("player_date_of_birth", "DATE"),
    bigquery.SchemaField("player_nationality", "STRING"),
    bigquery.SchemaField("player_section", "STRING"),
    bigquery.SchemaField("player_position", "STRING"),
    bigquery.SchemaField("player_shirt_number", "INTEGER"),
    bigquery.SchemaField("team_id", "INTEGER"),
    bigquery.SchemaField("team_name", "STRING"),
    bigquery.SchemaField("team_short_name", "STRING"),
    bigquery.SchemaField("team_tla", "STRING"),
    bigquery.SchemaField("team_crest", "STRING"),
    bigquery.SchemaField("played_matches", "INTEGER"),
    bigquery.SchemaField("goals", "INTEGER"),
    bigquery.SchemaField("assists", "INTEGER"),
    bigquery.SchemaField("penalties", "INTEGER"),
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


def fetch_scorers(api_key: str, competition_id: int) -> dict:
    """Busca os artilheiros de uma competição na API.

    Args:
        api_key: Token de autenticação da Football-Data.org.
        competition_id: ID da competição.

    Returns:
        JSON completo da resposta da API.

    Raises:
        requests.HTTPError: Se a API retornar status de erro.
    """
    url = f"{API_BASE_URL}/competitions/{competition_id}/scorers"
    headers = {"X-Auth-Token": api_key}

    logger.info("Chamando %s", url)
    response = requests.get(url, headers=headers, timeout=30)
    response.raise_for_status()
    return response.json()


def flatten_scorers(data: dict) -> list[dict]:
    """Achata os registros de artilheiros de uma competição.

    Extrai campos de player{} e team{} para o nível raiz, junto com
    o contexto de competition e season.

    Args:
        data: JSON completo retornado pelo endpoint /scorers.

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
    for scorer in data.get("scorers", []):
        player = scorer.get("player") or {}
        team = scorer.get("team") or {}
        rows.append({
            "competition_id": competition_id,
            "competition_name": competition_name,
            "competition_code": competition_code,
            "season_id": season_id,
            "season_start_date": season_start_date,
            "season_end_date": season_end_date,
            "season_current_matchday": season_current_matchday,
            "player_id": player.get("id"),
            "player_name": player.get("name"),
            "player_first_name": player.get("firstName"),
            "player_last_name": player.get("lastName"),
            "player_date_of_birth": player.get("dateOfBirth"),
            "player_nationality": player.get("nationality"),
            "player_section": player.get("section"),
            "player_position": player.get("position"),
            "player_shirt_number": player.get("shirtNumber"),
            "team_id": team.get("id"),
            "team_name": team.get("name"),
            "team_short_name": team.get("shortName"),
            "team_tla": team.get("tla"),
            "team_crest": team.get("crest"),
            "played_matches": scorer.get("playedMatches"),
            "goals": scorer.get("goals"),
            "assists": scorer.get("assists"),
            "penalties": scorer.get("penalties"),
        })

    return rows


def load_to_bigquery(
    rows: list[dict],
    project_id: str,
    dataset: str,
    location: str,
    table: str = "artilheiros",
) -> None:
    """Carrega os artilheiros na tabela BigQuery com substituição total.

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

    logger.info("Carregando %d artilheiros em %s.", len(rows), table_ref)
    job = client.load_table_from_json(rows, table_ref, job_config=job_config, location=location)
    job.result()

    tabela = client.get_table(table_ref)
    logger.info("Carga concluída. Total de linhas na tabela: %d.", tabela.num_rows)


def main() -> None:
    """Orquestra a ingestão de artilheiros: raw.competicoes → API → raw.artilheiros."""
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
            data = fetch_scorers(api_key, competition_id)
            linhas = flatten_scorers(data)
            for row in linhas:
                chave = (row["competition_id"], row["season_id"], row["player_id"])
                dedup[chave] = row
            logger.info("  %d artilheiros extraídos para competição %d.", len(linhas), competition_id)
        except requests.HTTPError as exc:
            logger.warning("Erro ao buscar artilheiros da competição %d: %s", competition_id, exc)

        if i < len(competition_ids) - 1:
            logger.info("Aguardando %ds (rate limit)...", RATE_LIMIT_SLEEP)
            time.sleep(RATE_LIMIT_SLEEP)

    rows = list(dedup.values())
    logger.info("Total de artilheiros únicos após deduplicação: %d.", len(rows))

    load_to_bigquery(rows, project_id, dataset, location)


if __name__ == "__main__":
    main()
