"""Ingestão de competições da API Football-Data.org para o BigQuery.

Consome o endpoint GET /v4/competitions, aplana o JSON aninhado e carrega
na tabela raw.competicoes com WRITE_TRUNCATE (carga full idempotente).

Uso:
    source .venv/bin/activate
    python ingestion/ingest_competitions.py
"""

import logging
import os
import sys

import requests
from dotenv import load_dotenv
from google.cloud import bigquery

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
)
logger = logging.getLogger(__name__)

API_BASE_URL = "https://api.football-data.org/v4"

SCHEMA = [
    bigquery.SchemaField("id", "INTEGER"),
    bigquery.SchemaField("name", "STRING"),
    bigquery.SchemaField("code", "STRING"),
    bigquery.SchemaField("type", "STRING"),
    bigquery.SchemaField("emblem", "STRING"),
    bigquery.SchemaField("plan", "STRING"),
    bigquery.SchemaField("area_id", "INTEGER"),
    bigquery.SchemaField("area_name", "STRING"),
    bigquery.SchemaField("area_code", "STRING"),
    bigquery.SchemaField("area_flag", "STRING"),
    bigquery.SchemaField("current_season_id", "INTEGER"),
    bigquery.SchemaField("current_season_start_date", "DATE"),
    bigquery.SchemaField("current_season_end_date", "DATE"),
    bigquery.SchemaField("current_season_current_matchday", "INTEGER"),
    bigquery.SchemaField("number_of_available_seasons", "INTEGER"),
    bigquery.SchemaField("last_updated", "TIMESTAMP"),
]


def fetch_competitions(api_key: str) -> list[dict]:
    """Busca a lista de competições disponíveis na API.

    Args:
        api_key: Token de autenticação da Football-Data.org.

    Returns:
        Lista de dicionários com os dados brutos de cada competição.

    Raises:
        requests.HTTPError: Se a API retornar status de erro.
    """
    url = f"{API_BASE_URL}/competitions"
    headers = {"X-Auth-Token": api_key}

    logger.info("Chamando %s", url)
    response = requests.get(url, headers=headers, timeout=30)
    response.raise_for_status()

    data = response.json()
    competitions = data.get("competitions", [])
    logger.info("%d competições recebidas da API.", len(competitions))
    return competitions


def flatten_competition(competition: dict) -> dict:
    """Aplana os campos aninhados de uma competição.

    Extrai os subcampos de `area` e `currentSeason` para o nível raiz.

    Args:
        competition: Dicionário bruto de uma competição retornado pela API.

    Returns:
        Dicionário com todos os campos no nível raiz, pronto para carga no BigQuery.
    """
    area = competition.get("area") or {}
    season = competition.get("currentSeason") or {}

    return {
        "id": competition.get("id"),
        "name": competition.get("name"),
        "code": competition.get("code"),
        "type": competition.get("type"),
        "emblem": competition.get("emblem"),
        "plan": competition.get("plan"),
        "area_id": area.get("id"),
        "area_name": area.get("name"),
        "area_code": area.get("code"),
        "area_flag": area.get("flag"),
        "current_season_id": season.get("id"),
        "current_season_start_date": season.get("startDate"),
        "current_season_end_date": season.get("endDate"),
        "current_season_current_matchday": season.get("currentMatchday"),
        "number_of_available_seasons": competition.get("numberOfAvailableSeasons"),
        "last_updated": competition.get("lastUpdated"),
    }


def load_to_bigquery(
    rows: list[dict],
    project_id: str,
    dataset: str,
    location: str,
    table: str = "competicoes",
) -> None:
    """Carrega as linhas na tabela BigQuery com substituição total.

    Usa WRITE_TRUNCATE para garantir idempotência: rodar duas vezes
    produz o mesmo resultado.

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
    """Orquestra a ingestão de competições: API → BigQuery."""
    load_dotenv()

    api_key = os.getenv("FOOTBALL_DATA_API_KEY", "")
    project_id = os.getenv("GCP_PROJECT_ID", "")
    dataset = os.getenv("BIGQUERY_DATASET_RAW", "raw")
    location = os.getenv("BIGQUERY_LOCATION", "US")

    ausentes = [v for v, k in [("FOOTBALL_DATA_API_KEY", api_key), ("GCP_PROJECT_ID", project_id)] if not k]
    if ausentes:
        logger.error("Variáveis de ambiente obrigatórias não definidas: %s", ausentes)
        sys.exit(1)

    competitions_raw = fetch_competitions(api_key)
    rows = [flatten_competition(c) for c in competitions_raw]
    load_to_bigquery(rows, project_id, dataset, location)


if __name__ == "__main__":
    main()
