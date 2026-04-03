with matches as (
    select
        match_id,
        goals,
        bookings,
        substitutions
    from {{ ref('stg_matches') }}
),

goals_unnested as (
    select
        match_id,
        'GOAL' as event_type,
        cast(json_value(event_data, '$.minute') as int64) as minute,
        cast(json_value(event_data, '$.scorer.id') as int64) as person_id,
        cast(json_value(event_data, '$.team.id') as int64) as team_id,
        json_value(event_data, '$.type') as detail,
        cast(json_value(event_data, '$.assist.id') as int64) as additional_person_id
    from matches,
    unnest(json_extract_array(matches.goals)) as event_data
),

bookings_unnested as (
    select
        match_id,
        'BOOKING' as event_type,
        cast(json_value(event_data, '$.minute') as int64) as minute,
        cast(json_value(event_data, '$.player.id') as int64) as person_id,
        cast(json_value(event_data, '$.team.id') as int64) as team_id,
        json_value(event_data, '$.card') as detail,
        null as additional_person_id
    from matches,
    unnest(json_extract_array(matches.bookings)) as event_data
),

substitutions_unnested as (
    select
        match_id,
        'SUBSTITUTION' as event_type,
        cast(json_value(event_data, '$.minute') as int64) as minute,
        cast(json_value(event_data, '$.playerIn.id') as int64) as person_id,
        cast(json_value(event_data, '$.team.id') as int64) as team_id,
        'Substitution' as detail,
        cast(json_value(event_data, '$.playerOut.id') as int64) as additional_person_id
    from matches,
    unnest(json_extract_array(matches.substitutions)) as event_data
),

all_events as (
    select * from goals_unnested
    union all
    select * from bookings_unnested
    union all
    select * from substitutions_unnested
),

final as (
    select
        {{ dbt_utils.generate_surrogate_key([
            'match_id', 'event_type', 'minute', 'person_id'
        ]) }} as event_id,
        match_id,
        event_type,
        minute,
        person_id,
        team_id,
        detail,
        additional_person_id
    from all_events
)

select * from final
