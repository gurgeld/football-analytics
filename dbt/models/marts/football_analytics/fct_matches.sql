{{
    config(
        materialized='incremental',
        unique_key='match_id',
        incremental_strategy='merge'
    )
}}

with source as (
    select * from {{ ref('stg_matches') }}
    {% if is_incremental() %}
        where _ingested_at > (select max(_ingested_at) from {{ this }})
    {% endif %}
)

select
    match_id,
    competition_id,
    season_year,
    matchday,
    stage,
    status,
    utc_date,
    home_team_id,
    away_team_id,
    home_score_full,
    away_score_full,
    home_score_half,
    away_score_half,
    winner
from source
