{#
  Use the custom schema as the full BigQuery dataset name.

  Without this, dbt concatenates target.schema + custom schema
  (e.g. mastr_staging_mastr_intermediate). Intermediate and marts
  set +schema to the exact dataset names mastr_intermediate / mastr_marts.
  Staging relies on target.schema = mastr_staging and does not set +schema.
#}
{% macro generate_schema_name(custom_schema_name, node) -%}
    {%- if custom_schema_name is none -%}
        {{ target.schema }}
    {%- else -%}
        {{ custom_schema_name | trim }}
    {%- endif -%}
{%- endmacro %}
