import streamlit as st
import math
from typing import Dict, List, Tuple, Union, Any
import requests
import polyline
import os
from dotenv import load_dotenv

# --- Configuration & Constants ---
load_dotenv()
api_key = st.secrets['api_key']

# Default values for aerial distance calculation
EARTH_RADIUS_KM = 6371

# --- Google Maps API Functions ---

def get_directions(origin: str, destination: str, api_key: str) -> Tuple[List[Tuple[float, float]], float]:
    """
    Fetches driving directions between an origin and destination using the Google Directions API.

    Args:
        origin (str): The starting point (address or lat/lon string).
        destination (str): The ending point (address or lat/lon string).
        api_key (str): Your Google Maps API key.

    Returns:
        Tuple[List[Tuple[float, float]], float]: A tuple containing:
            - decoded_points (List[Tuple[float, float]]): A list of (latitude, longitude) tuples representing the polyline.
            - distance (float): The distance of the route in kilometers.

    Raises:
        requests.exceptions.RequestException: If the API request fails or times out.
        KeyError: If the API response status is not 'OK' or data is missing.
    """
    if not api_key:
        raise ValueError("Google Maps API Key is not set. Please set it in your .env file or Streamlit secrets.")

    url = "https://maps.googleapis.com/maps/api/directions/json"
    params = {
        'origin': origin,
        'destination': destination,
        'key': api_key
    }
    
    try:
        response = requests.get(url, params=params, timeout=10)
        response.raise_for_status()  # Raise HTTPError for bad responses (4xx or 5xx)
        directions = response.json()

        if directions['status'] == 'OK' and directions['routes']:
            legs = directions['routes'][0]['legs'][0]
            distance_text = legs['distance']['text']
            polyline_str = directions['routes'][0]['overview_polyline']['points']
            
            decoded_points = polyline.decode(polyline_str)
            distance_km = float(distance_text.replace(',', '').split()[0]) # Handle commas in distance text

            return decoded_points, distance_km
        else:
            error_msg = directions.get('error_message', 'No routes found or unknown API error.')
            raise KeyError(f"Directions API Error: Status - {directions.get('status', 'N/A')}. Message: {error_msg}")
    except requests.exceptions.Timeout:
        raise requests.exceptions.Timeout("Directions API request timed out. Please check your internet connection or try again.")
    except requests.exceptions.RequestException as e:
        raise requests.exceptions.RequestException(f"Failed to connect to Google Directions API: {e}. Check network and API key.")


def get_lat_lon(address: str, api_key: str) -> Tuple[float, float]:
    """
    Converts an address to latitude and longitude using Google Geocoding API.

    Args:
        address (str): The address string.
        api_key (str): Your Google Maps API key.

    Returns:
        Tuple[float, float]: A tuple containing (latitude, longitude).

    Raises:
        requests.exceptions.RequestException: If the API request fails or times out.
        KeyError: If the address cannot be geocoded or API response is not 'OK'.
    """
    if not api_key:
        raise ValueError("Google Maps API Key is not set. Please set it in your .env file or Streamlit secrets.")

    url = "https://maps.googleapis.com/maps/api/geocode/json"
    params = {
        'address': address,
        'key': api_key
    }
    
    try:
        response = requests.get(url, params=params, timeout=10)
        response.raise_for_status()  # Raise HTTPError for bad responses (4xx or 5xx)
        result = response.json()

        if result['status'] == 'OK' and result['results']:
            location = result['results'][0]['geometry']['location']
            return (location['lat'], location['lng'])
        elif result['status'] == 'ZERO_RESULTS':
            raise KeyError(f"No results found for address: '{address}'. Please try a more specific address.")
        else:
            error_msg = result.get('error_message', 'Unknown geocoding error.')
            raise KeyError(f"Could not geocode address: '{address}'. Status: {result['status']}. Message: {error_msg}")
    except requests.exceptions.Timeout:
        raise requests.exceptions.Timeout("Geocoding API request timed out. Please check your internet connection or try again.")
    except requests.exceptions.RequestException as e:
        raise requests.exceptions.RequestException(f"Failed to connect to Google Geocoding API: {e}. Check network and API key.")


