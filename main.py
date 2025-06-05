import streamlit as st
import folium
from streamlit_folium import st_folium
import requests
import os
from dotenv import load_dotenv
import time
import pandas as pd
from typing import Dict, Tuple, Any

# Assuming these are your custom modules for carpooling logic and plotting
# Make sure these files are present and contain the specified functions.
import to_office_google_api
import to_home_google_api
from plotTo import plot as plot_to_office
from plotFrom import plot as plot_from_office

# --- Configuration ---
load_dotenv()
# API_KEY = os.getenv('api_key')
# Fallback for Streamlit Cloud deployment if using secrets:
API_KEY = st.secrets['api_key'] # Make sure this matches your secret name

ADMIN_EMAIL = "admin@admin.com"
ADMIN_PASSWORD = "admin"

# Default locations for a better demo experience
DEFAULT_OFFICE_LOCATION = "Brigade Tech Gardens, Bangalore"

DEFAULT_TO_OFFICE_COMPANION = ("Manab", "Zolo Arena, Bangalore")
DEFAULT_TO_OFFICE_DRIVERS = [
    ("Sundar Sri", "Nallur Halli Metro Station, Bangalore", 3),
    ("Abhijit Balan", "Marathahalli Bridge, Bangalore", 2),
    ("Tarun Chintapalli", "Sarjapura, Bangalore", 2),
    ("Jay Gupta", "Indiranagar Metro station, Bangalore", 3),
    ("Kishore K", "HopeFarm, Bangalore", 2)
]

DEFAULT_FROM_OFFICE_COMPANIONS = [
    ("Manab", "Zolo Arena, Bangalore"),
    ("Rohith", "Munnekolal, Bangalore"),
    ("Sayan", "Kundalahalli Railway Station, Bangalore"),
    ("Aman", "DMart, Siddapura, Bangalore"),
    ("Hitesh", "EcoSpace, Bellandur, Bangalore")
]

DEFAULT_FROM_OFFICE_DRIVERS = [
    ("Sundar Sri", "Nallur Halli Metro Station, Bangalore", 3),
    ("Abhijit Balan", "Marathahalli Bridge, Bangalore", 2),
    ("Tarun Chintapalli", "Sarjapura, Bangalore", 2),
    ("Jay Gupta", "Indiranagar Metro station, Bangalore", 3),
    ("Kishore K", "HopeFarm, Bangalore", 2)
]

# --- UI Styling Functions ---

def set_custom_css():
    """Applies custom CSS for background gradient, button styling, and general aesthetics."""
    st.markdown(
        """
        <style>
        .stApp {
            background: linear-gradient(to right, #ece9e6, #ffffff); /* Light grey to white gradient */
        }
        h1, h2, h3, h4, h5, h6 {
            color: #2F4F4F; /* Dark Slate Gray */
            text-align: center;
        }
        .stButton>button {
            background-color: #4CAF50; /* Green */
            color: white;
            border-radius: 8px;
            padding: 10px 20px;
            font-size: 16px;
            font-weight: bold;
            transition: background-color 0.3s ease, transform 0.2s ease;
        }
        .stButton>button:hover {
            background-color: #45a049; /* Darker green on hover */
            transform: translateY(-2px);
        }
        /* Specific style for the "Start Algorithm" button to make it red */
        div[data-testid="stVerticalBlock"] .red-button > button {
            background-color: #FF4B4B; /* Red */
            color: white;
        }
        div[data-testid="stVerticalBlock"] .red-button > button:hover {
            background-color: #E03C3C; /* Darker red on hover */
        }
        .stTextInput>div>div>input {
            border-radius: 5px;
            border: 1px solid #ccc;
            padding: 8px;
        }
        .stSelectbox>div>div>div {
            border-radius: 5px;
            border: 1px solid #ccc;
            padding: 8px;
        }
        .stSlider .stSliderHandle {
            background-color: #4CAF50;
        }
        .stSlider .stSliderTrack {
            background-color: #ccc;
        }
        .stExpander div[data-testid="stExpanderDetails"] {
            background-color: #f0f2f6; /* Light grey for expander content */
            border-radius: 5px;
            padding: 15px;
            margin-top: 5px;
        }
        </style>
        """,
        unsafe_allow_html=True
    )

# --- Helper Functions ---

def get_lat_lon(address: str, api_key: str) -> Tuple[float, float]:
    """
    Converts an address to latitude and longitude using Google Geocoding API.
    """
    if not api_key:
        raise ValueError("Google Maps API Key is not set. Please set it in your .env file or Streamlit secrets.")

    url = "https://maps.googleapis.com/maps/api/geocode/json"
    params = {'address': address, 'key': api_key}
    
    try:
        response = requests.get(url, params=params, timeout=10) # Added timeout
        response.raise_for_status()  # Raise HTTPError for bad responses (4xx or 5xx)
        result = response.json()

        if result['status'] == 'OK':
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


