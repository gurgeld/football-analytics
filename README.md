# Football Analytics Pipeline

Pipeline de dados de futebol end-to-end: ingestão da API football-data.org → BigQuery → dbt → Looker Studio.

## Arquitetura

```
football-data.org API v4
        │
        ▼
  Python (ingestion)
        │  append-only, idempotente
        ▼
  BigQuery: raw
        │
        ▼
  dbt staging (views)
        │
        ▼
  dbt intermediate (views)
        │
        ▼
  dbt marts (tables / incremental)
        │
        ▼
  Looker Studio
```

## Datasets no BigQuery

| Dataset | Camada | Materialização |
|---------|--------|----------------|
| `raw` | Fonte (ingestão) | Tabelas append-only |
| `staging` | Staging | Views |
| `intermediate` | Intermediário | Views |
| `football_analytics` | Marts | Tabelas (dims) + Incremental (facts) |

## Competições cobertas (plano free)

| Código | Competição |
|--------|-----------|
| `PL` | Premier League |
| `ELC` | Championship |
| `BL1` | Bundesliga |
| `PD` | La Liga |
| `SA` | Serie A |
| `FL1` | Ligue 1 |
| `DED` | Eredivisie |
| `PPL` | Primeira Liga |
| `BSA` | Brasileirão Série A |
| `CL` | Champions League |
| `EC` | Eurocopa |
| `WC` | Copa do Mundo |

Temporadas: a partir de 2022.

## Modelos dbt (18 no total)

**Staging (7):** `stg_areas`, `stg_competitions`, `stg_matches`, `stg_teams`, `stg_persons`, `stg_standings`, `stg_top_scorers`

**Intermediate (2):** `int_match_events`, `int_competition_seasons`

**Marts (9):**
- Dims: `dim_areas`, `dim_competitions`, `dim_teams`, `dim_persons`, `dim_seasons`
- Facts: `fct_matches`, `fct_standings`, `fct_top_scorers`, `fct_match_events`

## Pré-requisitos

- Python 3.11+
- Chave de API do football-data.org (plano free)
- Projeto Google Cloud com BigQuery habilitado
- Service account com roles `BigQuery Data Editor` e `BigQuery Job User`

## Instalação

```bash
git clone https://github.com/gurgeld/football-analytics.git
cd football-analytics

python3.11 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

## Configuração

Copie o arquivo de exemplo e preencha com suas credenciais:

```bash
cp .env.example .env
```

Variáveis necessárias:

```bash
FOOTBALL_DATA_API_KEY=sua_chave_aqui
GOOGLE_APPLICATION_CREDENTIALS=/caminho/para/service-account.json
BQ_PROJECT=seu-projeto-gcp
VENV_PATH=/caminho/para/.venv
PROFILES_DIR=/caminho/para/dbt
```

## Uso

### Criar datasets no BigQuery (executar uma vez)

```bash
python -m ingestion.setup_bq
```

### Ingestão incremental (todas as competições)

```bash
python -m ingestion.main
```

### Ingestão de um recurso específico

```bash
python -m ingestion.main --resource matches
```

### Reprocessar uma competição

```bash
python -m ingestion.main --full-refresh --competition PL
python -m ingestion.main --full-refresh --competition PL --season 2023
```

### Transformações dbt

```bash
cd dbt
dbt deps
dbt build
```

### Documentação dbt

```bash
cd dbt
dbt docs generate
dbt docs serve  # acesse localhost:8080
```

## Automação (cron diário)

O script `scripts/run_pipeline.sh` executa o pipeline completo: ingestão incremental → `dbt build` → `dbt docs generate`.

Para agendar às 06:00 UTC:

```bash
chmod +x scripts/run_pipeline.sh
crontab -e
# adicionar:
0 6 * * * /caminho/para/football-analytics/scripts/run_pipeline.sh >> /caminho/para/football-analytics/logs/cron.log 2>&1
```

## CI (GitHub Actions)

Em todo pull request para `main`, o workflow `.github/workflows/ci.yml` executa:

1. `dbt compile` — valida referências e integridade do DAG
2. `sqlfluff lint` — verifica estilo SQL (dialeto BigQuery)

Secrets necessários no repositório:

| Secret | Descrição |
|--------|-----------|
| `GOOGLE_APPLICATION_CREDENTIALS_JSON` | Service account JSON em base64 |
| `BQ_PROJECT` | ID do projeto GCP |

Para codificar o service account:

```bash
base64 -w 0 /caminho/para/service-account.json
```

## Stack

- **Ingestão:** Python 3.11, `requests`, `google-cloud-bigquery`, `tenacity`
- **Transformação:** dbt-core 1.8+, dbt-bigquery
- **Qualidade:** SQLFluff 3.x, dbt tests
- **Armazenamento:** Google BigQuery
- **Agendamento:** cron + bash
- **CI:** GitHub Actions