def get_directions_companion(api_key: str, origin: Tuple[float, float], destination: Tuple[float, float], mode: str = 'walking') -> Tuple[Union[float, str], Union[str, None]]:
    """
    Fetches walking directions (distance and duration) between two lat/lon points.

    Args:
        api_key (str): Your Google Maps API key.
        origin (Tuple[float, float]): The starting point as (latitude, longitude).
        destination (Tuple[float, float]): The ending point as (latitude, longitude).
        mode (str): Travel mode (e.g., 'walking', 'driving', 'bicycling', 'transit'). Defaults to 'walking'.

    Returns:
        Tuple[Union[float, str], Union[str, None]]: A tuple containing:
            - distance (float or str): The distance in kilometers (float) if successful, or status string if not 'OK'.
            - duration (str or None): The duration text (e.g., '5 mins') or None if no route found.

    Raises:
        requests.exceptions.RequestException: If the API request fails or times out.
        KeyError: If the API response status is not 'OK' or data is missing.
    """
    if not api_key:
        raise ValueError("Google Maps API Key is not set. Please set it in your .env file or Streamlit secrets.")

    url = "https://maps.googleapis.com/maps/api/directions/json"
    params = {
        'origin': f"{origin[0]},{origin[1]}",
        'destination': f"{destination[0]},{destination[1]}",
        'mode': mode,
        'key': api_key
    }

    try:
        response = requests.get(url, params=params, timeout=10)
        response.raise_for_status()
        data = response.json()

        if data['status'] == 'OK' and data['routes']:
            legs = data['routes'][0]['legs'][0]
            distance_km = float(legs['distance']['text'].replace(',', '').split()[0])
            duration_text = legs['duration']['text']
            return distance_km, duration_text
        else:
            error_msg = data.get('error_message', 'No route found or unknown API error.')
            raise KeyError(f"Companion Directions API Error: Status - {data.get('status', 'N/A')}. Message: {error_msg}")
    except requests.exceptions.Timeout:
        raise requests.exceptions.Timeout("Companion Directions API request timed out. Please check your internet connection or try again.")
    except requests.exceptions.RequestException as e:
        raise requests.exceptions.RequestException(f"Failed to connect to Google Directions API for companion: {e}. Check network and API key.")


def get_eta_waypoints(origin: Union[str, Tuple[float, float]], destination: Union[str, Tuple[float, float]], way_points: List[Tuple[float, float]], api_key: str) -> List[str]:
    """
    Fetches travel durations for a route with specified waypoints using the Google Directions API.

    Args:
        origin (Union[str, Tuple[float, float]]): The starting point (address string or lat/lon tuple).
        destination (Union[str, Tuple[float, float]]): The ending point (address string or lat/lon tuple).
        way_points (List[Tuple[float, float]]): A list of (latitude, longitude) tuples to use as waypoints.
        api_key (str): Your Google Maps API key.

    Returns:
        List[str]: A list of duration strings for each leg of the journey.

    Raises:
        requests.exceptions.RequestException: If the API request fails or times out.
        KeyError: If the API response status is not 'OK' or data is missing.
    """
    if not api_key:
        raise ValueError("Google Maps API Key is not set. Please set it in your .env file or Streamlit secrets.")

    url = "https://maps.googleapis.com/maps/api/directions/json"
    
    # Format origin/destination for the API call
    if isinstance(origin, tuple):
        origin_str = f"{origin[0]},{origin[1]}"
    else:
        origin_str = origin

    if isinstance(destination, tuple):
        destination_str = f"{destination[0]},{destination[1]}"
    else:
        destination_str = destination

    waypoints_str = "|".join([f"{lat},{lon}" for lat, lon in way_points])
    
    params = {
        'origin': origin_str,
        'destination': destination_str,
        'key': api_key,
        'waypoints': waypoints_str
    }

    try:
        response = requests.get(url, params=params, timeout=10)
        response.raise_for_status()
        data = response.json()

        if data['status'] == 'OK' and data['routes']:
            legs = data['routes'][0]['legs']
            durations = [leg['duration']['text'] for leg in legs]
            return durations
        else:
            error_msg = data.get('error_message', 'No routes found with waypoints or unknown API error.')
            raise KeyError(f"ETA Waypoints API Error: Status - {data.get('status', 'N/A')}. Message: {error_msg}")
    except requests.exceptions.Timeout:
        raise requests.exceptions.Timeout("ETA Waypoints API request timed out. Please check your internet connection or try again.")
    except requests.exceptions.RequestException as e:
        raise requests.exceptions.RequestException(f"Failed to connect to Google Directions API for waypoints: {e}. Check network and API key.")


