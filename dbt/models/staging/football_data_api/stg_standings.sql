with source as (
    select * from {{ source('raw', 'standings') }}
),

unnested as (
    select
        competition_id,
        season_year,
        matchday,
        type,
        stage,
        `group`,
        json_value(row_data, '$.position') as position_str,
        cast(json_value(row_data, '$.team.id') as int64) as team_id,
        json_value(row_data, '$.team.name') as team_name,
        cast(json_value(row_data, '$.points') as int64) as points,
        cast(json_value(row_data, '$.playedGames') as int64) as played_games,
        cast(json_value(row_data, '$.won') as int64) as won,
        cast(json_value(row_data, '$.draw') as int64) as drawn,
        cast(json_value(row_data, '$.lost') as int64) as lost,
        cast(json_value(row_data, '$.goalsFor') as int64) as goals_for,
        cast(json_value(row_data, '$.goalsAgainst') as int64) as goals_against,
        cast(json_value(row_data, '$.goalDifference') as int64) as goal_difference,
        _ingested_at
    from source,
    unnest(json_extract_array(source.table)) as row_data
),

deduped as (
    select
        competition_id,
        season_year,
        matchday,
        type,
        stage,
        `group`,
        cast(position_str as int64) as position,
        team_id,
        team_name,
        points,
        played_games,
        won,
        drawn,
        lost,
        goals_for,
        goals_against,
        goal_difference,
        _ingested_at
    from unnested
    qualify row_number() over (
        partition by competition_id, season_year, matchday, type, team_id
        order by _ingested_at desc
    ) = 1
)

select * from deduped
