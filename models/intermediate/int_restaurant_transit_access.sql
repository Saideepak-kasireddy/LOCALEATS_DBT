-- models/intermediate/int_restaurant_transit_access.sql
{{
    config(
        materialized='table'
    )
}}

WITH restaurants AS (
    SELECT 
        restaurant_id,
        restaurant_name,
        latitude AS restaurant_lat,
        longitude AS restaurant_lng,
        neighborhood
    FROM {{ ref('stg_yelp_restaurants') }}
    WHERE is_closed = FALSE
),

stops AS (
    SELECT 
        stop_id,
        stop_name,
        latitude AS stop_lat,
        longitude AS stop_lng,
        is_wheelchair_accessible,
        municipality
    FROM {{ ref('stg_mbta_stops') }}
),

distance_calc AS (
    SELECT
        r.restaurant_id,
        r.restaurant_name,
        r.neighborhood,
        s.stop_id,
        s.stop_name,
        s.is_wheelchair_accessible,
        
        -- Distance in meters using Haversine formula
        ROUND(
            6371000 * ACOS(
                LEAST(1.0,
                    COS(RADIANS(r.restaurant_lat)) * 
                    COS(RADIANS(s.stop_lat)) * 
                    COS(RADIANS(s.stop_lng) - RADIANS(r.restaurant_lng)) +
                    SIN(RADIANS(r.restaurant_lat)) * 
                    SIN(RADIANS(s.stop_lat))
                )
            ), 2
        ) AS distance_meters,
        
        -- Walking time (4.5 km/h speed)
        ROUND(
            6371000 * ACOS(
                LEAST(1.0,
                    COS(RADIANS(r.restaurant_lat)) * 
                    COS(RADIANS(s.stop_lat)) * 
                    COS(RADIANS(s.stop_lng) - RADIANS(r.restaurant_lng)) +
                    SIN(RADIANS(r.restaurant_lat)) * 
                    SIN(RADIANS(s.stop_lat))
                )
            ) / 75, 1
        ) AS walking_time_minutes
        
    FROM restaurants r
    CROSS JOIN stops s
    WHERE 
        ABS(r.restaurant_lat - s.stop_lat) < 0.015 
        AND ABS(r.restaurant_lng - s.stop_lng) < 0.015
)

SELECT
    *,
    ROW_NUMBER() OVER (PARTITION BY restaurant_id ORDER BY distance_meters) AS proximity_rank,
    CASE 
        WHEN distance_meters <= 200 THEN 'IMMEDIATE'
        WHEN distance_meters <= 500 THEN 'VERY_CLOSE'
        WHEN distance_meters <= 1000 THEN 'WALKABLE'
        ELSE 'ACCESSIBLE'
    END AS accessibility_category
FROM distance_calc
WHERE distance_meters <= 1500