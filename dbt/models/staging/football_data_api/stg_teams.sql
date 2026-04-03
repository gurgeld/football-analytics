with source as (
    select * from {{ source('raw', 'teams') }}
),

renamed as (
    select
        id as team_id,
        name,
        short_name,
        tla,
        cast(json_value(area, '$.id') as int64) as area_id,
        json_value(area, '$.name') as area_name,
        founded,
        club_colors,
        venue,
        cast(last_updated as timestamp) as last_updated,
        _ingested_at
    from source
)

select * from renamed