def initialize_session_state():
    """Initializes all necessary session state variables for the app."""
    if "logged_in" not in st.session_state:
        st.session_state.logged_in = False
    if "demo_started" not in st.session_state:
        st.session_state.demo_started = False
    if "demo_choice" not in st.session_state:
        st.session_state.demo_choice = None
    if "show_results" not in st.session_state:
        st.session_state.show_results = False
    if "algorithm_output" not in st.session_state:
        st.session_state.algorithm_output = None
    
    # Initialize 'To Office' specific defaults
    if "companion_name" not in st.session_state:
        st.session_state.companion_name = DEFAULT_TO_OFFICE_COMPANION[0]
        st.session_state.companion_location = DEFAULT_TO_OFFICE_COMPANION[1]
        st.session_state.office_location_to = DEFAULT_OFFICE_LOCATION
        st.session_state.num_drivers_to = 2 # Default to showing 2 drivers initially
        for i, (name, loc, cap) in enumerate(DEFAULT_TO_OFFICE_DRIVERS):
            st.session_state[f'driver_{i+1}_name_to'] = name
            st.session_state[f'driver_{i+1}_location_to'] = loc
            st.session_state[f'driver_{i+1}_capacity_to'] = cap
    if "show_map_to" not in st.session_state:
        st.session_state.show_map_to = False

    # Initialize 'From Office' specific defaults
    if "num_companions_from" not in st.session_state:
        st.session_state.office_location_from = DEFAULT_OFFICE_LOCATION
        st.session_state.num_companions_from = 3 # Default to showing 3 companions
        st.session_state.num_drivers_from = 2 # Default to showing 2 drivers
        for i, (name, loc) in enumerate(DEFAULT_FROM_OFFICE_COMPANIONS):
            st.session_state[f'companion_{i+1}_name_from'] = name
            st.session_state[f'companion_{i+1}_location_from'] = loc
        for i, (name, loc, cap) in enumerate(DEFAULT_FROM_OFFICE_DRIVERS):
            st.session_state[f'driver_{i+1}_name_from'] = name
            st.session_state[f'driver_{i+1}_location_from'] = loc
            st.session_state[f'driver_{i+1}_capacity_from'] = cap
    if "show_map_from" not in st.session_state:
        st.session_state.show_map_from = False

def reset_to_office_fields():
    """Resets 'To Office' demo input fields to their default values."""
    st.session_state.companion_name = DEFAULT_TO_OFFICE_COMPANION[0]
    st.session_state.companion_location = DEFAULT_TO_OFFICE_COMPANION[1]
    st.session_state.office_location_to = DEFAULT_OFFICE_LOCATION
    st.session_state.num_drivers_to = 2
    st.session_state.show_map_to = False
    for i, (name, loc, cap) in enumerate(DEFAULT_TO_OFFICE_DRIVERS):
        st.session_state[f'driver_{i+1}_name_to'] = name
        st.session_state[f'driver_{i+1}_location_to'] = loc
        st.session_state[f'driver_{i+1}_capacity_to'] = cap

def reset_from_office_fields():
    """Resets 'From Office' demo input fields to their default values."""
    st.session_state.office_location_from = DEFAULT_OFFICE_LOCATION
    st.session_state.num_companions_from = 3
    st.session_state.num_drivers_from = 2
    st.session_state.show_map_from = False
    for i, (name, loc) in enumerate(DEFAULT_FROM_OFFICE_COMPANIONS):
        st.session_state[f'companion_{i+1}_name_from'] = name
        st.session_state[f'companion_{i+1}_location_from'] = loc
    for i, (name, loc, cap) in enumerate(DEFAULT_FROM_OFFICE_DRIVERS):
        st.session_state[f'driver_{i+1}_name_from'] = name
        st.session_state[f'driver_{i+1}_location_from'] = loc
        st.session_state[f'driver_{i+1}_capacity_from'] = cap

# --- Streamlit Page Functions ---

def login_page():
    """Displays the admin login page."""
    st.markdown("<h1 style='text-align: center; color: #36454F;'>🔐 Admin Login</h1>", unsafe_allow_html=True)
    st.markdown("<h3 style='text-align: center; color: #505050;'>Please enter your credentials to continue</h3>", unsafe_allow_html=True)

    st.markdown("<br>", unsafe_allow_html=True) # Add some space

    # Centered login form
    login_col1, login_col2, login_col3 = st.columns([1, 2, 1])
    with login_col2:
        with st.container(border=True):
            st.markdown("<h4 style='text-align: center; color: #4CAF50;'>Login Form</h4>", unsafe_allow_html=True)
            email = st.text_input("📧 Email", placeholder="admin@admin.com")
            password = st.text_input("🔒 Password", type="password", placeholder="Enter password")

            st.markdown("<br>", unsafe_allow_html=True)
            if st.button("➡️ Login", use_container_width=True):
                if email == ADMIN_EMAIL and password == ADMIN_PASSWORD:
                    st.session_state.logged_in = True
                    st.success("✅ Login successful!")
                    st.rerun()
                else:
                    st.error("❌ Invalid email or password")
    
    st.markdown("<br><br><br>", unsafe_allow_html=True) # Add more space at the bottom

