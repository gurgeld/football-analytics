"""Ingestão de times da API Football-Data.org para o BigQuery.

Para cada competição em raw.competicoes, chama GET /v4/competitions/{id}/teams,
aplana o JSON e carrega em raw.times com WRITE_TRUNCATE. Times duplicados entre
competições são deduplicados pelo id antes da carga.

Uso:
    source .venv/bin/activate
    python ingestion/ingest_teams.py
"""

import json
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
    bigquery.SchemaField("id", "INTEGER"),
    bigquery.SchemaField("name", "STRING"),
    bigquery.SchemaField("short_name", "STRING"),
    bigquery.SchemaField("tla", "STRING"),
    bigquery.SchemaField("crest", "STRING"),
    bigquery.SchemaField("address", "STRING"),
    bigquery.SchemaField("website", "STRING"),
    bigquery.SchemaField("founded", "INTEGER"),
    bigquery.SchemaField("club_colors", "STRING"),
    bigquery.SchemaField("venue", "STRING"),
    bigquery.SchemaField("running_competitions", "STRING"),
    bigquery.SchemaField("coach", "STRING"),
    bigquery.SchemaField("squad", "STRING"),
    bigquery.SchemaField("staff", "STRING"),
    bigquery.SchemaField("last_updated", "TIMESTAMP"),
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


def fetch_teams(api_key: str, competition_id: int) -> list[dict]:
    """Busca os times de uma competição na API.

    Args:
        api_key: Token de autenticação da Football-Data.org.
        competition_id: ID da competição.

    Returns:
        Lista de dicionários com os dados brutos de cada time.

    Raises:
        requests.HTTPError: Se a API retornar status de erro.
    """
    url = f"{API_BASE_URL}/competitions/{competition_id}/teams"
    headers = {"X-Auth-Token": api_key}

    logger.info("Chamando %s", url)
    response = requests.get(url, headers=headers, timeout=30)
    response.raise_for_status()

    teams = response.json().get("teams", [])
    logger.info("  %d times recebidos para competição %d.", len(teams), competition_id)
    return teams


def flatten_team(team: dict) -> dict:
    """Aplana um time, serializando campos complexos como JSON string.

    Campos escalares são extraídos diretamente. Objetos e listas aninhados
    (runningCompetitions, coach, squad, staff) são serializados com json.dumps()
    para armazenamento como STRING no BigQuery.

    Args:
        team: Dicionário bruto de um time retornado pela API.

    Returns:
        Dicionário pronto para carga no BigQuery.
    """
    return {
        "id": team.get("id"),
        "name": team.get("name"),
        "short_name": team.get("shortName"),
        "tla": team.get("tla"),
        "crest": team.get("crest"),
        "address": team.get("address"),
        "website": team.get("website"),
        "founded": team.get("founded"),
        "club_colors": team.get("clubColors"),
        "venue": team.get("venue"),
        "running_competitions": json.dumps(team.get("runningCompetitions"), ensure_ascii=False),
        "coach": json.dumps(team.get("coach"), ensure_ascii=False),
        "squad": json.dumps(team.get("squad"), ensure_ascii=False),
        "staff": json.dumps(team.get("staff"), ensure_ascii=False),
        "last_updated": team.get("lastUpdated"),
    }


def load_to_bigquery(
    rows: list[dict],
    project_id: str,
    dataset: str,
    location: str,
    table: str = "times",
) -> None:
    """Carrega os times na tabela BigQuery com substituição total.

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

    logger.info("Carregando %d times em %s.", len(rows), table_ref)
    job = client.load_table_from_json(rows, table_ref, job_config=job_config, location=location)
    job.result()

    tabela = client.get_table(table_ref)
    logger.info("Carga concluída. Total de linhas na tabela: %d.", tabela.num_rows)


def main() -> None:
    """Orquestra a ingestão de times: raw.competicoes → API → raw.times."""
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

    times_por_id: dict[int, dict] = {}
    for i, competition_id in enumerate(competition_ids):
        try:
            teams_raw = fetch_teams(api_key, competition_id)
            for team in teams_raw:
                times_por_id[team["id"]] = flatten_team(team)
        except requests.HTTPError as exc:
            logger.warning("Erro ao buscar times da competição %d: %s", competition_id, exc)

        if i < len(competition_ids) - 1:
            logger.info("Aguardando %ds (rate limit)...", RATE_LIMIT_SLEEP)
            time.sleep(RATE_LIMIT_SLEEP)

    rows = list(times_por_id.values())
    logger.info("Total de times únicos após deduplicação: %d.", len(rows))

    load_to_bigquery(rows, project_id, dataset, location)


if __name__ == "__main__":
    main()
