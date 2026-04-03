with source as (
    select * from {{ source('raw', 'persons') }}
),

renamed as (
    select
        id as person_id,
        name,
        first_name,
        last_name,
        cast(date_of_birth as date) as date_of_birth,
        nationality,
        position,
        cast(json_value(current_team, '$.id') as int64) as current_team_id,
        cast(last_updated as timestamp) as last_updated,
        _ingested_at
    from source
)

select * from renamed