def welcome_page():
    """Displays the welcome page after successful login."""
    st.markdown("<h1 style='text-align: center; color: #36454F;'>🎉 Welcome to the Carpooling Optimization Demo</h1>", unsafe_allow_html=True)
    st.markdown(f"<h3 style='text-align: center; color: #505050;'>Hello, **{ADMIN_EMAIL}**! You've successfully logged in.</h3>", unsafe_allow_html=True)

    st.markdown("---")
    st.container(border=True).info("""
        This interactive application demonstrates a sophisticated carpooling optimization algorithm.
        You can explore scenarios for daily commutes:
        
        * **➡️ To Office:** Optimize morning routes, matching companions with drivers heading to a central office location.
        * **⬅️ From Office:** Optimize evening routes, pairing companions with drivers going home from the office.
        
        Our goal is to reduce travel time, minimize carbon footprint, and enhance the carpooling experience!
    """)

    st.markdown("---")
    st.markdown("<h3 style='text-align: center; color: #4CAF50;'>Ready to Experience Efficient Carpooling?</h3>", unsafe_allow_html=True)
    st.markdown("<br>", unsafe_allow_html=True)
    
    # Centered and larger button
    btn_col1, btn_col2, btn_col3 = st.columns([1, 2, 1])
    with btn_col2:
        if st.button("🚀 Get Started with the Carpooling Demo", use_container_width=True):
            st.session_state.demo_started = True
            st.rerun()

    st.markdown("<br><br><br>", unsafe_allow_html=True)

def demo_start_choice_page():
    """Asks the user if they are ready to start the demo."""
    st.markdown("<h1 style='text-align: center; color: #36454F;'>🚗 Carpooling Demo Setup</h1>", unsafe_allow_html=True)
    st.markdown("<h3 style='text-align: center; color: #505050;'>Before we dive in, are you ready to configure a carpooling scenario?</h3>", unsafe_allow_html=True)

    st.markdown("<br>", unsafe_allow_html=True)
    st.container(border=True).info("""
        Choosing 'Yes' will take you to select the carpooling direction (To Office or From Office).
        If you select 'Not now', you'll return to the welcome screen.
    """)
    st.markdown("<br>", unsafe_allow_html=True)

    # Use columns to make buttons more prominent and centered
    col_yes, col_no = st.columns([1.5, 1.5]) # Make columns slightly wider
    with col_yes:
        if st.button("✅ Yes, Let's Go!", use_container_width=True):
            st.session_state.demo_choice = "choose_direction"
            st.rerun()
    with col_no:
        if st.button("❌ Not Now, Take Me Back", use_container_width=True):
            st.session_state.demo_started = False # Go back to the initial welcome screen
            st.rerun()
    
    st.markdown("<br><br><br>", unsafe_allow_html=True)


def choose_direction_page():
    """Allows the user to choose the carpooling direction."""
    st.markdown("<h1 style='text-align: center; color: #36454F;'>➡️⬅️ Select Carpooling Direction</h1>", unsafe_allow_html=True)
    st.markdown("<h3 style='text-align: center; color: #505050;'>Please choose the scenario you'd like to simulate:</h3>", unsafe_allow_html=True)

    st.markdown("<br>", unsafe_allow_html=True)
    st.container(border=True).info("""
        **To Office:** Simulates morning commutes where individuals from various locations need a ride to a common office.
        **From Office:** Simulates evening commutes where individuals from the office need a ride to their respective homes.
    """)
    st.markdown("<br>", unsafe_allow_html=True)

    col_to, col_from = st.columns(2)
    with col_to:
        if st.button("➡️ Carpooling To Office", use_container_width=True, help="Optimize routes for morning commute to office."):
            st.session_state.demo_choice = "to_office"
            st.session_state.show_results = False # Reset results view
            st.session_state.algorithm_output = None # Clear previous results
            st.rerun()
    with col_from:
        if st.button("⬅️ Carpooling From Office", use_container_width=True, help="Optimize routes for evening commute from office."):
            st.session_state.demo_choice = "from_office"
            st.session_state.show_results = False # Reset results view
            st.session_state.algorithm_output = None # Clear previous results
            st.rerun()

    st.markdown("---") # Visual separator
    navigation_buttons(back_target="start_choice") # Allow going back to demo start choice

