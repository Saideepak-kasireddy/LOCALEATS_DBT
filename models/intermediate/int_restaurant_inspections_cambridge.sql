-- models/intermediate/int_restaurant_inspections_cambridge.sql
{{
    config(
        materialized='table'
    )
}}

WITH restaurants AS (
    SELECT 
        restaurant_id,
        restaurant_name,
        street_address,
        city,
        latitude,
        longitude
    FROM {{ ref('stg_yelp_restaurants') }}
    WHERE UPPER(city) IN ('CAMBRIDGE', 'SOMERVILLE')
        AND is_closed = FALSE
),

cambridge_inspections AS (
    SELECT * FROM {{ ref('stg_cambridge_inspections') }}
),

-- Geographic matching with tighter radius for Cambridge (smaller city)
geo_matches AS (
    SELECT
        r.restaurant_id,
        r.restaurant_name,
        c.inspection_id,
        c.establishment_name,
        c.code_number,
        c.code_description,
        c.case_open_date AS inspection_date,
        c.case_status,
        c.violation_severity,
        c.violation_severity_score,
        c.is_resolved,
        c.days_since_case_opened AS days_since_inspection,
        c.data_source,
        
        -- Calculate distance
        ROUND(
            6371000 * ACOS(
                LEAST(1.0,
                    COS(RADIANS(r.latitude)) * 
                    COS(RADIANS(c.latitude)) * 
                    COS(RADIANS(c.longitude) - RADIANS(r.longitude)) +
                    SIN(RADIANS(r.latitude)) * 
                    SIN(RADIANS(c.latitude))
                )
            ), 2
        ) AS distance_meters
        
    FROM restaurants r
    INNER JOIN cambridge_inspections c
        ON ABS(r.latitude - c.latitude) < 0.002  -- Tighter radius for Cambridge
        AND ABS(r.longitude - c.longitude) < 0.002
),

-- Name similarity matching
name_matches AS (
    SELECT
        *,
        -- Calculate name similarity score
        CASE
            WHEN UPPER(TRIM(restaurant_name)) = UPPER(TRIM(establishment_name)) THEN 100
            WHEN UPPER(TRIM(restaurant_name)) LIKE '%' || UPPER(TRIM(establishment_name)) || '%' THEN 90
            WHEN UPPER(TRIM(establishment_name)) LIKE '%' || UPPER(TRIM(restaurant_name)) || '%' THEN 90
            WHEN EDITDISTANCE(UPPER(restaurant_name), UPPER(establishment_name)) <= 3 THEN 80
            WHEN EDITDISTANCE(UPPER(restaurant_name), UPPER(establishment_name)) <= 5 THEN 70
            ELSE 50
        END AS name_similarity_score,
        
        -- Distance score
        CASE
            WHEN distance_meters <= 25 THEN 100
            WHEN distance_meters <= 50 THEN 90
            WHEN distance_meters <= 100 THEN 80
            WHEN distance_meters <= 200 THEN 70
            ELSE 50
        END AS distance_score
        
    FROM geo_matches
    WHERE distance_meters <= 200  -- Max 200m radius
),

-- Calculate overall match confidence
scored_matches AS (
    SELECT
        *,
        ROUND((name_similarity_score * 0.7 + distance_score * 0.3), 0) AS match_confidence
    FROM name_matches
),

-- Keep only high-confidence matches
final_matches AS (
    SELECT
        restaurant_id,
        restaurant_name,
        inspection_id,
        establishment_name AS matched_establishment_name,
        match_confidence,
        distance_meters,
        inspection_date,
        days_since_inspection,
        code_number AS violation_code,
        code_description AS violation_description,
        violation_severity,
        violation_severity_score,
        case_status,
        is_resolved,
        
        -- Determine inspection result based on case status and resolution
        CASE
            WHEN is_resolved = TRUE THEN 'PASS'
            WHEN is_resolved = FALSE AND days_since_inspection > 90 THEN 'FAIL'
            ELSE 'PASS'
        END AS inspection_result,
        
        data_source
        
    FROM scored_matches
    WHERE match_confidence >= 70  -- Only keep good matches
)

SELECT * FROM final_matches