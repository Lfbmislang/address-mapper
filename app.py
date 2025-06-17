import streamlit as st
import pandas as pd
import googlemaps
from datetime import datetime
import pydeck as pdk
import os

# Page configuration
st.set_page_config(page_title="Google Maps Address Visualizer", layout="wide")
st.title("📍 Google Maps Address Visualizer")

# Initialize Google Maps client
def get_gmaps_client():
    api_key = st.secrets.get("GOOGLE_MAPS_API_KEY", os.getenv("GOOGLE_MAPS_API_KEY"))
    if not api_key:
        api_key = st.text_input("Enter Google Maps API Key", type="password")
    if api_key:
        return googlemaps.Client(key=api_key)
    return None

def main():
    gmaps = get_gmaps_client()
    
    with st.sidebar:
        st.header("Data Input")
        uploaded_file = st.file_uploader(
            "Upload CSV file with addresses", 
            type=["csv"],
            help="File should contain 'name' and 'address' columns"
        )
        
        if uploaded_file:
            sample_data = pd.read_csv(uploaded_file).head(1)
            st.info(f"Sample row:\nName: {sample_data['name'].values[0]}\nAddress: {sample_data['address'].values[0]}")

    if uploaded_file and gmaps:
        try:
            df = pd.read_csv(uploaded_file)
            
            # Validate columns
            if not all(col in df.columns for col in ['name', 'address']):
                st.error("CSV must contain 'name' and 'address' columns")
                st.stop()
            
            # Geocode addresses
            with st.status("Geocoding addresses with Google Maps...", expanded=True) as status:
                st.write("Converting addresses to coordinates...")
                df = geocode_addresses(df, gmaps)
                status.update(label="Geocoding complete!", state="complete")
            
            # Show data
            with st.expander("Processed Data", expanded=True):
                st.dataframe(df)
            
            # Display map
            display_google_map(df)
            
        except Exception as e:
            st.error(f"Error: {str(e)}")
    elif uploaded_file and not gmaps:
        st.error("Please enter a valid Google Maps API key to continue")

def geocode_addresses(df, gmaps_client):
    """Convert addresses to coordinates using Google Maps API"""
    df = df.copy()
    locations = []
    
    progress_bar = st.progress(0)
    total = len(df)
    
    for i, row in df.iterrows():
        try:
            geocode_result = gmaps_client.geocode(row['address'])
            if geocode_result:
                loc = geocode_result[0]['geometry']['location']
                locations.append({
                    'name': row['name'],
                    'address': row['address'],
                    'latitude': loc['lat'],
                    'longitude': loc['lng'],
                    'formatted_address': geocode_result[0]['formatted_address']
                })
            else:
                st.warning(f"Could not geocode: {row['address']}")
        except Exception as e:
            st.warning(f"Error geocoding {row['address']}: {str(e)}")
        
        progress_bar.progress((i + 1) / total)
    
    return pd.DataFrame(locations)

def display_google_map(df):
    """Display interactive map with Google Maps style"""
    # Create PyDeck layer
    layer = pdk.Layer(
        "ScatterplotLayer",
        data=df,
        get_position=["longitude", "latitude"],
        get_radius=100,
        get_fill_color=[255, 0, 0, 200],
        pickable=True,
        auto_highlight=True,
    )
    
    # Tooltip with HTML formatting
    tooltip = {
        "html": """
        <div style="padding: 10px; background: white; color: black; border-radius: 5px; box-shadow: 0 0 5px rgba(0,0,0,0.2)">
            <b>{name}</b><br/>
            <small>{address}</small><br/>
            <small>📍 {formatted_address}</small><br/>
            <small>Lat: {latitude:.4f}, Lng: {longitude:.4f}</small>
        </div>
        """,
        "style": {
            "backgroundColor": "transparent",
            "border": "none"
        }
    }
    
    # Set initial view
    view_state = pdk.ViewState(
        latitude=df["latitude"].mean(),
        longitude=df["longitude"].mean(),
        zoom=12,
        pitch=0
    )
    
    # Google Maps style configuration
    google_map_style = pdk.map_styles.ROAD
    
    # Create and display the map
    st.pydeck_chart(pdk.Deck(
        layers=[layer],
        initial_view_state=view_state,
        tooltip=tooltip,
        map_style=google_map_style,
        api_keys={"google_maps": st.secrets.get("GOOGLE_MAPS_API_KEY")}
    ))

if __name__ == "__main__":
    main()