def demo_to_office_page():
    """Interface for the 'To Office' carpooling demo."""
    # If results are available, display them and exit this function
    if st.session_state.show_results and st.session_state.algorithm_output:
        locations, assignments, driver_paths, total_time = st.session_state.algorithm_output
        display_results_to_office(locations, assignments, driver_paths, total_time)
        navigation_buttons(back_target="to_office") # Allow going back to input form
        return

    st.markdown("<h1 style='text-align: center; color: #36454F;'>🚗 Carpooling Demo - To Office</h1>", unsafe_allow_html=True)
    st.info("Configure the participants and the office destination for the morning commute. Details can be entered on the left, and the map will visualize locations on the right.")

    # Two main columns for inputs and map
    col_inputs, col_map = st.columns([1, 2]) # Adjusted ratio for better map prominence

    with col_inputs:
        with st.container(border=True):
            st.subheader("👤 Your Details (Companion)")
            st.session_state.companion_name = st.text_input(
                "Your Name", value=st.session_state.companion_name, key="to_companion_name", help="Enter your name."
            )
            st.session_state.companion_location = st.text_input(
                "Your Pickup Location", value=st.session_state.companion_location, key="to_companion_location", help="e.g., 'Zolo Arena, Bangalore'"
            )
        
        st.markdown("<br>", unsafe_allow_html=True) # Space between containers

        with st.container(border=True):
            st.subheader("🏢 Office Destination")
            st.session_state.office_location_to = st.text_input(
                "Office Address", value=st.session_state.office_location_to, key="to_office_location", help="e.g., 'Brigade Tech Gardens, Bangalore'"
            )
        
        st.markdown("<br>", unsafe_allow_html=True)

        with st.container(border=True):
            st.subheader("🚗 Available Drivers")
            st.session_state.num_drivers_to = st.slider(
                "Number of Drivers to Include", 1, 5, value=st.session_state.num_drivers_to, key="to_num_drivers", help="Select how many drivers you want to configure."
            )

            # Use st.expander for each driver's details to reduce visual clutter
            for i in range(1, st.session_state.num_drivers_to + 1):
                with st.expander(f"**Driver {i} Details**"):
                    st.session_state[f'driver_{i}_name_to'] = st.text_input(
                        f"Name", key=f'driver_{i}_name_input_to', value=st.session_state[f'driver_{i}_name_to'], help=f"Enter name for Driver {i}"
                    )
                    st.session_state[f'driver_{i}_location_to'] = st.text_input(
                        f"Location", key=f'driver_{i}_location_input_to', value=st.session_state[f'driver_{i}_location_to'], help=f"e.g., 'Marathahalli Bridge, Bangalore'"
                    )
                    st.session_state[f'driver_{i}_capacity_to'] = st.number_input(
                        f"Capacity (Seats available)", min_value=1, max_value=10, value=st.session_state[f'driver_{i}_capacity_to'], key=f'driver_{i}_capacity_input_to', help=f"Number of passengers Driver {i} can carry."
                    )
        
        st.markdown("---") # Separator before action buttons
        col_buttons_input = st.columns(2)
        with col_buttons_input[0]:
            if st.button("Reset All Inputs", key="reset_to_office", use_container_width=True, help="Clear all entered data and revert to defaults."):
                reset_to_office_fields()
                st.rerun()
        with col_buttons_input[1]:
            if st.button("Show/Update Map", key="update_map_to", use_container_width=True, help="Visualize the entered locations on the map."):
                st.session_state.show_map_to = True

    with col_map:
        with st.container(border=True):
            st.subheader("🗺️ Locations Overview Map")
            if st.session_state.show_map_to:
                try:
                    office_lat, office_lon = get_lat_lon(st.session_state.office_location_to, API_KEY)
                    companion_lat, companion_lon = get_lat_lon(st.session_state.companion_location, API_KEY)

                    all_points = [(office_lat, office_lon), (companion_lat, companion_lon)]
                    driver_locations_map = []

                    for i in range(1, st.session_state.num_drivers_to + 1):
                        driver_loc_str = st.session_state[f'driver_{i}_location_to']
                        if driver_loc_str:
                            driver_lat, driver_lon = get_lat_lon(driver_loc_str, API_KEY)
                            all_points.append((driver_lat, driver_lon))
                            driver_locations_map.append((driver_lat, driver_lon, st.session_state[f'driver_{i}_name_to']))
                    
                    if all_points:
                        min_lat = min(p[0] for p in all_points)
                        max_lat = max(p[0] for p in all_points)
                        min_lon = min(p[1] for p in all_points)
                        max_lon = max(p[1] for p in all_points)
                        
                        # Add a small buffer to the bounds for better visualization
                        lat_buffer = (max_lat - min_lat) * 0.15
                        lon_buffer = (max_lon - min_lon) * 0.15
                        
                        m = folium.Map(location=[(min_lat + max_lat) / 2, (min_lon + max_lon) / 2], zoom_start=12)
                        m.fit_bounds([[min_lat - lat_buffer, min_lon - lon_buffer], [max_lat + lat_buffer, max_lon + lon_buffer]])

                        folium.Marker([office_lat, office_lon], tooltip="Office (Destination)", icon=folium.Icon(color='blue', icon='briefcase')).add_to(m)
                        folium.Marker([companion_lat, companion_lon], tooltip=f"{st.session_state.companion_name} (Companion)", icon=folium.Icon(color='green', icon='user')).add_to(m)

                        for d_lat, d_lon, d_name in driver_locations_map:
                            folium.Marker([d_lat, d_lon], tooltip=f"{d_name} (Driver)", icon=folium.Icon(color='red', icon='car')).add_to(m)

                        st_folium(m, width=700, height=550) # Make map slightly larger
                    else:
                        st.warning("No valid locations entered to display on the map.")
                except Exception as e:
                    st.error(f"Error loading map: {e}. Please ensure all entered addresses are valid and your Google Maps API key is correct and enabled for Geocoding API.")
            else:
                st.info("Click 'Show/Update Map' on the left to visualize the entered locations.")
        
        st.markdown("<br>", unsafe_allow_html=True)
        # Start Algorithm Button - placed in map column for better grouping
        st.markdown("<div class='red-button' style='text-align: center;'>", unsafe_allow_html=True)
        if st.button("▶️ Start Carpooling Algorithm", key="start_algo_to_main", use_container_width=True, help="Run the optimization algorithm to find the best carpool assignments."):
            with st.spinner("Running the carpooling algorithm... This might take a moment."):
                locations = {
                    "office": st.session_state.office_location_to,
                    "drivers": {
                        st.session_state[f'driver_{i}_name_to']: st.session_state[f'driver_{i}_location_to']
                        for i in range(1, st.session_state.num_drivers_to + 1)
                        if st.session_state[f'driver_{i}_name_to'] and st.session_state[f'driver_{i}_location_to']
                    },
                    "companions": {
                        st.session_state.companion_name: st.session_state.companion_location
                    }
                }
                driver_capacities = {
                    st.session_state[f'driver_{i}_name_to']: st.session_state[f'driver_{i}_capacity_to']
                    for i in range(1, st.session_state.num_drivers_to + 1)
                    if st.session_state[f'driver_{i}_name_to']
                }

                try:
                    start_time = time.time()
                    # Assuming to_office_google_api.helper expects locations and capacities
                    geocoded_locs, assignments, driver_paths = to_office_google_api.helper(locations)
                    end_time = time.time()
                    total_time = end_time - start_time

                    st.session_state.algorithm_output = (geocoded_locs, assignments, driver_paths, total_time)
                    st.session_state.show_results = True
                    st.success("Algorithm completed successfully! Navigating to results...")
                    time.sleep(1) # Small delay for success message to be seen
                    st.rerun()

                except requests.exceptions.RequestException as req_err:
                    st.error(f"Network or API request error: {req_err}. Please check your internet connection or Google Maps API key settings.")
                except KeyError as ke_err:
                    st.error(f"Location input error: {ke_err}. One or more addresses could not be geocoded. Please verify the entered addresses.")
                except Exception as e:
                    st.error(f"An unexpected error occurred during algorithm execution: {e}. Please report this issue.")
                st.session_state.show_results = False # Keep results hidden on error
        st.markdown("</div>", unsafe_allow_html=True) # End centering div

    st.markdown("---") # Final separator before navigation
    navigation_buttons(back_target="choose_direction") # Navigation at the very bottom


