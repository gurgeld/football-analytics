-- Exemplo de query pronta para Looker Studio
-- Resultados de partidas com nome de competição e times

select
    m.match_id,
    c.name                                      as competition_name,
    c.code                                      as competition_code,
    m.season_year,
    m.matchday,
    m.stage,
    m.utc_date,
    m.status,
    ht.name                                     as home_team_name,
    at.name                                     as away_team_name,
    m.home_score_full,
    m.away_score_full,
    m.home_score_half,
    m.away_score_half,
    m.winner
from {{ ref('fct_matches') }}           as m
inner join {{ ref('dim_competitions') }} as c
    on m.competition_id = c.competition_id
inner join {{ ref('dim_teams') }}        as ht
    on m.home_team_id = ht.team_id
inner join {{ ref('dim_teams') }}        as at
    on m.away_team_id = at.team_id
where m.status = 'FINISHED'
order by m.utc_date desc
