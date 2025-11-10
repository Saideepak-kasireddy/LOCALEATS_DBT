-- models/intermediate/int_restaurant_inspections_unified.sql
{{
    config(
        materialized='table'
    )
}}

WITH boston_inspections AS (
    SELECT
        restaurant_id,
        restaurant_name,
        inspection_id,
        match_confidence,
        inspection_date,
        days_since_inspection,
        violation_code,
        violation_severity,
        violation_severity_score,
        inspection_result,
        'BOSTON' AS data_source
    FROM {{ ref('int_restaurant_inspections') }}
),

cambridge_inspections AS (
    SELECT
        restaurant_id,
        restaurant_name,
        inspection_id,
        match_confidence,
        inspection_date,
        days_since_inspection,
        violation_code,
        violation_severity,
        violation_severity_score,
        inspection_result,
        data_source
    FROM {{ ref('int_restaurant_inspections_cambridge') }}
),

-- Union both sources
unified AS (
    SELECT * FROM boston_inspections
    UNION ALL
    SELECT * FROM cambridge_inspections
),

-- Add row numbers for deduplication if needed
with_dedup AS (
    SELECT
        *,
        ROW_NUMBER() OVER (
            PARTITION BY restaurant_id, inspection_date, violation_code 
            ORDER BY match_confidence DESC, days_since_inspection ASC
        ) AS row_num
    FROM unified
)

SELECT
    restaurant_id,
    restaurant_name,
    inspection_id,
    match_confidence,
    inspection_date,
    days_since_inspection,
    violation_code,
    violation_severity,
    violation_severity_score,
    inspection_result,
    data_source,
    CURRENT_TIMESTAMP() AS unified_at
FROM with_dedup
WHERE row_num = 1  -- Keep best match if duplicates exist