def demo_from_office_page():
    """Interface for the 'From Office' carpooling demo."""
    # If results are available, display them and exit this function
    if st.session_state.show_results and st.session_state.algorithm_output:
        locations, assignments, driver_paths, total_time = st.session_state.algorithm_output
        display_results_from_office(locations, assignments, driver_paths, total_time)
        navigation_buttons(back_target="from_office") # Allow going back to input form
        return

    st.markdown("<h1 style='text-align: center; color: #36454F;'>🚗 Carpooling Demo - From Office</h1>", unsafe_allow_html=True)
    st.info("Configure the office departure point and the participants for the evening commute. Details can be entered on the left, and the map will visualize locations on the right.")

    # Two main columns for inputs and map
    col_inputs, col_map = st.columns([1, 2]) # Adjusted ratio for better map prominence

    with col_inputs:
        with st.container(border=True):
            st.subheader("🏢 Office Departure Point")
            st.session_state.office_location_from = st.text_input(
                "Office Address", value=st.session_state.office_location_from, key="from_office_location", help="e.g., 'Brigade Tech Gardens, Bangalore'"
            )
        
        st.markdown("<br>", unsafe_allow_html=True)

        with st.container(border=True):
            st.subheader("👥 Companions Going Home")
            st.session_state.num_companions_from = st.slider(
                "Number of Companions to Include", 1, 5, value=st.session_state.num_companions_from, key="from_num_companions", help="Select how many companions are seeking a ride."
            )
            for i in range(1, st.session_state.num_companions_from + 1):
                with st.expander(f"**Companion {i} Details**"):
                    st.session_state[f'companion_{i}_name_from'] = st.text_input(
                        f"Name", key=f'companion_{i}_name_input_from', value=st.session_state[f'companion_{i}_name_from'], help=f"Enter name for Companion {i}"
                    )
                    st.session_state[f'companion_{i}_location_from'] = st.text_input(
                        f"Drop-off Location", key=f'companion_{i}_location_input_from', value=st.session_state[f'companion_{i}_location_from'], help=f"e.g., 'Zolo Arena, Bangalore'"
                    )
        
        st.markdown("<br>", unsafe_allow_html=True)

        with st.container(border=True):
            st.subheader("🚗 Available Drivers")
            st.session_state.num_drivers_from = st.slider(
                "Number of Drivers to Include", 1, 5, value=st.session_state.num_drivers_from, key="from_num_drivers", help="Select how many drivers are available."
            )
            for i in range(1, st.session_state.num_drivers_from + 1):
                with st.expander(f"**Driver {i} Details**"):
                    st.session_state[f'driver_{i}_name_from'] = st.text_input(
                        f"Name", key=f'driver_{i}_name_input_from', value=st.session_state[f'driver_{i}_name_from'], help=f"Enter name for Driver {i}"
                    )
                    st.session_state[f'driver_{i}_location_from'] = st.text_input(
                        f"Home Location", key=f'driver_{i}_location_input_from', value=st.session_state[f'driver_{i}_location_from'], help=f"e.g., 'Nallur Halli Metro Station, Bangalore'"
                    )
                    st.session_state[f'driver_{i}_capacity_from'] = st.number_input(
                        f"Capacity (Seats available)", min_value=1, max_value=10, value=st.session_state[f'driver_{i}_capacity_from'], key=f'driver_{i}_capacity_input_from', help=f"Number of passengers Driver {i} can carry."
                    )
        
        st.markdown("---")
        col_buttons_input = st.columns(2)
        with col_buttons_input[0]:
            if st.button("Reset All Inputs", key="reset_from_office", use_container_width=True, help="Clear all entered data and revert to defaults."):
                reset_from_office_fields()
                st.rerun()
        with col_buttons_input[1]:
            if st.button("Show/Update Map", key="update_map_from", use_container_width=True, help="Visualize the entered locations on the map."):
                st.session_state.show_map_from = True

    with col_map:
        with st.container(border=True):
            st.subheader("🗺️ Locations Overview Map")
            if st.session_state.show_map_from:
                try:
                    office_lat, office_lon = get_lat_lon(st.session_state.office_location_from, API_KEY)
                    all_points = [(office_lat, office_lon)]
                    
                    companion_locations_map = []
                    for i in range(1, st.session_state.num_companions_from + 1):
                        companion_loc_str = st.session_state[f'companion_{i}_location_from']
                        if companion_loc_str:
                            lat, lon = get_lat_lon(companion_loc_str, API_KEY)
                            all_points.append((lat, lon))
                            companion_locations_map.append((lat, lon, st.session_state[f'companion_{i}_name_from']))

                    driver_locations_map = []
                    for i in range(1, st.session_state.num_drivers_from + 1):
                        driver_loc_str = st.session_state[f'driver_{i}_location_from']
                        if driver_loc_str:
                            lat, lon = get_lat_lon(driver_loc_str, API_KEY)
                            all_points.append((lat, lon))
                            driver_locations_map.append((lat, lon, st.session_state[f'driver_{i}_name_from']))
                    
                    if all_points:
                        min_lat = min(p[0] for p in all_points)
                        max_lat = max(p[0] for p in all_points)
                        min_lon = min(p[1] for p in all_points)
                        max_lon = max(p[1] for p in all_points)

                        lat_buffer = (max_lat - min_lat) * 0.15
                        lon_buffer = (max_lon - min_lon) * 0.15

                        m = folium.Map(location=[(min_lat + max_lat) / 2, (min_lon + max_lon) / 2], zoom_start=12)
                        m.fit_bounds([[min_lat - lat_buffer, min_lon - lon_buffer], [max_lat + lat_buffer, max_lon + lon_buffer]])

                        folium.Marker([office_lat, office_lon], tooltip="Office (Departure)", icon=folium.Icon(color='blue', icon='briefcase')).add_to(m)

                        for c_lat, c_lon, c_name in companion_locations_map:
                            folium.Marker([c_lat, c_lon], tooltip=f"{c_name} (Companion)", icon=folium.Icon(color='green', icon='user')).add_to(m)

                        for d_lat, d_lon, d_name in driver_locations_map:
                            folium.Marker([d_lat, d_lon], tooltip=f"{d_name} (Driver)", icon=folium.Icon(color='red', icon='car')).add_to(m)

                        st_folium(m, width=700, height=550)
                    else:
                        st.warning("No valid locations entered to display on the map.")
                except Exception as e:
                    st.error(f"Error loading map: {e}. Please ensure all entered addresses are valid and your Google Maps API key is correct and enabled for Geocoding API.")
            else:
                st.info("Click 'Show/Update Map' on the left to visualize the entered locations.")
        
        st.markdown("<br>", unsafe_allow_html=True)
        # Start Algorithm Button
        st.markdown("<div class='red-button' style='text-align: center;'>", unsafe_allow_html=True)
        if st.button("▶️ Start Carpooling Algorithm", key="start_algo_from_main", use_container_width=True, help="Run the optimization algorithm to find the best carpool assignments."):
            with st.spinner("Running the carpooling algorithm... This might take a moment."):
                locations = {
                    "office": st.session_state.office_location_from,
                    "drivers": {
                        st.session_state[f'driver_{i}_name_from']: st.session_state[f'driver_{i}_location_from']
                        for i in range(1, st.session_state.num_drivers_from + 1)
                        if st.session_state[f'driver_{i}_name_from'] and st.session_state[f'driver_{i}_location_from']
                    },
                    "companions": {
                        st.session_state[f'companion_{i}_name_from']: st.session_state[f'companion_{i}_location_from']
                        for i in range(1, st.session_state.num_companions_from + 1)
                        if st.session_state[f'companion_{i}_name_from'] and st.session_state[f'companion_{i}_location_from']
                    }
                }
                capacity = {
                    st.session_state[f'driver_{i}_name_from']: st.session_state[f'driver_{i}_capacity_from']
                    for i in range(1, st.session_state.num_drivers_from + 1)
                    if st.session_state[f'driver_{i}_name_from']
                }

                try:
                    start_time = time.time()
                    geocoded_locs, assignments, driver_paths = to_home_google_api.helper(locations, capacity)
                    end_time = time.time()
                    total_time = end_time - start_time

                    st.session_state.algorithm_output = (geocoded_locs, assignments, driver_paths, total_time)
                    st.session_state.show_results = True
                    st.success("Algorithm completed successfully! Navigating to results...")
                    time.sleep(1)
                    st.rerun()

                except requests.exceptions.RequestException as req_err:
                    st.error(f"Network or API request error: {req_err}. Please check your internet connection or Google Maps API key settings.")
                except KeyError as ke_err:
                    st.error(f"Location input error: {ke_err}. One or more addresses could not be geocoded. Please verify the entered addresses.")
                except Exception as e:
                    st.error(f"An unexpected error occurred during algorithm execution: {e}. Please report this issue.")
                st.session_state.show_results = False
        st.markdown("</div>", unsafe_allow_html=True)

    st.markdown("---")
    navigation_buttons(back_target="choose_direction") # Navigation at the very bottom

