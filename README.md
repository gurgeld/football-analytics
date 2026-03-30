# Football Analytics

Pipeline de dados end-to-end para análise de ligas europeias de futebol.

## Stack

| Camada | Ferramenta |
|---|---|
| Fonte | [Football-Data.org](https://www.football-data.org) API |
| Ingestão | Python + `google-cloud-bigquery` |
| Warehouse | Google BigQuery (free tier) |
| Transformação | dbt Core |
| Orquestração | GitHub Actions |
| Visualização | Looker Studio |

## Arquitetura

```
Football-Data.org API
        │
        ▼
  [Python Ingestion]
        │
        ▼
   BigQuery (raw)
        │
        ▼
   dbt Core: staging → intermediate → marts
        │
        ▼
   Looker Studio
```

## Estrutura do Repositório

```
football-analytics/
├── .github/workflows/     # CI/CD com GitHub Actions
├── dbt/                   # Projeto dbt
│   ├── models/
│   │   ├── staging/       # Limpeza e tipagem (views)
│   │   ├── intermediate/  # Joins e lógica de negócio (views)
│   │   └── marts/         # Modelos finais (tables/incremental)
│   ├── macros/
│   ├── tests/
│   ├── dbt_project.yml
│   └── packages.yml
├── ingestion/             # Scripts Python de ingestão
├── scripts/               # Scripts auxiliares
├── .env.example
├── requirements.txt
└── README.md
```

## Setup

### Pré-requisitos

- Python 3.10+
- Conta no Google Cloud com projeto criado
- API key do Football-Data.org (gratuita)

### Instalação

```bash
# Clonar o repositório
git clone https://github.com/seu-usuario/football-analytics.git
cd football-analytics

# Criar ambiente virtual
python -m venv .venv
source .venv/bin/activate

# Instalar dependências
pip install -r requirements.txt

# Configurar variáveis de ambiente
cp .env.example .env
# Editar .env com seus valores

# Configurar dbt
cp dbt/profiles.yml.template ~/.dbt/profiles.yml
# Editar ~/.dbt/profiles.yml com seu projeto GCP

# Instalar pacotes dbt
cd dbt && dbt deps
```

## Modelagem Dimensional

### Dimensões
- `dim_competicoes` — Ligas e torneios
- `dim_times` — Times com metadados

### Fatos
- `fct_partidas` — Partidas com placar e resultado
- `fct_classificacao` — Snapshot da tabela por rodada
- `fct_artilharia` — Gols por jogador por competição

## Licença

MIT
