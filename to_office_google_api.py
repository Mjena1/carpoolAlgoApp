#This can handle only one companion
import math
from typing import Dict, List, Tuple,Union
import requests
import polyline

from dotenv import load_dotenv
import os

load_dotenv()

api_key = os.getenv('api_key')

#*********************************** Google Map Api Functions ***************************************
def get_directions(origin, destination, api_key):
    url = "https://maps.googleapis.com/maps/api/directions/json"
    params = {
        'origin': origin,
        'destination': destination,
        'key': api_key
    }
    response = requests.get(url, params=params)
    # return response.json()
    directions = response.json()
    # print(directions)
    polyline_str = directions['routes'][0]['overview_polyline']['points']
    decoded_points = polyline.decode(polyline_str)
    return decoded_points

def get_lat_lon(address, api_key):
    def geocode_address(address, api_key):
        url = "https://maps.googleapis.com/maps/api/geocode/json"
        params = {
            'address': address,
            'key': api_key
        }
        response = requests.get(url, params=params)
        return response.json()

    result = geocode_address(address, api_key)

    location = result['results'][0]['geometry']['location']
    lat_lon = (location['lat'], location['lng'])

    return lat_lon

def get_directions_companion(api_key, origin, destination, mode='walking'):
    url = f"https://maps.googleapis.com/maps/api/directions/json"

    params = {
        'origin': f"{origin[0]},{origin[1]}",         # Use lat/lon format or can be anything(ex: 'BTG' or (12.000, 77.8499))
        'destination': f"{destination[0]},{destination[1]}",  # Use lat/lon format
        'mode': mode,
        'key': api_key
    }
    response = requests.get(url, params=params)

    if response.status_code == 200:
        data = response.json()
        # return data
        # Check if any routes were found
        if data['status'] == 'OK':
            # Extract distance and duration
            legs = data['routes'][0]['legs'][0]
            distance = legs['distance']['text']
            duration = legs['duration']['text']

            return float(distance.split()[0]), duration
        else:
            return data['status'], None
    else:
        return 'Error', None

#*********************************** Helper Functions ***************************************
def calculate_aerial_distance(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """Compute the distance between two latitude-longitude points in kilometers."""
    R = 6371  # Radius of the Earth in kilometers
    dLat = deg2rad(lat2 - lat1)
    dLon = deg2rad(lon2 - lon1)
    a = math.sin(dLat / 2) ** 2 + math.cos(deg2rad(lat1)) * math.cos(deg2rad(lat2)) * math.sin(dLon / 2) ** 2
    c = 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))
    return R * c

def deg2rad(deg: float) -> float:
    """Convert degrees to radians."""
    return deg * (math.pi / 180)

def find_best_paths(locations) -> Dict[str, List[Tuple[float, float]]]:
    """Compute the shortest paths from drivers to the office based on travel time."""
    office_location = locations['office']
    
    paths = {}
    
    for label, place in locations['drivers'].items():

        # if label.startswith('driver'):
        # print(place)
        # print(office_location)
        path = get_directions(place, office_location, api_key)
        paths[label] = path
    

    return paths


def calculate_driver_companion_distances(
    driver_paths: Dict[str, List[Tuple[float, float]]],
    companion_lat_lons: Dict[str, Tuple[float, float]]
) -> Dict[Tuple[str, str, Tuple[float, float]], List[Tuple[Tuple[float, float], float]]]:
    """Calculate the top 5 closest nodes for each driver-companion pair based on aerial distance."""
    aerial_distances = {}
    
    for driver_label, path in driver_paths.items():
        if not path:
            continue
        for companion_name, companion_lat_lon in companion_lat_lons.items():
            distances = []
            for lat_lon in path:
                distance = calculate_aerial_distance(companion_lat_lon[0], companion_lat_lon[1], lat_lon[0], lat_lon[1])
                distances.append((lat_lon, distance))
            
            top_5_nodes = sorted(distances, key=lambda x: x[1])[:5]
            aerial_distances[(driver_label, companion_name, companion_lat_lon)] = top_5_nodes
    
    return aerial_distances

def find_best_intersection_node(
    driver_paths: Dict[str, List[Tuple[float, float]]],
    companion_lat_lons: Dict[str, Tuple[float, float]],
    aerial_distances: Dict[Tuple[str, str, Tuple[float, float]], List[Tuple[Tuple[float, float], float]]]
) -> Dict[Tuple[str, str], Tuple[float, float, int]]:
    """Find the best intersection node among the top 5 nodes for each driver-companion pair."""
    road_distances = {}
    buffer_time = 5
    
    for (driver_label, companion_name, companion_lat_lon), top_5_nodes in aerial_distances.items():
        shortest_road_distance = float('inf')
        shortest_road_time = float('inf')
        best_intersection_lat_lon = None

        
        for lat_lon, _ in top_5_nodes:
           

            road_distance_companion_intersection, travel_time_companion_intersection = get_directions_companion(api_key, companion_lat_lon, lat_lon,mode="driving")
            road_distance_driver_intersection, travel_time_driver_intersection = get_directions_companion(api_key,driver_paths[driver_label][0], lat_lon,mode="driving")
            # print(travel_time_companion_intersection)

            if (road_distance_companion_intersection < shortest_road_distance and int(travel_time_companion_intersection.split()[0]) <= int(travel_time_driver_intersection.split()[0]) + buffer_time):
                shortest_road_distance = road_distance_companion_intersection
                shortest_road_time = travel_time_companion_intersection
                best_intersection_lat_lon = lat_lon
        
        road_distances[(driver_label, companion_name)] = (shortest_road_distance, shortest_road_time, best_intersection_lat_lon)
    
    return road_distances

#*********************************** Helper Functions ***************************************

##************************* Constants ******************************************************

#************************* Constants ******************************************************

def helper( locations: Dict[str, Union[str, Dict[str, str]]])-> Tuple[Dict[str, Tuple[float, float]], Dict[str, Tuple[int, int]]]:

    companion_lat_lons = {name : get_lat_lon(companion_place, api_key) for name, companion_place in locations["companions"].items()}
    
    driver_paths = find_best_paths(locations)
    aerial_distances = calculate_driver_companion_distances(driver_paths, companion_lat_lons)
    driver_companion_distances = find_best_intersection_node(driver_paths, companion_lat_lons, aerial_distances)

    
    # Find the best driver-companion pairing
    best_driver = None
    best_distance = float('inf')
    best_intersection_node = None
    companions_name = None

    
    for (driver_label, companion_name), (distance, time, intersection) in driver_companion_distances.items():
        if distance < best_distance:
            best_distance = distance
            best_driver = driver_label
            best_intersection_node = intersection
            companion_name = companion_name
            
    print(driver_paths)
            
    return (locations, {best_driver: [(companion_name, best_intersection_node)]},driver_paths)




#     locations = {                #in google maps, im assuming all the locations are in string format
#     "office": 'Brigade Tech Gardens, Bangalore',
#     "drivers": {
#         "Driver A": 'Hoodi Metro Station, Bangalore',
#         "Driver B": 'Church Street, Bangalore',
#         "Driver C": 'Singayyanapalya Metro Station, Bangalore',
#         "Driver D": 'Marathalli Bridge, Bangalore'
#     },
#     "companions": {
#         "Companion 1": 'Kundalahalli Metro Station, Bangalore',
#         # 'Companion 2': 'Marathalli Bridge, Bangalore'

#     },
# }