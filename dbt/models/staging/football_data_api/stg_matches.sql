with source as (
    select * from {{ source('raw', 'matches') }}
),

renamed as (
    select
        id as match_id,
        cast(json_value(competition, '$.id') as int64) as competition_id,
        json_value(competition, '$.code') as competition_code,
        cast(json_value(season, '$.startDate') as date) as season_start_date,
        cast(
            left(json_value(season, '$.startDate'), 4) as int64
        ) as season_year,
        matchday,
        stage,
        status,
        cast(utc_date as timestamp) as utc_date,
        cast(json_value(home_team, '$.id') as int64) as home_team_id,
        json_value(home_team, '$.name') as home_team_name,
        cast(json_value(away_team, '$.id') as int64) as away_team_id,
        json_value(away_team, '$.name') as away_team_name,
        cast(json_value(score, '$.fullTime.home') as int64) as home_score_full,
        cast(json_value(score, '$.fullTime.away') as int64) as away_score_full,
        cast(json_value(score, '$.halfTime.home') as int64) as home_score_half,
        cast(json_value(score, '$.halfTime.away') as int64) as away_score_half,
        json_value(score, '$.winner') as winner,
        goals,
        bookings,
        substitutions,
        referees,
        _ingested_at
    from source
)

select * from renamed
