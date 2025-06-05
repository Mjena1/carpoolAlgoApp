import folium
import requests
import os
from dotenv import load_dotenv
import polyline
import folium
from folium.plugins import BeautifyIcon, MarkerCluster
from branca.element import Template, MacroElement

# Load API Key from environment variables
load_dotenv()
api_key = os.getenv('api_key')

def get_lat_lon(address, api_key):
    """
    Geocodes an address to get latitude and longitude using Google Maps API.
    """
    url = "https://maps.googleapis.com/maps/api/geocode/json"
    params = {'address': address, 'key': api_key}
    response = requests.get(url, params=params)
    response.raise_for_status()
    result = response.json()
    location = result['results'][0]['geometry']['location']
    return (location['lat'], location['lng'])



def get_directions(origin, destination, api_key, mode='walking'):
    url = "https://maps.googleapis.com/maps/api/directions/json"

    # Convert (lat, lon) tuples to "latitude,longitude" strings
    origin_str = f"{origin[0]},{origin[1]}"
    destination_str = f"{destination[0]},{destination[1]}"

    params = {
        'origin': origin_str,
        'destination': destination_str,
        'key': api_key,
        'mode': mode
    }
    response = requests.get(url, params=params)
    
    directions = response.json()
    
    # Check for successful response and routes
    if directions['status'] == 'OK' and directions['routes']:
        polyline_str = directions['routes'][0]['overview_polyline']['points']
        decoded_points = polyline.decode(polyline_str)
        return decoded_points
    else:
        # Handle cases where no route is found or API call fails
        print(f"Error fetching directions: {directions['status']}")
        return None

def plot(locations, assignments, driver_paths):

    office_coords = get_lat_lon(locations["office"], api_key)
    companion_coords = {
        companion: get_lat_lon(address, api_key)
        for companion, address in locations["companions"].items()
    }

    mymap = folium.Map(location=office_coords, zoom_start=12, control_scale=True)

    # Add office marker
    folium.Marker(
        office_coords,
        popup="Office",
        tooltip="Office Location",
        icon=folium.Icon(color='red', icon='briefcase', prefix='fa')
    ).add_to(mymap)

    # Color palette
    colors = ['blue', 'green', 'purple', 'orange', 'darkred', 'cadetblue']

    # Plot driver paths
    for i, (driver, coords) in enumerate(driver_paths.items()):
        color = colors[i % len(colors)]
        folium.PolyLine(coords, color=color, weight=5, opacity=0.8, tooltip=f"{driver}'s Route").add_to(mymap)
        folium.Marker(
            coords[-1],
            popup=f"Driver: {driver}",
            tooltip=f"{driver} destination",
            icon=BeautifyIcon(icon_shape='marker', border_color=color, text_color=color, number=i+1)
        ).add_to(mymap)

    # Marker cluster for companions
    companion_cluster = MarkerCluster(name="Companions").add_to(mymap)

    # Plot companion paths and meeting points
    for driver, companion_list in assignments.items():
        for companion, meeting_point in companion_list:
            companion_coord = companion_coords[companion]
            path = get_directions(companion_coord, meeting_point, api_key)
            if path:
                folium.PolyLine(path, color='black', weight=3, opacity=0.6, dash_array='5').add_to(mymap)

            # Get distance and duration
            url = "https://maps.googleapis.com/maps/api/directions/json"
            params = {
                'origin': f"{companion_coord[0]},{companion_coord[1]}",
                'destination': f"{meeting_point[0]},{meeting_point[1]}",
                'key': api_key,
                'mode': 'driving'
            }
            response = requests.get(url, params=params).json()
            if response['status'] == 'OK':
                leg = response['routes'][0]['legs'][0]
                distance = leg['distance']['text']
                duration = leg['duration']['text']
                tooltip_text = f"{companion} → Meeting Point\n{distance}, {duration}"
            else:
                tooltip_text = f"{companion} → Meeting Point"

            folium.Marker(
                companion_coord,
                popup=f"Companion: {companion}",
                tooltip=f"{companion}'s destination",
                icon=folium.Icon(color='green', icon='user', prefix='fa')
            ).add_to(companion_cluster)

            folium.Marker(
                meeting_point,
                popup=f"Droping Point for {companion}",
                tooltip=tooltip_text,
                icon=folium.Icon(color='orange', icon='flag', prefix='fa')
            ).add_to(mymap)

    # Add layer control
    folium.LayerControl().add_to(mymap)

    # Add legend using HTML
    legend_html = """
    {% macro html(this, kwargs) %}
    <div style="
        position: fixed;
        bottom: 50px;
        left: 50px;
        width: 200px;
        height: 160px;
        z-index:9999;
        font-size:14px;
        background-color: white;
        border:2px solid grey;
        padding: 10px;
        box-shadow: 2px 2px 6px rgba(0,0,0,0.3);
    ">
        <b>Legend</b><br>
        <i class="fa fa-briefcase fa-1x" style="color:red"></i> Office<br>
        <i class="fa fa-user fa-1x" style="color:green"></i> Companion Destination<br>
        <i class="fa fa-flag fa-1x" style="color:orange"></i> Dropping Point<br>
        <i class="fa fa-car fa-1x" style="color:blue"></i> Driver Destination<br>
    </div>
    {% endmacro %}
    """
    legend = MacroElement()
    legend._template = Template(legend_html)
    mymap.get_root().add_child(legend)

    mymap.save('map.html')
    print("The paths have been plotted and saved to map.html.")
    return mymap
