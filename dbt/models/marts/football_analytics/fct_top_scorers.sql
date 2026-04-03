{{
    config(
        materialized='incremental',
        unique_key='scorer_id',
        incremental_strategy='merge'
    )
}}

with source as (
    select * from {{ ref('stg_top_scorers') }}
    {% if is_incremental() %}
        where _ingested_at > (select max(_ingested_at) from {{ this }})
    {% endif %}
)

select
    {{ dbt_utils.generate_surrogate_key([
        'competition_id', 'season_year', 'person_id'
    ]) }} as scorer_id,
    competition_id,
    season_year,
    person_id,
    team_id,
    goals,
    assists,
    penalties
from source
