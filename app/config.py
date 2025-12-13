"""
Configuration and Constants for LocalEats AI
"""

# Snowflake table names
GOLD_RESTAURANT_EMBEDDINGS = "GOLD_RESTAURANT_EMBEDDINGS"
GOLD_RESTAURANTS_MASTER = "GOLD_RESTAURANTS_MASTER"
BRONZE_MBTA_STOPS = "BRONZE.BRONZE_MBTA_STOPS"
INT_RESTAURANT_TRANSIT = "DBT_SKASIREDDY_INTERMEDIATE.INT_RESTAURANT_TRANSIT_ACCESS"

# Cuisine keywords for detection
CUISINE_KEYWORDS = {
    'mexican': 'Mexican',
    'italian': 'Italian',
    'chinese': 'Chinese',
    'indian': 'Indian',
    'thai': 'Thai',
    'japanese': 'Japanese',
    'korean': 'Korean',
    'vietnamese': 'Vietnamese',
    'pizza': 'Pizza'
}

# Common typos and corrections
CUISINE_TYPOS = {
    'meican': 'mexican',
    'mexian': 'mexican',
    'itailan': 'italian',
    'itallian': 'italian',
    'chinease': 'chinese',
    'chineese': 'chinese',
    'thia': 'thai',
    'japenese': 'japanese',
    'japanes': 'japanese',
    'koren': 'korean',
    'vietnames': 'vietnamese'
}

# Invalid locations - use full city/state names to avoid false positives
INVALID_LOCATIONS = [
    'alaska', 'seattle', 'portland oregon', 'new york city', 'new york', 'nyc', 
    'chicago', 'los angeles', 'san francisco', 'miami', 'texas',
    'california', 'florida', 'washington state'
]

# Restaurant-related keywords - ADD cafe/coffee
RESTAURANT_KEYWORDS = [
    'food', 'restaurant', 'eat', 'dining', 'dinner', 'lunch', 'breakfast',
    'cuisine', 'mexican', 'italian', 'chinese', 'thai', 'indian', 'pizza',
    'burger', 'sushi', 'cafe', 'coffee', 'vegan', 'vegetarian',
    'place', 'spot', 'friendly'  # Added these
]
# Known Boston locations with coordinates
QUICK_LOCATIONS = {
    "MIT": {"latitude": 42.3601, "longitude": -71.0942},
    "Harvard Square": {"latitude": 42.3736, "longitude": -71.1197},
    "Downtown Boston": {"latitude": 42.3601, "longitude": -71.0589},
    "Fenway Park": {"latitude": 42.3467, "longitude": -71.0972},
    "Jamaica Plain": {"latitude": 42.3099, "longitude": -71.1111}
}

# Boston neighborhoods for geocoding
BOSTON_NEIGHBORHOODS = {
    "jamaica plain": {"latitude": 42.3099, "longitude": -71.1111},
    "centre street": {"latitude": 42.3099, "longitude": -71.1111},
    "center street": {"latitude": 42.3099, "longitude": -71.1111},
    "roxbury": {"latitude": 42.3317, "longitude": -71.0828},
    "dorchester": {"latitude": 42.2876, "longitude": -71.0662},
    "south end": {"latitude": 42.3417, "longitude": -71.0719},
    "north end": {"latitude": 42.3647, "longitude": -71.0542},
    "back bay": {"latitude": 42.3503, "longitude": -71.0810},
    "allston": {"latitude": 42.3528, "longitude": -71.1319},
    "brighton": {"latitude": 42.3486, "longitude": -71.1656},
    "charlestown": {"latitude": 42.3782, "longitude": -71.0602},
    "cambridge": {"latitude": 42.3736, "longitude": -71.1097},
    "somerville": {"latitude": 42.3876, "longitude": -71.0995}
}

# Default coordinates (Boston)
DEFAULT_BOSTON_LAT = 42.3601
DEFAULT_BOSTON_LON = -71.0589

# Walking speed (meters per minute)
WALKING_SPEED_M_PER_MIN = 80

# Quality threshold for reviewer
QUALITY_THRESHOLD = 8