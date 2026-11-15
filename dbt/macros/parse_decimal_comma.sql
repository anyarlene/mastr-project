{#
  Parse a German-style decimal string (comma as decimal separator) to NUMERIC.
  Blank / whitespace-only values become NULL.
#}
{% macro parse_decimal_comma(expr) -%}
    safe_cast(
        replace(nullif(trim({{ expr }}), ''), ',', '.') as numeric
    )
{%- endmacro %}
