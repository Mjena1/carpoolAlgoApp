import streamlit as st
import math
from typing import Dict, List, Tuple,Union
import requests
import polyline

from dotenv import load_dotenv
import os

load_dotenv()

api_key = st.secrets['api_key']

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
    legs = directions['routes'][0]['legs'][0]
    distance = legs['distance']['text']
    polyline_str = directions['routes'][0]['overview_polyline']['points']
    decoded_points = polyline.decode(polyline_str)
    return decoded_points, float(distance.split()[0])

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

def get_eta_waypoints(origin, destination, way_points, api_key):
    url = "https://maps.googleapis.com/maps/api/directions/json"
    waypoints_str = "|".join([f"{lat},{lon}" for lat, lon in way_points])
    params = {
        'origin': origin,
        'destination': destination,
        'key': api_key,
        'waypoints' : waypoints_str
    }
    response = requests.get(url, params=params)
    # return response['legs']['duration']['text']
    if response.status_code == 200:
        data = response.json()
        
        if data['status'] == 'OK':
            # Extract duration for each leg
            legs = data['routes'][0]['legs']
            durations = [leg['duration']['text'] for leg in legs]
            # total_duration_seconds = sum(leg['duration']['value'] for leg in legs)  # in seconds
            
            # Return the list of durations and total duration in a readable format
            return durations    # total duration in minutes
        else:
            print(f"Error in response: {data['status']}")
            return None, None
    else:
        print(f"Request failed with status code: {response.status_code}")
        return None, None

#***********************************Helper Functions************************************************************
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

def find_best_paths(locations) -> Dict[str, List[Tuple[Tuple[float, float], float]]]:
    """Compute the shortest paths from drivers to the office based on travel time."""
    office_location = locations['office']
    
    paths = {}
    
    for label, place in locations['drivers'].items():
        path = get_directions(office_location, place, api_key)
        paths[label] = path
        # if label.startswith('driver'):
        #     try:
                
        #     except nx.NetworkXNoPath:
        #         paths[label] = []  # No path found
    
    return paths

'''while going to office, our algo will only consider one companion, im considering companion_lat_lons will only contain one companion'''
def calculate_driver_companion_distances(        
    # driver_paths: List[Tuple[Tuple[float, float], float]],  #path is like a dictionary
    driver_paths: Dict[str, List[Tuple[Tuple[float, float], float]]],
    companion_lat_lons: Dict[str, Tuple[float, float]]
) -> Dict[Tuple[str, str, Tuple[float, float]], List[Tuple[Tuple[float, float], float]]]:
    """Calculate the top 5 closest nodes for each driver-companion pair based on aerial distance."""
    aerial_distances = {}
    
    for driver_label, (path, _ ) in driver_paths.items():
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

def find_best_intersection_node(      #doesn't need driver_paths
    driver_paths: List[Tuple[Tuple[float, float], float]],
    companion_lat_lons: Dict[str, Tuple[float, float]],
    aerial_distances: Dict[Tuple[str, str, Tuple[float, float]], List[Tuple[Tuple[float, float], float]]]
) -> Dict[Tuple[str, str], Tuple[float, float, int]]:
    """Find the best intersection node among the top 5 nodes for each driver-companion pair."""
    road_distances = {}
    
    for (driver_label, companion_name, companion_lat_lon), top_5_nodes in aerial_distances.items():
        shortest_road_distance = float('inf')
        shortest_road_time = float('inf')
        best_intersection_lat_lon = None
        
        for lat_lon, _ in top_5_nodes:
           
            road_distance_from_intersection, travel_time_from_intersection = get_directions_companion(api_key, lat_lon, companion_lat_lon)

            if (road_distance_from_intersection < shortest_road_distance):
                shortest_road_distance = road_distance_from_intersection
                shortest_road_time = travel_time_from_intersection
                best_intersection_lat_lon = lat_lon
        
        road_distances[(driver_label, companion_name)] = (shortest_road_distance, shortest_road_time, best_intersection_lat_lon) # here i need to handle for multiple companions

    return road_distances

