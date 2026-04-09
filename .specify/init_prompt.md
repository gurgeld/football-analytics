/speckit.specify

Construir um pipeline de dados de futebol end-to-end cobrindo ligas europeias e o Campeonato Brasileiro Série A.

Fonte de dados única: football-data.org API v4 (free tier, 10 req/min).
Credenciais via variáveis de ambiente: FOOTBALL_DATA_API_KEY e GCP_PROJECT_ID.

Competições no escopo: Premier League (PL), Bundesliga (BL1), Serie A (SA), Ligue 1 (FL1),
Primera Division (PD), Eredivisie (DED), Primeira Liga (PPL), Championship (ELC),
UEFA Champions League (CL) e Campeonato Brasileiro Série A (BSA).

O pipeline deve:
1. Ingerir todos os dados históricos disponíveis na API (backfill inicial)
2. Manter os dados atualizados diariamente de forma incremental, inserindo apenas o que está faltando
3. Transformar os dados em um Star Schema (dims e fcts) via dbt
4. Expor os dados para dashboards no Looker Studio

Restrições importantes:
- A camada raw preserva o payload completo da API sem perda de informação. Campos aninhados (objetos e arrays) são armazenados como JSON string
- Ingestão incremental usa append — nunca WRITE_TRUNCATE na raw
- HTTP 403 em uma competição loga o erro e continua para as demais
- Credenciais nunca hardcodadas