def display_results_to_office(locations: Dict[str, Any], assignments: Dict[str, Any], driver_paths: Dict[str, Any], algorithm_time: float):
    """Displays the carpooling results for 'To Office' scenario."""
    st.markdown("<h1 style='text-align: center; color: #36454F;'>✅ Carpooling Results - To Office</h1>", unsafe_allow_html=True)
    st.success("Here are the optimized carpooling routes and assignments for your morning commute to the office!")

    st.markdown("---")
    st.subheader("🗺️ Optimized Routes Map")
    st.container(border=True).info("Below is the map visualizing the optimized routes. Drivers' paths are shown picking up companions and proceeding to the office.")
    
    m = plot_to_office(locations, assignments, driver_paths)
    if m is not None:
        st_folium(m, width=2000, height=650) # Increased map size
    else:
        st.error("Map could not be generated. Ensure the `plot_to_office` function works correctly and returns a Folium map object.")

    st.markdown("---")
    st.subheader("👥 Carpooling Assignments Summary")
    st.container(border=True).write("This table summarizes which companions are assigned to each driver:")
    if assignments:
        assignment_data = []
        for driver, companions_data in assignments.items():
            companion_list = ", ".join([name for name, _ in companions_data])
            assignment_data.append({"Driver": driver, "Assigned Companions": companion_list if companion_list else "None"})
        
        df_assignments = pd.DataFrame(assignment_data)
        st.dataframe(df_assignments, hide_index=True, use_container_width=True) # Use st.dataframe for better interactivity
        st.info("Each driver is assigned to pick up the listed companions on their way to the office.")
    else:
        st.warning("No carpooling assignments were generated. This might indicate that no suitable matches were found, or the algorithm encountered an issue.")

    st.markdown("---")
    st.subheader("⏱️ Algorithm Performance")
    st.write(f"**Time taken to run the optimization algorithm:** `{algorithm_time:.4f}` seconds")
    st.info("The algorithm's performance can vary based on the number of participants and the complexity of routes. This metric indicates the computational efficiency.")

