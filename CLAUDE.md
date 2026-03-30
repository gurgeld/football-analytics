# CLAUDE.md

## Visão Geral do Projeto

Pipeline de dados end-to-end para análise de ligas europeias de futebol. Dados ingeridos da API Football-Data.org, armazenados no BigQuery, transformados com dbt Core e visualizados no Looker Studio.

## Stack

- **SO:** Ubuntu
- **Warehouse:** Google BigQuery (free tier / sandbox)
- **Transformação:** dbt Core com adapter `dbt-bigquery`
- **Ingestão:** Python 3.10+ com `requests` e `google-cloud-bigquery`
- **Orquestração:** cron jobs (local) + GitHub Actions (CI/CD e schedule)
- **Visualização:** Looker Studio
- **Versionamento:** Git + GitHub
- **Linter:** ruff

## Estrutura do Repositório

```
football-analytics/
├── CLAUDE.md
├── README.md
├── .env.example              # Template de variáveis de ambiente
├── .gitignore
├── requirements.txt
├── .github/workflows/        # GitHub Actions
├── dbt/                      # Projeto dbt
│   ├── dbt_project.yml
│   ├── packages.yml
│   ├── profiles.yml.template # Template — perfil real fica em ~/.dbt/profiles.yml
│   ├── models/
│   │   ├── staging/football_data/   # Views de limpeza e tipagem
│   │   ├── intermediate/            # Joins e lógica entre staging models
│   │   └── marts/core/              # Tabelas finais (dims e fatos)
│   ├── macros/
│   ├── seeds/
│   ├── snapshots/
│   └── tests/                # Testes genéricos e singulares
├── ingestion/                # Scripts Python de ingestão
└── scripts/                  # Scripts auxiliares (setup, cron, etc.)
```

## Comandos Frequentes

### Python / Ambiente

```bash
# Ativar virtualenv
source .venv/bin/activate

# Instalar dependências
pip install -r requirements.txt

# Lint
ruff check .
ruff format .
```

### dbt (executar dentro de `cd dbt/`)

```bash
# Instalar pacotes
dbt deps

# Rodar todos os modelos + testes
dbt build

# Rodar apenas staging
dbt build --select staging.*

# Rodar um modelo específico com dependências
dbt build --select +fct_partidas

# Rodar só testes
dbt test

# Compilar SQL sem executar (debug)
dbt compile --select stg_football_data__partidas

# Gerar docs
dbt docs generate && dbt docs serve
```

### BigQuery / GCP

```bash
# Autenticação via ADC (Application Default Credentials)
gcloud auth application-default login

# Query rápida via CLI
bq query --use_legacy_sql=false 'SELECT COUNT(*) FROM raw.partidas'
```

### Git

```bash
# Convenção de branches
# feature/nome-da-feature
# fix/descricao-do-fix

# Convenção de commits (em português)
# feat: adiciona modelo fct_partidas
# fix: corrige tipagem de data em stg_partidas
# refactor: extrai lógica de resultado para macro
# docs: atualiza README com instruções de setup
# ci: adiciona workflow de dbt build no PR
```

## Convenções de Código

### Python (Ingestão)

- Sempre usar **type hints** em funções e retornos.
- Docstrings em português com formato Google style.
- Carregar variáveis de ambiente com `python-dotenv`.
- Nunca hardcodar credenciais ou API keys — usar `.env`.
- Scripts de ingestão devem ser **idempotentes**: rodar duas vezes não deve duplicar dados.
- Usar `google.cloud.bigquery.LoadJobConfig` com `write_disposition=WRITE_TRUNCATE` para carga full ou `WRITE_APPEND` para incremental (com dedup na camada dbt).
- Nomear arquivos como `ingest_{entidade}.py` (ex: `ingest_partidas.py`).
- Incluir logging com `logging` (não `print`).

### dbt

#### Naming Conventions

- **Sources:** declarar em `_sources.yml` — prefixo do arquivo: `_` (underscore).
- **Staging:** `stg_{source}__{entidade}.sql` — dois underscores entre source e entidade.
- **Intermediate:** `int_{entidade}_{verbo}.sql` (ex: `int_partidas_com_times.sql`).
- **Marts:** `dim_{entidade}.sql` ou `fct_{entidade}.sql`.
- **Schema YAMLs:** `_sources.yml`, `_stg_models.yml`, `_mart_models.yml`.

#### Materialização

- `staging/` → `view` (sem custo de storage, recalcula a cada query).
- `intermediate/` → `view` (mesma lógica do staging).
- `marts/` → `table` por padrão; usar `incremental` para fatos com alto volume ou append natural (ex: `fct_partidas`, `fct_classificacao`).