# --- Helper Functions (Core Logic) ---

def _deg2rad(deg: float) -> float:
    """Converts degrees to radians."""
    return deg * (math.pi / 180)

def calculate_aerial_distance(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """
    Computes the great-circle distance (aerial distance) between two
    latitude-longitude points using the Haversine formula.

    Args:
        lat1 (float): Latitude of the first point.
        lon1 (float): Longitude of the first point.
        lat2 (float): Latitude of the second point.
        lon2 (float): Longitude of the second point.

    Returns:
        float: The distance between the two points in kilometers.
    """
    dLat = _deg2rad(lat2 - lat1)
    dLon = _deg2rad(lon2 - lon1)
    
    a = (math.sin(dLat / 2) ** 2 +
         math.cos(_deg2rad(lat1)) * math.cos(_deg2rad(lat2)) *
         math.sin(dLon / 2) ** 2)
    
    c = 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))
    return EARTH_RADIUS_KM * c


def find_driver_to_office_paths(locations: Dict[str, Union[str, Dict[str, str]]], api_key: str) -> Dict[str, Tuple[List[Tuple[float, float]], float]]:
    """
    Computes the shortest driving paths for each driver from their starting location
    to the office.

    Args:
        locations (Dict[str, Union[str, Dict[str, str]]]): A dictionary containing:
            - 'office' (str): The office address.
            - 'drivers' (Dict[str, str]): A dictionary of driver names to their addresses.
        api_key (str): Your Google Maps API key.

    Returns:
        Dict[str, Tuple[List[Tuple[float, float]], float]]: A dictionary where keys are driver names
        and values are tuples containing:
            - A list of (latitude, longitude) tuples representing the driver's path polyline.
            - The distance of the driver's path in kilometers.
    """
    office_location = locations['office']
    driver_paths = {}
    
    for driver_name, driver_location in locations['drivers'].items():
        try:
            path_polyline, distance_km = get_directions(driver_location, office_location, api_key)
            driver_paths[driver_name] = (path_polyline, distance_km)
        except (requests.exceptions.RequestException, KeyError) as e:
            print(f"Warning: Could not get path for driver '{driver_name}' from '{driver_location}' to office: {e}")
            driver_paths[driver_name] = ([], 0.0) # Assign empty path and 0 distance on failure
    
    return driver_paths


def calculate_driver_companion_aerial_distances(
    driver_paths: Dict[str, Tuple[List[Tuple[float, float]], float]],
    companion_lat_lons: Dict[str, Tuple[float, float]]
) -> Dict[Tuple[str, str, Tuple[float, float]], List[Tuple[Tuple[float, float], float]]]:
    """
    Calculates the aerial distance between each companion's location and the 
    top 5 closest nodes on each driver's path to the office.

    Args:
        driver_paths (Dict[str, Tuple[List[Tuple[float, float]], float]]): 
            Driver paths with polyline points and distances.
        companion_lat_lons (Dict[str, Tuple[float, float]]): 
            A dictionary of companion names to their (latitude, longitude) tuples.

    Returns:
        Dict[Tuple[str, str, Tuple[float, float]], List[Tuple[Tuple[float, float], float]]]:
        A nested dictionary where keys are (driver_name, companion_name, companion_lat_lon) tuples,
        and values are lists of (path_node_lat_lon, aerial_distance_to_companion) for the top 5
        closest path nodes.
    """
    aerial_distances = {}
    
    for driver_name, (path_polyline, _) in driver_paths.items():
        if not path_polyline:
            continue # Skip if driver has no valid path
        
        for companion_name, companion_lat_lon in companion_lat_lons.items():
            distances_to_path_nodes = []
            for path_node_lat_lon in path_polyline:
                distance = calculate_aerial_distance(
                    companion_lat_lon[0], companion_lat_lon[1], 
                    path_node_lat_lon[0], path_node_lat_lon[1]
                )
                distances_to_path_nodes.append((path_node_lat_lon, distance))
            
            # Sort and get top 5 closest nodes
            top_5_nodes = sorted(distances_to_path_nodes, key=lambda x: x[1])[:5]
            aerial_distances[(driver_name, companion_name, companion_lat_lon)] = top_5_nodes
    
    return aerial_distances


