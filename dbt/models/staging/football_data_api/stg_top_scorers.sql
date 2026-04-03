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
)

select * from renamed
