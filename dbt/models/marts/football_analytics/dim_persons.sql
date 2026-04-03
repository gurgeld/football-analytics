with latest as (
    select
        person_id,
        name,
        date_of_birth,
        nationality,
        position,
        _ingested_at,
        row_number() over (
            partition by person_id order by _ingested_at desc
        ) as rn
    from {{ ref('stg_persons') }}
)

select
    person_id,
    name,
    date_of_birth,
    nationality,
    position
from latest
where rn = 1
