"""
Utility functions for LocalEats AI
"""
# Import functions that don't have circular dependencies first
from .cortex_helper import call_cortex, display_agent_status
from .geo_utils import calculate_haversine_distance, geocode_location, format_transit_directions


# Import query processor functions separately to avoid circular imports
def get_query_processor_functions():
    """Lazy import to avoid circular dependencies"""
    from .query_processor import process_user_query, search_restaurant_by_name
    return process_user_query, search_restaurant_by_name

# For MBTA route, import separately
def get_mbta_route_function():
    """Lazy import for MBTA route"""
    from .geo_utils import get_mbta_route
    return get_mbta_route

# Export what's safe to import at module level
__all__ = [
    'call_cortex',
    'display_agent_status',
    'calculate_haversine_distance',
    'geocode_location',
    'format_transit_directions',
    'create_restaurant_map'
]