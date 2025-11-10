-- models/staging/stg_yelp_restaurants.sql
WITH source_data AS (
    SELECT * FROM {{ source('bronze', 'bronze_yelp_restaurants') }}
),

-- Remove duplicates based on restaurant_id and loaded_at
deduped AS (
    SELECT *,
        ROW_NUMBER() OVER (
            PARTITION BY restaurant_id 
            ORDER BY loaded_at DESC, updated_at DESC
        ) AS rn
    FROM source_data
),

cleaned AS (
    SELECT
        -- IDs
        restaurant_id,
        
        -- Basic Info (standardized business name like health inspections)
        REGEXP_REPLACE(
            TRIM(UPPER(COALESCE(name, 'UNKNOWN_RESTAURANT'))), 
            '\\s+', ' '
        ) AS restaurant_name,
        COALESCE(NULLIF(TRIM(phone), ''), 'NO_PHONE') AS phone,
        COALESCE(NULLIF(TRIM(url), ''), '') AS url,
        
        -- Address (dropping address2)
        COALESCE(TRIM(address), 'NO_ADDRESS') AS street_address,
        -- address2 DROPPED
        COALESCE(INITCAP(TRIM(city)), 'Boston') AS city,
        COALESCE(UPPER(TRIM(state)), 'MA') AS state,
        
        -- ZIP standardization (same logic as health inspections)
        CASE 
            WHEN zip_code IS NULL OR TRIM(zip_code) = '' THEN '00000'
            WHEN LENGTH(TRIM(zip_code)) = 4 THEN LPAD(TRIM(zip_code), 5, '0')
            WHEN LENGTH(TRIM(zip_code)) = 10 AND zip_code LIKE '%-%' THEN LEFT(zip_code, 5)
            WHEN REGEXP_LIKE(TRIM(zip_code), '^[0-9]{5}$') THEN TRIM(zip_code)
            ELSE '99999'
        END AS postal_code,
        
        COALESCE(NULLIF(TRIM(neighborhood), ''), 'UNKNOWN') AS neighborhood,
        
        -- Full address construction (without address2)
        CONCAT_WS(', ', 
            COALESCE(TRIM(address), 'NO_ADDRESS'),
            COALESCE(INITCAP(TRIM(city)), 'Boston'), 
            CONCAT(COALESCE(UPPER(TRIM(state)), 'MA'), ' ', 
                CASE 
                    WHEN zip_code IS NULL OR TRIM(zip_code) = '' THEN '00000'
                    WHEN LENGTH(TRIM(zip_code)) = 4 THEN LPAD(TRIM(zip_code), 5, '0')
                    WHEN LENGTH(TRIM(zip_code)) = 10 AND zip_code LIKE '%-%' THEN LEFT(zip_code, 5)
                    WHEN REGEXP_LIKE(TRIM(zip_code), '^[0-9]{5}$') THEN TRIM(zip_code)
                    ELSE '99999'
                END
            )
        ) AS full_address_formatted,
        
        -- Location (keeping original names)
        latitude,
        longitude,
        
        -- Categories
        COALESCE(primary_cuisine, SPLIT_PART(category_aliases, ',', 1), 'UNKNOWN') AS primary_cuisine,
        COALESCE(category_aliases, '') AS category_aliases,
        COALESCE(category_titles, '') AS category_titles,
        
        -- Ratings & Reviews
        COALESCE(yelp_rating, 0.0) AS yelp_rating,
        COALESCE(yelp_review_count, 0) AS yelp_review_count,
        
        -- Price & Status
        COALESCE(price_tier, 'NO_PRICE') AS price_tier,
        CASE 
            WHEN price_tier = '$' THEN 1
            WHEN price_tier = '$$' THEN 2
            WHEN price_tier = '$$$' THEN 3
            WHEN price_tier = '$$$$' THEN 4
            ELSE 0
        END AS price_level,
        COALESCE(is_closed, FALSE) AS is_closed,
        
        -- Metadata
        api_key_used,
        search_location,
        loaded_at,
        updated_at,
        CURRENT_TIMESTAMP() AS staging_processed_at
        
    FROM deduped
    WHERE rn = 1  -- Keep only most recent version of each restaurant
        AND restaurant_id IS NOT NULL
        AND name IS NOT NULL
        AND latitude IS NOT NULL
        AND longitude IS NOT NULL
        AND latitude BETWEEN 41.5 AND 43.0  -- Boston area bounds
        AND longitude BETWEEN -72.0 AND -70.0
)

SELECT * FROM cleaned