with latest as (
    select
        team_id,
        name,
        short_name,
        tla,
        area_id,
        founded,
        club_colors,
        venue,
        _ingested_at,
        row_number() over (
            partition by team_id order by _ingested_at desc
        ) as rn
    from {{ ref('stg_teams') }}
)

select
    team_id,
    name,
    short_name,
    tla,
    area_id,
    founded,
    club_colors,
    venue
from latest
where rn = 1
