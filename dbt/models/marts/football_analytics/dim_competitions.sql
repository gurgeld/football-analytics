select
    competition_id,
    name,
    code,
    type,
    area_id,
    area_name
from {{ ref('stg_competitions') }}