def find_best_intersection_node_for_pickup(
    aerial_distances: Dict[Tuple[str, str, Tuple[float, float]], List[Tuple[Tuple[float, float], float]]]
) -> Dict[Tuple[str, str], Tuple[float, str, Tuple[float, float]]]:
    """
    Finds the best intersection node on a driver's path for each driver-companion pair
    based on the shortest *road* distance between the companion and the path node.

    Args:
        aerial_distances (Dict): Output from `calculate_driver_companion_aerial_distances`.

    Returns:
        Dict[Tuple[str, str], Tuple[float, str, Tuple[float, float]]]: A dictionary where keys
        are (driver_name, companion_name) tuples, and values are tuples containing:
            - shortest_road_distance_km (float): The shortest road distance from companion to an intersection node.
            - travel_time_str (str): The travel time from companion to that intersection node.
            - best_intersection_lat_lon (Tuple[float, float]): The (lat, lon) of the best intersection node.
    """
    road_distances = {}
    
    for (driver_name, companion_name, companion_lat_lon), top_5_nodes in aerial_distances.items():
        shortest_road_distance = float('inf')
        shortest_road_time_str = "N/A"
        best_intersection_lat_lon = None
        
        for intersection_lat_lon, _ in top_5_nodes:
            try:
                current_road_distance, current_travel_time_str = get_directions_companion(
                    API_KEY, companion_lat_lon, intersection_lat_lon
                )

                # Assuming `get_directions_companion` returns a float for distance or an error string
                if isinstance(current_road_distance, float) and current_road_distance < shortest_road_distance:
                    shortest_road_distance = current_road_distance
                    shortest_road_time_str = current_travel_time_str
                    best_intersection_lat_lon = intersection_lat_lon
            except (requests.exceptions.RequestException, KeyError) as e:
                # Log or handle individual companion-node failures, but don't stop the whole process
                print(f"Warning: Could not get road directions for {companion_name} to node {intersection_lat_lon}: {e}")
                continue # Try next node

        if best_intersection_lat_lon: # Only add if a valid intersection was found
            road_distances[(driver_name, companion_name)] = (
                shortest_road_distance, shortest_road_time_str, best_intersection_lat_lon
            )
    
    return road_distances


def assign_drivers_to_companions(
    road_distances: Dict[Tuple[str, str], Tuple[float, str, Tuple[float, float]]],
    driver_capacities: Dict[str, int]
) -> Dict[str, List[Tuple[str, Tuple[float, float]]]]:
    """
    Assigns companions to drivers based on shortest road distance and driver capacity.

    Args:
        road_distances (Dict): Output from `find_best_intersection_node_for_pickup`.
        driver_capacities (Dict[str, int]): A dictionary of driver names to their maximum passenger capacity.

    Returns:
        Dict[str, List[Tuple[str, Tuple[float, float]]]]: A dictionary where keys are driver names
        and values are lists of (companion_name, best_intersection_lat_lon) tuples assigned to that driver.
    """
    # Sort potential assignments by the shortest road distance from companion to driver's path
    # This prioritizes companions who are easiest to pick up.
    sorted_potential_assignments = sorted(
        road_distances.items(), 
        key=lambda item: item[1][0] # Sort by shortest_road_distance_km
    )

    assignments: Dict[str, List[Tuple[str, Tuple[float, float]]]] = {driver: [] for driver in driver_capacities.keys()}
    companion_assigned = set()

    for (driver_name, companion_name), (_, _, best_intersection_node) in sorted_potential_assignments:
        if (len(assignments[driver_name]) < driver_capacities.get(driver_name, 0) and
            companion_name not in companion_assigned):
            
            assignments[driver_name].append((companion_name, best_intersection_node))
            companion_assigned.add(companion_name)
    
    return assignments


