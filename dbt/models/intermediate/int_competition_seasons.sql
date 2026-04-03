with competitions as (
    select
        competition_id,
        name as competition_name,
        code as competition_code,
        area_id,
        current_season_start_date,
        current_season_end_date
    from {{ ref('stg_competitions') }}
),

match_seasons as (
    select
        competition_id,
        season_year,
        count(*) as match_count
    from {{ ref('stg_matches') }}
    group by competition_id, season_year
),

final as (
    select
        ms.competition_id,
        c.competition_name,
        c.competition_code,
        ms.season_year,
        c.current_season_start_date as season_start_date,
        c.current_season_end_date as season_end_date,
        ms.match_count,
        c.area_id
    from match_seasons as ms
    left join competitions as c
        on ms.competition_id = c.competition_id
)

select * from final
