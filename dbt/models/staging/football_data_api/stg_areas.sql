with source as (
    select * from {{ source('raw', 'areas') }}
),

renamed as (
    select
        id as area_id,
        name,
        code,
        cast(json_value(parent_area, '$.id') as int64) as parent_area_id,
        json_value(parent_area, '$.name') as parent_area_name,
        _ingested_at
    from source
)

select * from renamed
