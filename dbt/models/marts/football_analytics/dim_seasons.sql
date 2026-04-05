select
    concat(competition_code, '-', cast(season_year as string)) as season_key,
    competition_id,
    season_year,
    season_start_date as start_date,
    season_end_date as end_date
from {{ ref('int_competition_seasons') }}
