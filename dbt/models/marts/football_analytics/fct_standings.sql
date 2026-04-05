{{
    config(
        materialized='incremental',
        unique_key='standing_id',
        incremental_strategy='merge'
    )
}}

with source as (
    select * from {{ ref('stg_standings') }}
    {% if is_incremental() %}
        where _ingested_at > (select max(_ingested_at) from {{ this }})
    {% endif %}
)

select
    {{ dbt_utils.generate_surrogate_key([
        'competition_id', 'season_year', 'matchday', 'type', 'team_id'
    ]) }} as standing_id,
    competition_id,
    season_year,
    matchday,
    type,
    team_id,
    position,
    points,
    played_games,
    won,
    drawn,
    lost,
    goals_for,
    goals_against,
    goal_difference
from source
