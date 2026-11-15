{#
  Parse a European calendar date string (DD/MM/YYYY) to DATE.
  Blank / whitespace-only values become NULL.
#}
{% macro parse_european_date(expr) -%}
    safe.parse_date('%d/%m/%Y', nullif(trim({{ expr }}), ''))
{%- endmacro %}