# --- Main Helper Function ---

def helper(
    locations: Dict[str, Union[str, Dict[str, str]]], 
    capacity: Dict[str, int]
) -> Tuple[Dict[str, Any], Dict[str, List[Tuple[str, Tuple[float, float]]]], Dict[str, List[Tuple[float, float]]]]:
    """
    Main helper function to orchestrate the carpooling optimization for "To Office" scenario.

    Args:
        locations (Dict[str, Union[str, Dict[str, str]]]): A dictionary containing:
            - 'office' (str): The office address.
            - 'drivers' (Dict[str, str]): A dictionary of driver names to their addresses.
            - 'companions' (Dict[str, str]): A dictionary of companion names to their addresses.
        capacity (Dict[str, int]): A dictionary of driver names to their car capacities.

    Returns:
        Tuple[Dict[str, Any], Dict[str, List[Tuple[str, Tuple[float, float]]]], Dict[str, List[Tuple[float, float]]]]:
        A tuple containing:
            - locations (Dict[str, Any]): The original locations dictionary, potentially with geocoded values.
            - assignments (Dict[str, List[Tuple[str, Tuple[float, float]]]]): Optimized carpooling assignments.
            - driver_polylines (Dict[str, List[Tuple[float, float]]]): Polylines for each driver's path.
    """
    # 1. Geocode companion locations
    companion_lat_lons: Dict[str, Tuple[float, float]] = {}
    for name, place in locations["companions"].items():
        try:
            companion_lat_lons[name] = get_lat_lon(place, API_KEY)
        except (requests.exceptions.RequestException, KeyError) as e:
            print(f"Error geocoding companion '{name}' at '{place}': {e}. Skipping this companion.")
            # Decide how to handle: skip, or assign a default invalid coordinate
            continue 

    # If no companions or geocoding failed for all, return empty results
    if not companion_lat_lons:
        print("No valid companion locations found after geocoding. Cannot run algorithm.")
        return locations, {}, {}

    # 2. Find optimal paths for each driver to the office
    driver_paths = find_driver_to_office_paths(locations, API_KEY)
    
    # Extract just the polylines for the final output
    driver_polylines: Dict[str, List[Tuple[float, float]]] = {
        driver: path_data[0] for driver, path_data in driver_paths.items()
    }

    # 3. Calculate aerial distances between companions and driver paths
    aerial_distances = calculate_driver_companion_aerial_distances(driver_paths, companion_lat_lons)
    
    # 4. Find the best road intersection nodes for pickups
    road_distances_for_pickup = find_best_intersection_node_for_pickup(aerial_distances)

    # 5. Assign companions to drivers based on road distances and capacities
    assignments = assign_drivers_to_companions(road_distances_for_pickup, capacity)

    print("Driver Polylines:", driver_polylines)
    print("Assignments:", assignments)
    
    # Reformat locations to include geocoded companion data for plotting purposes
    # This ensures the `plotTo` module receives all necessary coordinates
    all_geocoded_locations = {
        "office": locations["office"], # Keep original string for office, as get_lat_lon is called inside plot functions
        "drivers": {name: get_lat_lon(loc, API_KEY) for name, loc in locations["drivers"].items()},
        "companions": companion_lat_lons # Use geocoded companion locations directly
    }

    return all_geocoded_locations, assignments, driver_polylines

########### Needed Things For debugging Urgently ################

#     locations = {                #in google maps, im assuming all the locations are in string format
#     "office": 'Brigade Tech Gardens, Bangalore',
#     "drivers": {
#         "Driver A": 'Kormangla, Bangalore',
#         "Driver B": 'Church Street, Bangalore',
        
#     },
#     "companions": {
#         "Companion 1": 'Hoodi Metro Station, Bangalore',
#         "Companion 2": 'Marathalli Bridge, Bangalore',
#         "Companion 3": 'Singayyanapalya Metro Station, Bangalore'
#     },
# }
    
# capacity = {
#     'Driver A': 2,  # Driver A
#     'Driver B': 2,  # Driver B
# }