def display_results_from_office(locations: Dict[str, Any], assignments: Dict[str, Any], driver_paths: Dict[str, Any], algorithm_time: float):
    """Displays the carpooling results for 'From Office' scenario."""
    st.markdown("<h1 style='text-align: center; color: #36454F;'>✅ Carpooling Results - From Office</h1>", unsafe_allow_html=True)
    st.success("Here are the optimized carpooling routes and assignments for your evening commute from the office!")

    st.markdown("---")
    st.subheader("🗺️ Optimized Routes Map")
    st.container(border=True).info("Below is the map visualizing the optimized routes. Drivers' paths are shown picking up from office and dropping off companions at their homes.")
    
    m = plot_from_office(locations, assignments, driver_paths)
    if m is not None:
        st_folium(m, width=2000, height=650) # Increased map size
    else:
        st.error("Map could not be generated. Ensure the `plot_from_office` function works correctly and returns a Folium map object.")

    st.markdown("---")
    st.subheader("👥 Carpooling Assignments Summary")
    st.container(border=True).write("This table summarizes which companions are assigned to each driver:")
    if assignments:
        assignment_data = []
        for driver, companions_data in assignments.items():
            companion_list = ", ".join([name for name, _ in companions_data])
            assignment_data.append({"Driver": driver, "Assigned Companions": companion_list if companion_list else "None"})
        
        df_assignments = pd.DataFrame(assignment_data)
        st.dataframe(df_assignments, hide_index=True, use_container_width=True)
        st.info("Each driver is assigned to drop off the listed companions on their way home from the office.")
    else:
        st.warning("No carpooling assignments were generated. This might indicate that no suitable matches were found, or the algorithm encountered an issue.")

    st.markdown("---")
    st.subheader("⏱️ Algorithm Performance")
    st.write(f"**Time taken to run the optimization algorithm:** `{algorithm_time:.4f}` seconds")
    st.info("The algorithm's performance can vary based on the number of participants and the complexity of routes. This metric indicates the computational efficiency.")

