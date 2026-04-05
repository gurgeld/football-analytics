{% macro generate_schema_name(custom_schema_name, node) -%}
    {#-
        Override the default dbt macro to route models to the correct BigQuery
        dataset based on the custom_schema_name configured in dbt_project.yml.
        This ignores the profile's default schema so every environment uses the
        same dataset names (raw, staging, intermediate, football_analytics).
    -#}
    {%- if custom_schema_name is none -%}
        {{ default_schema }}
    {%- else -%}
        {{ custom_schema_name | trim }}
    {%- endif -%}
{%- endmacro %}