def get_neighboring_lat_lons(road_distances, driver_paths):
    neighboring_lat_lons = {}
    for (driver, companion), (short_dist, short_time, intersection) in road_distances.items():
        path = driver_paths[driver][0]
        distance = driver_paths[driver][1]
   
        avg_adj_lat_lon_dist = distance / len(path)
        no_nodes = int(0.5 // avg_adj_lat_lon_dist)
        lat_lon_idx = 0

        for i in range(len(driver_paths[driver][0])):
            if i == intersection:
                lat_lon_idx = i
                break
  
        neighboring_lat_lon_list = [intersection]
        
        if lat_lon_idx - (2 * no_nodes) >= 0:
            neighboring_lat_lon_list.append(driver_paths[driver][0][lat_lon_idx - (2 * no_nodes)])
        if lat_lon_idx - no_nodes >= 0:
            neighboring_lat_lon_list.append(driver_paths[driver][0][lat_lon_idx - no_nodes])
        if lat_lon_idx + (2 * no_nodes) < len(driver_paths[driver][0]):
            neighboring_lat_lon_list.append(driver_paths[driver][0][lat_lon_idx + (2 * no_nodes)])
        if lat_lon_idx + no_nodes < len(driver_paths[driver][0]):
            neighboring_lat_lon_list.append(driver_paths[driver][0][lat_lon_idx + no_nodes])

        neighboring_lat_lons[(driver, companion)] = neighboring_lat_lon_list

    return neighboring_lat_lons

def assign_driver_companion(road_distances, driver_capacity): # matching algo
    # all_distances_list = []
    # for (driver, companion), neighboring_nodes in neighboring_lat_lons.items():
    #     # times_driver = get_eta_waypoints(drivers[driver], office, neighboring_nodes, api_key) # i dont need times in this case ig
    #     # print(times_driver)

    #     for i, lat_lons in enumerate(neighboring_nodes):
    #         distance, duration = get_directions_companion(api_key, companion_lat_lon, lat_lons)
    #         if(times_driver[i] > duration):
    #             all_distances_list.append((driver, duration, distance))
    # print(all_distances_list)
    # final_out = all_distances_list[0]
    # if(len(all_distances_list) == 1):
    #     return final_out
    # for i in all_distances_list[1:]:
    #     if i[2] < final_out[2]:
    #         final_out = i
    #     elif i[2] == final_out[2]:
    #         if i[1] < final_out[1]:
    #             final_out = i
    
    # return final_out
    sorted_distances = sorted(road_distances.items(), key=lambda road_distances: road_distances[1][0])
    assignments = {driver : [] for driver in driver_capacity.keys()} # hardcoded driver capacity
    companion_assigned = set()

    for (driver, companion), (_, _, node) in sorted_distances:
        if len(assignments[driver]) < driver_capacity[driver] and companion not in companion_assigned:
            assignments[driver].append((companion, node))
            companion_assigned.add(companion)

    return assignments



##************************* Constants ******************************************************


#*******************************Main****************************************

def helper(locations: Dict[str, Union[str, Dict[str, str]]],capacity):
    # locations: Dict[str, Union[str, Dict[str, str]]],capacity
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
    companion_lat_lons = {name : get_lat_lon(companion_place, api_key) for name, companion_place in locations["companions"].items()}
    driver_paths = find_best_paths(locations)
    # print(driver_paths)
    # return
    # capacity = {
    #     'Driver A': 2,  # Driver A
    #     'Driver B': 2,  # Driver B
    # }


    aerial_distances = calculate_driver_companion_distances(driver_paths, companion_lat_lons)
    road_distances = find_best_intersection_node(driver_paths, companion_lat_lons, aerial_distances)
    # print(road_distances)
    print(capacity)
    # neighboring_lat_lons = get_neighboring_lat_lons(road_distances, driver_paths)
    assignments = assign_driver_companion(road_distances, capacity)
    driver_pth={}
    for key, (path,dist) in driver_paths.items():
        driver_pth[key]=path
    print(driver_pth)
    return (locations, assignments,driver_pth)

