-- models/intermediate/int_inspection_aggregates.sql
{{
    config(
        materialized='table'
    )
}}

-- STEP 1: Check if int_restaurant_inspections exists and works
WITH inspection_base AS (
    SELECT * FROM {{ ref('int_restaurant_inspections_unified') }}
),
-- STEP 2: Keep your original aggregation logic
inspection_trends AS (
    SELECT
        restaurant_id,
        restaurant_name,
        COUNT(DISTINCT inspection_id) AS total_inspections_all_time,
        
        -- Overall performance
        AVG(CASE WHEN inspection_result = 'PASS' THEN 1.0 ELSE 0.0 END) * 100 AS pass_rate,
        COUNT(DISTINCT violation_code) AS unique_violation_types,
        
        -- Recent 6 months performance
        COUNT(DISTINCT CASE 
            WHEN days_since_inspection <= 180 
            THEN inspection_id 
        END) AS recent_inspection_count,
        
        AVG(CASE 
            WHEN days_since_inspection <= 180 AND inspection_result = 'PASS' THEN 1.0
            WHEN days_since_inspection <= 180 AND inspection_result = 'FAIL' THEN 0.0
            ELSE NULL
        END) * 100 AS recent_pass_rate,
        
        -- Critical violations
        COUNT(DISTINCT CASE 
            WHEN violation_severity = 'HIGH' 
            THEN violation_code 
        END) AS critical_violation_count,
        
        SUM(violation_severity_score) AS total_violation_score,
        
        -- Most recent inspection
        MIN(days_since_inspection) AS days_since_last_inspection,
        MAX(inspection_date) AS latest_inspection_date
        
    FROM inspection_base
    GROUP BY 1, 2
),

-- STEP 3: Add ALL restaurants (handles NULLs)
all_restaurants AS (
    SELECT 
        r.restaurant_id,
        r.restaurant_name,
        it.total_inspections_all_time,
        it.pass_rate,
        it.unique_violation_types,
        it.recent_inspection_count,
        it.recent_pass_rate,
        it.critical_violation_count,
        it.total_violation_score,
        it.days_since_last_inspection,
        it.latest_inspection_date,
        
        -- Simple match confidence based on whether we found data
        CASE 
            WHEN it.restaurant_id IS NULL THEN 'NO_MATCH'
            WHEN it.total_inspections_all_time = 0 THEN 'NO_INSPECTIONS'
            WHEN it.total_inspections_all_time < 3 THEN 'LOW_CONFIDENCE'
            WHEN it.total_inspections_all_time < 10 THEN 'MEDIUM_CONFIDENCE'
            ELSE 'HIGH_CONFIDENCE'
        END AS match_confidence
        
    FROM {{ ref('stg_yelp_restaurants') }} r
    LEFT JOIN inspection_trends it ON r.restaurant_id = it.restaurant_id
    WHERE r.is_closed = FALSE
)

SELECT
    restaurant_id,
    restaurant_name,
    COALESCE(total_inspections_all_time, 0) AS total_inspections_all_time,
    COALESCE(pass_rate, -1) AS pass_rate,  -- -1 indicates no data
    COALESCE(unique_violation_types, 0) AS unique_violation_types,
    COALESCE(recent_inspection_count, 0) AS recent_inspection_count,
    COALESCE(recent_pass_rate, -1) AS recent_pass_rate,
    COALESCE(critical_violation_count, 0) AS critical_violation_count,
    COALESCE(total_violation_score, 0) AS total_violation_score,
    days_since_last_inspection,
    latest_inspection_date,
    match_confidence,
    
    -- Performance category (handle nulls)
    CASE
        WHEN pass_rate IS NULL OR pass_rate < 0 THEN 'NO_DATA'
        WHEN COALESCE(recent_pass_rate, pass_rate) >= 95 THEN 'EXCELLENT'
        WHEN COALESCE(recent_pass_rate, pass_rate) >= 85 THEN 'GOOD'
        WHEN COALESCE(recent_pass_rate, pass_rate) >= 70 THEN 'SATISFACTORY'
        WHEN COALESCE(recent_pass_rate, pass_rate) >= 50 THEN 'NEEDS_IMPROVEMENT'
        ELSE 'POOR'
    END AS performance_category,
    
    -- Risk level (handle nulls)
    CASE
        WHEN total_inspections_all_time IS NULL OR total_inspections_all_time = 0 THEN 'UNKNOWN_RISK'
        WHEN critical_violation_count = 0 AND COALESCE(recent_pass_rate, 100) >= 90 THEN 'LOW_RISK'
        WHEN critical_violation_count <= 2 AND COALESCE(recent_pass_rate, 100) >= 70 THEN 'MEDIUM_RISK'
        ELSE 'HIGH_RISK'
    END AS health_risk_level,
    
    CURRENT_TIMESTAMP() AS aggregation_timestamp
    
FROM all_restaurants