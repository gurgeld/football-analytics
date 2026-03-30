"""Ingestão de partidas da API Football-Data.org para o BigQuery.

Para cada competição em raw.competicoes, chama GET /v4/competitions/{id}/matches,
achata o JSON e carrega em raw.partidas com WRITE_TRUNCATE.

Uso:
    source .venv/bin/activate
    python ingestion/ingest_matches.py
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
    bigquery.SchemaField("utc_date", "TIMESTAMP"),
    bigquery.SchemaField("status", "STRING"),
    bigquery.SchemaField("matchday", "INTEGER"),
    bigquery.SchemaField("stage", "STRING"),
    bigquery.SchemaField("group", "STRING"),
    bigquery.SchemaField("last_updated", "TIMESTAMP"),
    bigquery.SchemaField("competition_id", "INTEGER"),
    bigquery.SchemaField("competition_name", "STRING"),
    bigquery.SchemaField("competition_code", "STRING"),
    bigquery.SchemaField("season_id", "INTEGER"),
    bigquery.SchemaField("season_start_date", "DATE"),
    bigquery.SchemaField("season_end_date", "DATE"),
    bigquery.SchemaField("season_current_matchday", "INTEGER"),
    bigquery.SchemaField("home_team_id", "INTEGER"),
    bigquery.SchemaField("home_team_name", "STRING"),
    bigquery.SchemaField("home_team_short_name", "STRING"),
    bigquery.SchemaField("home_team_tla", "STRING"),
    bigquery.SchemaField("home_team_crest", "STRING"),
    bigquery.SchemaField("away_team_id", "INTEGER"),
    bigquery.SchemaField("away_team_name", "STRING"),
    bigquery.SchemaField("away_team_short_name", "STRING"),
    bigquery.SchemaField("away_team_tla", "STRING"),
    bigquery.SchemaField("away_team_crest", "STRING"),
    bigquery.SchemaField("score_winner", "STRING"),
    bigquery.SchemaField("score_duration", "STRING"),
    bigquery.SchemaField("score_full_time_home", "INTEGER"),
    bigquery.SchemaField("score_full_time_away", "INTEGER"),
    bigquery.SchemaField("score_half_time_home", "INTEGER"),
    bigquery.SchemaField("score_half_time_away", "INTEGER"),
    bigquery.SchemaField("odds", "STRING"),
    bigquery.SchemaField("referees", "STRING"),
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


def fetch_matches(api_key: str, competition_id: int) -> list[dict]:
    """Busca todas as partidas de uma competição na API.

    Args:
        api_key: Token de autenticação da Football-Data.org.
        competition_id: ID da competição.

    Returns:
        Lista de dicionários com os dados brutos de cada partida.

    Raises:
        requests.HTTPError: Se a API retornar status de erro.
    """
    url = f"{API_BASE_URL}/competitions/{competition_id}/matches"
    headers = {"X-Auth-Token": api_key}

    logger.info("Chamando %s", url)
    response = requests.get(url, headers=headers, timeout=30)
    response.raise_for_status()

    matches = response.json().get("matches", [])
    logger.info("  %d partidas recebidas para competição %d.", len(matches), competition_id)
    return matches


def flatten_match(match: dict) -> dict:
    """Achata os campos aninhados de uma partida.

    Campos escalares são extraídos para o nível raiz. Objetos variáveis
    (odds) e listas (referees) são serializados como JSON string.

    Args:
        match: Dicionário bruto de uma partida retornado pela API.

    Returns:
        Dicionário pronto para carga no BigQuery.
    """
    home = match.get("homeTeam") or {}
    away = match.get("awayTeam") or {}
    score = match.get("score") or {}
    full_time = score.get("fullTime") or {}
    half_time = score.get("halfTime") or {}
    competition = match.get("competition") or {}
    season = match.get("season") or {}

    return {
        "id": match.get("id"),
        "utc_date": match.get("utcDate"),
        "status": match.get("status"),
        "matchday": match.get("matchday"),
        "stage": match.get("stage"),
        "group": match.get("group"),
        "last_updated": match.get("lastUpdated"),
        "competition_id": competition.get("id"),
        "competition_name": competition.get("name"),
        "competition_code": competition.get("code"),
        "season_id": season.get("id"),
        "season_start_date": season.get("startDate"),
        "season_end_date": season.get("endDate"),
        "season_current_matchday": season.get("currentMatchday"),
        "home_team_id": home.get("id"),
        "home_team_name": home.get("name"),
        "home_team_short_name": home.get("shortName"),
        "home_team_tla": home.get("tla"),
        "home_team_crest": home.get("crest"),
        "away_team_id": away.get("id"),
        "away_team_name": away.get("name"),
        "away_team_short_name": away.get("shortName"),
        "away_team_tla": away.get("tla"),
        "away_team_crest": away.get("crest"),
        "score_winner": score.get("winner"),
        "score_duration": score.get("duration"),
        "score_full_time_home": full_time.get("home"),
        "score_full_time_away": full_time.get("away"),
        "score_half_time_home": half_time.get("home"),
        "score_half_time_away": half_time.get("away"),
        "odds": json.dumps(match.get("odds"), ensure_ascii=False),
        "referees": json.dumps(match.get("referees"), ensure_ascii=False),
    }


def load_to_bigquery(
    rows: list[dict],
    project_id: str,
    dataset: str,
    location: str,
    table: str = "partidas",
) -> None:
    """Carrega as partidas na tabela BigQuery com substituição total.

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

    logger.info("Carregando %d partidas em %s.", len(rows), table_ref)
    job = client.load_table_from_json(rows, table_ref, job_config=job_config, location=location)
    job.result()

    tabela = client.get_table(table_ref)
    logger.info("Carga concluída. Total de linhas na tabela: %d.", tabela.num_rows)


def main() -> None:
    """Orquestra a ingestão de partidas: raw.competicoes → API → raw.partidas."""
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

    partidas_por_id: dict[int, dict] = {}
    for i, competition_id in enumerate(competition_ids):
        try:
            matches_raw = fetch_matches(api_key, competition_id)
            for match in matches_raw:
                partidas_por_id[match["id"]] = flatten_match(match)
        except requests.HTTPError as exc:
            logger.warning("Erro ao buscar partidas da competição %d: %s", competition_id, exc)

        if i < len(competition_ids) - 1:
            logger.info("Aguardando %ds (rate limit)...", RATE_LIMIT_SLEEP)
            time.sleep(RATE_LIMIT_SLEEP)

    rows = list(partidas_por_id.values())
    logger.info("Total de partidas únicas após deduplicação: %d.", len(rows))

    load_to_bigquery(rows, project_id, dataset, location)


if __name__ == "__main__":
    main()
