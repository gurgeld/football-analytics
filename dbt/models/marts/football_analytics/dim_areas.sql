select distinct
    area_id,
    name,
    code,
    parent_area_id
from {{ ref('stg_areas') }}
