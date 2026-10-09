{#- Fingerprint of everything that decides which raw trips count as valid: the
    reject-threshold variables and the source of the models that apply the rules.
    fct_trips stores it per month and rebuilds months built under a different
    fingerprint, so a rules change cannot leave stale rows behind. -#}
{% macro staging_rules_hash() -%}
    {%- if not execute -%}
        {{- return('') -}}
    {%- endif -%}
    {%- set parts = [
        tojson(var('max_trip_distance_miles')),
        tojson(var('max_trip_duration_hours')),
    ] -%}
    {%- for node in graph.nodes.values() | selectattr('resource_type', 'equalto', 'model') | sort(attribute='name') -%}
        {%- if node.name in ['stg_yellow_trips_classified', 'stg_yellow_trips', 'stg_taxi_zones'] -%}
            {%- do parts.append(node.name ~ ':' ~ node.raw_code) -%}
        {%- endif -%}
    {%- endfor -%}
    {{- return(local_md5(parts | join('|'))) -}}
{%- endmacro %}
