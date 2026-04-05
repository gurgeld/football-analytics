with source as (
    select * from {{ source('raw', 'top_scorers') }}
),

renamed as (
    select
        competition_id,
        season_year,
        player_id as person_id,
        json_value(player, '$.name') as person_name,
        cast(json_value(team, '$.id') as int64) as team_id,
        json_value(team, '$.name') as team_name,
        goals,
        assists,
        penalties,
        _ingested_at
    from source
),

deduped as (
    select * from renamed
    qualify row_number() over (
        partition by competition_id, season_year, person_id
        order by _ingested_at desc
    ) = 1
)

select * from deduped
