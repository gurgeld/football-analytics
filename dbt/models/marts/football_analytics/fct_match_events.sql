{{
    config(
        materialized='incremental',
        unique_key='event_id',
        incremental_strategy='merge'
    )
}}
-- depends_on: {{ ref('stg_matches') }}
-- depends_on: {{ ref('fct_matches') }}

with source as (
    select * from {{ ref('int_match_events') }}
)

{% if is_incremental() %}
select * from source
where match_id in (
    select match_id
    from {{ ref('stg_matches') }}
    where _ingested_at > (select max(_ingested_at) from {{ ref('fct_matches') }})
)
{% else %}
select * from source
{% endif %}
