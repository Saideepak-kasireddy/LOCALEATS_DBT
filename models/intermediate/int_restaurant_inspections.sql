-- models/intermediate/int_restaurant_inspections.sql
{{
    config(
        materialized='table'
    )
}}

WITH restaurants AS (
    SELECT * FROM {{ ref('stg_yelp_restaurants') }}
),

inspections AS (
    SELECT * FROM {{ ref('stg_health_inspections') }}
),

-- Match restaurants with inspections
matched AS (
    SELECT 
        r.restaurant_id,
        r.restaurant_name,
        r.street_address AS restaurant_address,
        r.postal_code AS restaurant_zip,
        i.inspection_id,
        i.license_no,
        i.business_name AS inspection_business_name,
        i.street_address AS inspection_address,
        i.postal_code AS inspection_zip,
        i.inspection_date,
        i.inspection_result,
        i.violation_code,
        i.violation_severity,
        i.violation_severity_score,
        i.violation_description,
        
        -- Match confidence score
        CASE
            WHEN r.restaurant_name = i.business_name THEN 100
            WHEN CONTAINS(r.restaurant_name, SPLIT_PART(i.business_name, ' ', 1)) 
                AND LENGTH(SPLIT_PART(i.business_name, ' ', 1)) > 4 THEN 85
            WHEN r.street_address = i.street_address AND r.postal_code = i.postal_code THEN 90
            WHEN SUBSTR(r.restaurant_name, 1, 5) = SUBSTR(i.business_name, 1, 5) THEN 70
            ELSE 50
        END AS match_confidence,
        
        DATEDIFF(day, i.inspection_date, CURRENT_DATE()) AS days_since_inspection
        
    FROM restaurants r
    INNER JOIN inspections i
        ON r.city = i.city  
        AND r.postal_code = i.postal_code
        AND (
            r.restaurant_name = i.business_name
            OR CONTAINS(r.restaurant_name, SPLIT_PART(i.business_name, ' ', 1))
            OR (r.street_address = i.street_address AND LEFT(r.postal_code, 3) = LEFT(i.postal_code, 3))
        )
    WHERE i.inspection_date >= DATEADD(year, -3, CURRENT_DATE())
)

SELECT * 
FROM matched
WHERE match_confidence >= 70