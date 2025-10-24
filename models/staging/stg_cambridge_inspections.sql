-- models/staging/stg_cambridge_inspections.sql
{{
    config(
        materialized='view'
    )
}}

WITH source AS (
    SELECT * FROM {{ source('bronze', 'BRONZE_SANITARY_INSPECTIONS_CAMBRIDGE') }}
),

cleaned AS (
    SELECT
        -- Identifiers
        CASE_NUMBER AS inspection_id,
        ESTABLISHMENT_NAME AS establishment_name,
        ADDRESS AS full_address,
        STREET AS street_address,
        
        -- Location
        LATITUDE AS latitude,
        LONGITUDE AS longitude,
        
        -- Violation details
        CODE_NUMBER AS code_number,
        CODE_DESCRIPTION AS code_description,
        CODE_CASE_STATUS AS case_status,
        
        -- Dates
        TRY_TO_DATE(CASE_OPEN_DATE, 'MM/DD/YYYY') AS case_open_date,
        TRY_TO_DATE(CASE_CLOSED_DATE, 'MM/DD/YYYY') AS case_closed_date,
        TRY_TO_DATE(DATE_CORRECTED, 'MM/DD/YYYY') AS date_corrected,
        
        -- Calculate days metrics
        DATEDIFF('day', TRY_TO_DATE(CASE_OPEN_DATE, 'MM/DD/YYYY'), CURRENT_DATE()) AS days_since_case_opened,
        DATEDIFF('day', TRY_TO_DATE(CASE_OPEN_DATE, 'MM/DD/YYYY'), TRY_TO_DATE(CASE_CLOSED_DATE, 'MM/DD/YYYY')) AS days_to_resolve,
        
        -- Metadata
        MBL AS parcel_id,
        VIEWPOINT_ID AS viewpoint_id,
        LOAD_TIMESTAMP AS loaded_at,
        'CAMBRIDGE' AS data_source
        
    FROM source
    WHERE ESTABLISHMENT_NAME IS NOT NULL
        AND LATITUDE IS NOT NULL
        AND LONGITUDE IS NOT NULL
),

-- Assign severity based on Cambridge code patterns
with_severity AS (
    SELECT
        *,
        CASE
            -- Critical food safety codes (typically 2.xxx, 3.xxx, 4.xxx series)
            WHEN CODE_NUMBER LIKE '2.%' OR CODE_NUMBER LIKE '3.%' OR CODE_NUMBER LIKE '4.%' THEN 'HIGH'
            -- Structural/maintenance codes (typically 5.xxx, 6.xxx series)
            WHEN CODE_NUMBER LIKE '5.%' OR CODE_NUMBER LIKE '6.%' THEN 'MEDIUM'
            -- Administrative/minor codes
            WHEN CODE_NUMBER LIKE '7.%' OR CODE_NUMBER LIKE '8.%' THEN 'LOW'
            -- Default for unknown patterns
            ELSE 'MEDIUM'
        END AS violation_severity,
        
        CASE
            WHEN CODE_NUMBER LIKE '2.%' OR CODE_NUMBER LIKE '3.%' OR CODE_NUMBER LIKE '4.%' THEN 10
            WHEN CODE_NUMBER LIKE '5.%' OR CODE_NUMBER LIKE '6.%' THEN 5
            WHEN CODE_NUMBER LIKE '7.%' OR CODE_NUMBER LIKE '8.%' THEN 2
            ELSE 5
        END AS violation_severity_score,
        
        -- Determine if case is resolved
        CASE
            WHEN CASE_CLOSED_DATE IS NOT NULL THEN TRUE
            WHEN DATE_CORRECTED IS NOT NULL THEN TRUE
            WHEN CODE_CASE_STATUS = 'CLOSED' THEN TRUE
            ELSE FALSE
        END AS is_resolved
        
    FROM cleaned
)

SELECT * FROM with_severity