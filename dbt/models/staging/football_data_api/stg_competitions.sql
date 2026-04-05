with source as (
    select * from {{ source('raw', 'competitions') }}
),

renamed as (
    select
        id as competition_id,
        name,
        code,
        type,
        cast(json_value(area, '$.id') as int64) as area_id,
        json_value(area, '$.name') as area_name,
        cast(json_value(current_season, '$.id') as int64) as current_season_id,
        cast(
            json_value(current_season, '$.startDate') as date
        ) as current_season_start_date,
        cast(
            json_value(current_season, '$.endDate') as date
        ) as current_season_end_date,
        cast(last_updated as timestamp) as last_updated,
        _ingested_at
    from source
)

select * from renamed