def navigation_buttons(back_target: str = None):
    """
    Displays navigation buttons for going back and logging out.
    """
    st.markdown("<br>", unsafe_allow_html=True) # Add some space before buttons
    st.markdown("---") # Add a separator before navigation buttons for clarity
    
    nav_col1, nav_col2, nav_col3 = st.columns([1, 1, 1]) # Use 3 columns for better spacing
    
    if back_target:
        with nav_col1:
            if st.button("🔙 Go Back", use_container_width=True):
                st.session_state.demo_choice = back_target
                st.session_state.show_results = False # Hide results when going back
                st.session_state.algorithm_output = None # Clear previous results
                st.rerun()
    
    # Empty column for spacing
    with nav_col2:
        st.write("") 

    with nav_col3:
        if st.button("🚪 Log Out", use_container_width=True):
            # Clear all session state variables upon logout
            for key in list(st.session_state.keys()):
                del st.session_state[key]
            st.rerun()

# --- Main Application Logic ---
def main():
    """Controls the flow of the Streamlit application based on session state."""
    st.set_page_config(
        page_title="Carpooling Optimization Demo",
        layout="wide", # Use wide layout to maximize horizontal space
        initial_sidebar_state="collapsed", # Keep sidebar collapsed by default
        menu_items={
            'About': "This is a carpooling optimization demo application. Built with Streamlit."
        }
    )
    
    set_custom_css() # Apply custom CSS globally

    initialize_session_state()

    # Define the page flow using session state
    if not st.session_state.logged_in:
        login_page()
    elif not st.session_state.demo_started:
        welcome_page()
    elif st.session_state.demo_choice is None or st.session_state.demo_choice == "start_choice":
        demo_start_choice_page()
    elif st.session_state.demo_choice == "choose_direction":
        choose_direction_page()
    elif st.session_state.demo_choice == "to_office":
        demo_to_office_page()
    elif st.session_state.demo_choice == "from_office":
        demo_from_office_page()

if __name__ == "__main__":
    main()
