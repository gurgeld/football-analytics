<!--
SYNC IMPACT REPORT
==================
Version change: (template) → 1.0.0
Modified principles: N/A (initial population from template)
Added sections: Core Principles (5), Restrições Técnicas, Fluxo de Desenvolvimento, Governance
Removed sections: N/A
Templates checked:
  ✅ .specify/templates/plan-template.md — alinhado com princípios
  ✅ .specify/templates/spec-template.md — sem conflitos
  ✅ .specify/templates/tasks-template.md — sem conflitos
  ✅ README.md — alinhado com stack e convenções documentadas
Deferred TODOs: nenhum
-->

# Football Analytics Pipeline Constitution

## Core Principles

### I. Camada Raw é Imutável

A camada `raw` no BigQuery é append-only. Registros existentes NUNCA devem ser
atualizados ou deletados, exceto via operação `--full-refresh` explícita e com
escopo obrigatório de competição (`--competition` é argumento obrigatório).
Todos os campos aninhados da API DEVEM ser serializados como `STRING` (JSON)
para preservar a estrutura original sem perda.

**Rationale**: Garante auditabilidade e permite reprocessamento histórico sem
depender de dados externos.

### II. Idempotência Obrigatória na Ingestão

Toda execução de `python -m ingestion.main` DEVE produzir os mesmos contadores
de linhas nas tabelas `raw` quando executada múltiplas vezes sobre os mesmos
dados. O código de ingestão DEVE verificar chaves existentes antes de inserir
(`query_existing_ids` / `query_existing_composite_keys`). Dados duplicados na
camada raw DEVEM ser deduplicados na camada staging via `QUALIFY ROW_NUMBER()`.

**Rationale**: Previne duplicatas que propagariam erros para todas as camadas
downstream e dão falso positivo nos testes dbt.

### III. Qualidade de Dados via Testes dbt (NÃO NEGOCIÁVEL)

Todo modelo dbt DEVE ter ao menos os testes `unique` e `not_null` na coluna de
chave primária. Colunas com domínio fechado DEVEM ter `accepted_values`. Fatos
compostos DEVEM usar `dbt_utils.unique_combination_of_columns`. O comando
`dbt build` DEVE passar com zero erros antes de qualquer merge para `main`.

**Rationale**: Detecta dados inválidos antes de chegarem ao dashboard, evitando
decisões baseadas em métricas incorretas.

### IV. Custo Zero no BigQuery (Plano Free)

Staging e intermediate DEVEM ser materializados como `view` (sem armazenamento).
Facts DEVEM usar `incremental` com `merge` strategy — nunca `full-refresh` em
produção. Queries NUNCA devem usar `SELECT *` em tabelas grandes sem filtro.
O modelo `generate_schema_name` DEVE rotear modelos para os datasets corretos
sem depender de parâmetro de profile.

**Rationale**: O projeto opera no plano gratuito do BigQuery. Materializações
incorretas geram cobranças inesperadas.

### V. Nomenclatura em Português Brasileiro

Todos os identificadores SQL (aliases, CTEs, colunas derivadas), comentários em
código, mensagens de log descritivas e mensagens de commit DEVEM estar em
português brasileiro. Nomes de tabelas e colunas que espelham a API externa
PODEM manter o inglês (e.g., `match_id`, `season_year`). Princípio não se
aplica a nomes de variáveis de ambiente e configuração de ferramentas.

**Rationale**: Convenção estabelecida pelo time para facilitar leitura e revisão
no contexto do projeto.

## Restrições Técnicas

- **Python**: 3.11+. Dependências declaradas em `requirements.txt` (produção) e
  `requirements-dev.txt` (lint/testes).
- **Rate limit**: ≤10 requisições/minuto para a API football-data.org, aplicado
  via sliding-window no `ingestion/client.py`.
- **Retry**: falhas transitórias (HTTP 5xx, timeout) DEVEM usar backoff
  exponencial com no máximo 3 tentativas (via `tenacity`).
- **Competições**: apenas os 12 códigos do plano free são válidos (`FREE_PLAN_CODES`
  em `ingestion/resources/competitions.py`). Temporadas a partir de 2022 (`MIN_SEASON`).
- **CI**: todo PR para `main` DEVE passar em `dbt compile` e `sqlfluff lint`
  via GitHub Actions antes de ser mergeado.
- **dbt**: dbt-core 1.8+, adapter dbt-bigquery. Pacotes declarados em
  `dbt/packages.yml`. Chaves surrogate via `dbt_utils.generate_surrogate_key`.

## Fluxo de Desenvolvimento

1. Toda feature DEVE ser desenvolvida em branch separada com prefixo numérico
   (e.g., `001-nome-da-feature`).
2. Spec, plano e tarefas DEVEM existir em `specs/<id>-<nome>/` antes da
   implementação.
3. Tarefas marcadas `[P]` PODEM ser executadas em paralelo; demais são
   sequenciais e dependentes.
4. `dbt build` (zero erros) é pré-requisito para PR. `dbt test` é executado
   como parte do `dbt build`.
5. Mensagens de commit DEVEM seguir o padrão Conventional Commits em português
   (e.g., `feat:`, `fix:`, `docs:`).
6. Automação diária via `scripts/run_pipeline.sh` agendado no cron às 06:00 UTC.

## Governance

Esta constituição define as regras inegociáveis do projeto. Em caso de conflito
com qualquer outra documentação, esta constituição prevalece.

**Processo de emenda**: qualquer alteração a um princípio existente ou adição
de novo princípio DEVE ser registrada neste arquivo com bump de versão seguindo
semver (MAJOR = remoção/redefinição incompatível, MINOR = novo princípio,
PATCH = clarificação). A data `Last Amended` DEVE ser atualizada.

**Compliance**: toda PR review DEVE verificar conformidade com os princípios I–V.
Violações detectadas em review bloqueiam o merge.

**Arquivo de orientação em runtime**: `CLAUDE.md` na raiz do repositório contém
orientações operacionais para o agente de desenvolvimento e DEVE estar alinhado
com esta constituição.

**Version**: 1.0.0 | **Ratified**: 2026-04-06 | **Last Amended**: 2026-04-06