#### Style Guide SQL

- Palavras reservadas em **UPPERCASE** (`SELECT`, `FROM`, `WHERE`, `CASE`, `WHEN`).
- CTEs nomeadas descritivamente (`WITH source AS`, `WITH renamed AS`).
- Sempre usar `{{ ref('model_name') }}` para dependências entre modelos.
- Sempre usar `{{ source('source_name', 'table_name') }}` para tabelas raw.
- Usar `SAFE_CAST` no BigQuery ao invés de `CAST` para evitar erros em dados sujos.
- Surrogate keys via `{{ dbt_utils.generate_surrogate_key([...]) }}`.
- Uma coluna por linha no `SELECT`.

#### Testes

- Toda PK deve ter testes `not_null` e `unique` no YAML.
- FKs devem ter `relationships` test quando a dimensão existir.
- Testes de dados (`accepted_values`, etc.) quando aplicável.

### BigQuery — Otimizações para Free Tier

- **Sempre** selecionar colunas específicas — nunca `SELECT *` em queries manuais.
- Particionar fatos por `data_partida` (`DATE` ou `TIMESTAMP`).
- Clusterizar por colunas de filtro frequente (ex: `competicao_id`).
- Usar `LIMIT` em desenvolvimento.
- O free tier permite 1 TB de scan/mês e 10 GB de storage — manter consciência disso.
- Preferir `view` nas camadas staging/intermediate para economizar storage.

### GitHub Actions

- Workflows em `.github/workflows/`.
- CI no PR: `dbt build` com `--target dev`.
- Schedule: usar cron para ingestão + `dbt build` periódico.
- Secrets necessários: `GCP_SA_KEY` (service account JSON), `FOOTBALL_DATA_API_KEY`.

## Fonte de Dados

### Football-Data.org API

- **Base URL:** `https://api.football-data.org/v4/`
- **Auth:** Header `X-Auth-Token: {API_KEY}`
- **Rate limit:** 10 requests/minuto (free tier)
- **Competições cobertas (free tier):** PL, BL1, SA, PD, FL1, CL, WC, EC, entre outras.

### Endpoints Principais

| Endpoint | Descrição | Grão |
|---|---|---|
| `GET /competitions` | Lista competições | 1 por liga |
| `GET /competitions/{id}/teams` | Times da competição | 1 por time |
| `GET /competitions/{id}/matches` | Partidas | 1 por partida |
| `GET /competitions/{id}/standings` | Classificação | 1 por time na tabela |
| `GET /competitions/{id}/scorers` | Artilheiros | 1 por jogador |

## Modelagem Dimensional

### Camadas

1. **raw** (BigQuery dataset) — dados brutos da API, sem transformação.
2. **staging** (dbt views) — limpeza, renomeação e tipagem. Uma view por source table.
3. **intermediate** (dbt views) — joins entre staging models, lógica de negócio.
4. **marts** (dbt tables) — modelos finais consumidos pelo Looker Studio.

### Modelos

| Modelo | Tipo | Materialização |
|---|---|---|
| `dim_competicoes` | dimensão | table (full refresh) |
| `dim_times` | dimensão | table (full refresh) |
| `fct_partidas` | fato | incremental (por partida_id) |
| `fct_classificacao` | fato | incremental (snapshot por rodada) |
| `fct_artilharia` | fato | table (full refresh) |

### Chaves

- Dimensões usam **natural keys** da API (ex: `competicao_id`, `time_id`).
- Fatos sem PK natural usam **surrogate keys** via `dbt_utils.generate_surrogate_key()`.

## Variáveis de Ambiente

Definidas em `.env` (não versionado). Template em `.env.example`.

| Variável | Descrição |
|---|---|
| `FOOTBALL_DATA_API_KEY` | Token da Football-Data.org |
| `GCP_PROJECT_ID` | ID do projeto no Google Cloud |
| `BIGQUERY_DATASET_RAW` | Dataset para dados brutos (default: `raw`) |
| `BIGQUERY_LOCATION` | Região do BigQuery (default: `US`) |
| `DBT_BIGQUERY_PROJECT` | Projeto GCP usado pelo dbt |

## Cuidados Importantes

- **Nunca** versionar `.env`, `profiles.yml` ou chaves de service account.
- **Sempre** ativar o virtualenv antes de rodar scripts ou dbt.
- **Sempre** rodar `dbt deps` depois de clonar ou alterar `packages.yml`.
- Scripts de cron devem incluir `source /path/to/.venv/bin/activate` no início.
- Respeitar rate limit da API: 10 req/min. Incluir `time.sleep()` entre chamadas.
