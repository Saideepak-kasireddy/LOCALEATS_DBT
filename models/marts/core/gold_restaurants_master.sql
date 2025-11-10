-- models/marts/gold_restaurants_master.sql
{{
    config(
        materialized='table',
        tags=['gold']
    )
}}

WITH restaurants AS (
    SELECT * FROM {{ ref('stg_yelp_restaurants') }}
    WHERE is_closed = FALSE
),

scores AS (
    SELECT * FROM {{ ref('int_restaurant_scores') }}
),

inspections AS (
    SELECT * FROM {{ ref('int_inspection_aggregates') }}
),

transit AS (
    SELECT
        restaurant_id,
        MIN(distance_meters) as nearest_stop_distance_m,
        MIN(walking_time_minutes) as nearest_stop_walk_time_min,
        FIRST_VALUE(stop_name) OVER (
            PARTITION BY restaurant_id 
            ORDER BY distance_meters
        ) as nearest_stop_name,
        COUNT(DISTINCT stop_id) as nearby_stops_count,
        COUNT(DISTINCT CASE WHEN is_wheelchair_accessible THEN stop_id END) as accessible_stops_count
    FROM {{ ref('int_restaurant_transit_access') }}
    WHERE proximity_rank <= 10
    GROUP BY restaurant_id, stop_name, distance_meters
    QUALIFY ROW_NUMBER() OVER (PARTITION BY restaurant_id ORDER BY distance_meters) = 1
),

-- Create rich text descriptions for embedding
restaurant_descriptions AS (
    SELECT
        r.restaurant_id,
        CONCAT(
            r.restaurant_name, '. ',
            'A ', COALESCE(r.primary_cuisine, 'restaurant'), ' restaurant ',
            'in ', r.neighborhood, ', ', r.city, '. ',
            CASE 
                WHEN r.price_tier IS NOT NULL THEN CONCAT('Price range: ', r.price_tier, '. ')
                ELSE ''
            END,
            'Rated ', r.yelp_rating, ' stars with ', r.yelp_review_count, ' reviews. ',
            'Categories: ', COALESCE(r.category_titles, 'General dining'), '. ',
            CASE 
                WHEN s.recommendation_tier = 'HIGHLY_RECOMMENDED' THEN 'Highly recommended. '
                WHEN s.recommendation_tier = 'RECOMMENDED' THEN 'Recommended. '
                ELSE ''
            END,
            CASE 
                WHEN i.health_risk_level = 'LOW_RISK' THEN 'Excellent safety record. '
                WHEN i.health_risk_level = 'MEDIUM_RISK' THEN 'Good safety record. '
                WHEN i.health_risk_level = 'HIGH_RISK' THEN 'Some safety concerns. '
                ELSE ''
            END,
            CASE 
                WHEN t.nearest_stop_distance_m <= 200 THEN 'Very close to public transit. '
                WHEN t.nearest_stop_distance_m <= 500 THEN 'Near public transit. '
                ELSE ''
            END
        ) AS search_description
    FROM restaurants r
    LEFT JOIN scores s ON r.restaurant_id = s.restaurant_id
    LEFT JOIN inspections i ON r.restaurant_id = i.restaurant_id
    LEFT JOIN transit t ON r.restaurant_id = t.restaurant_id
)

SELECT
    -- Restaurant Identity
    r.restaurant_id,
    r.restaurant_name,
    r.phone,
    r.url as yelp_url,
    
    -- Location
    r.street_address,
    r.city,
    r.state,
    r.postal_code,
    r.neighborhood,
    r.latitude,
    r.longitude,
    
    -- Cuisine & Categories
    r.primary_cuisine,
    r.category_titles,
    r.category_aliases,
    
    -- Yelp Metrics
    r.yelp_rating,
    r.yelp_review_count,
    r.price_tier,
    r.price_level,
    
    -- Scoring Dimensions
    s.safety_score,
    s.accessibility_score,
    s.popularity_score,
    s.value_score,
    s.overall_score,
    s.recommendation_tier,
    
    -- Safety Details
    i.total_inspections_all_time,
    i.pass_rate,
    i.recent_pass_rate,
    i.critical_violation_count,
    i.performance_category,
    i.health_risk_level,
    i.days_since_last_inspection,
    i.latest_inspection_date,
    
    -- Transit Details
    t.nearest_stop_name,
    t.nearest_stop_distance_m,
    t.nearest_stop_walk_time_min,
    t.nearby_stops_count,
    t.accessible_stops_count,
    
    -- Semantic Search Fields
    d.search_description,
    
    -- Metadata
    CURRENT_TIMESTAMP() as gold_created_at
    
FROM restaurants r
LEFT JOIN scores s ON r.restaurant_id = s.restaurant_id
LEFT JOIN inspections i ON r.restaurant_id = i.restaurant_id
LEFT JOIN transit t ON r.restaurant_id = t.restaurant_id
LEFT JOIN restaurant_descriptions d ON r.restaurant_id = d.restaurant_id