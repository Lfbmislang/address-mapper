import streamlit as st
import pandas as pd
import geopandas as gpd
import pydeck as pdk
from geopy.geocoders import Nominatim
from geopy.extra.rate_limiter import RateLimiter
import time

# Configure page
st.set_page_config(page_title="Smart Address Mapper", layout="wide")
st.title("📍 Smart Address Mapping Tool")

# Initialize geocoder
@st.cache_resource
def init_geocoder():
    geolocator = Nominatim(user_agent="streamlit_address_mapper")
    return RateLimiter(geolocator.geocode, min_delay_seconds=1)

geocode = init_geocoder()

def main():
    with st.sidebar:
        st.header("Upload & Settings")
        uploaded_file = st.file_uploader(
            "Upload CSV file with addresses", 
            type=["csv"],
            help="File should contain 'name' and 'address' columns"
        )
        
        api_key = st.text_input(
            "Mapbox Access Token (optional)", 
            help="Get from https://account.mapbox.com",
            type="password"
        )
        
        map_style = st.selectbox(
            "Map Style",
            ["streets-v11", "outdoors-v11", "light-v10", "dark-v10", "satellite-v9"],
            index=0
        )

    if uploaded_file is not None:
        try:
            # Read and preview data
            df = pd.read_csv(uploaded_file)
            
            with st.expander("Raw Data Preview"):
                st.dataframe(df.head())
            
            # Validate required columns
            if not all(col in df.columns for col in ['name', 'address']):
                st.error("CSV must contain 'name' and 'address' columns")
                st.stop()
            
            # Geocode addresses
            with st.status("Geocoding addresses...", expanded=True) as status:
                st.write("Converting addresses to coordinates...")
                df = geocode_addresses(df)
                status.update(label="Geocoding complete!", state="complete")
            
            # Show processed data
            with st.expander("Processed Data"):
                st.dataframe(df)
            
            # Display map
            display_map(df, map_style, api_key)
            
        except Exception as e:
            st.error(f"Error: {str(e)}")
            st.stop()
    else:
        st.info("👈 Please upload a CSV file to get started")
        st.markdown("""
        ### Expected CSV Format:
        ```csv
        name,address
        "Central Park","Central Park, New York, NY"
        "Eiffel Tower","Champ de Mars, 5 Avenue Anatole France, Paris"
        ```
        """)

def geocode_addresses(df: pd.DataFrame) -> pd.DataFrame:
    """Convert addresses to latitude/longitude coordinates"""
    df = df.copy()
    
    # Add progress bar
    progress_bar = st.progress(0)
    total_rows = len(df)
    
    # Geocode each address
    coordinates = []
    for i, row in df.iterrows():
        try:
            location = geocode(row['address'])
            if location:
                coordinates.append((location.latitude, location.longitude))
            else:
                coordinates.append((None, None))
        except Exception as e:
            st.warning(f"Couldn't geocode: {row['address']} - {str(e)}")
            coordinates.append((None, None))
        
        # Update progress
        progress_bar.progress((i + 1) / total_rows)
        time.sleep(0.1)  # Small delay for smooth progress update
    
    # Add coordinates to dataframe
    df[['latitude', 'longitude']] = pd.DataFrame(coordinates, index=df.index)
    
    # Remove rows where geocoding failed
    df = df.dropna(subset=['latitude', 'longitude'])
    
    return df

def display_map(df: pd.DataFrame, map_style: str, api_key: str = None):
    """Display interactive map with clickable popups"""
    layer = pdk.Layer(
        "ScatterplotLayer",
        data=df,
        get_position=["longitude", "latitude"],
        get_radius=100,
        get_fill_color=[255, 0, 0, 180],
        pickable=True,
        auto_highlight=True,
    )
    
    # Tooltip template
    tooltip = {
        "html": """
        <b>Name:</b> {name}<br/>
        <b>Address:</b> {address}<br/>
        <b>Latitude:</b> {latitude:.4f}<br/>
        <b>Longitude:</b> {longitude:.4f}
        """,
        "style": {
            "backgroundColor": "white",
            "color": "black",
            "padding": "10px",
            "border-radius": "5px",
            "box-shadow": "0px 0px 5px rgba(0,0,0,0.2)"
        }
    }
    
    # Set initial view to center on the data
    view_state = pdk.ViewState(
        latitude=df["latitude"].mean(),
        longitude=df["longitude"].mean(),
        zoom=11,
        pitch=0
    )
    
    # Configure map
    st.pydeck_chart(pdk.Deck(
        layers=[layer],
        initial_view_state=view_state,
        tooltip=tooltip,
        map_style=f"mapbox://styles/mapbox/{map_style}",
        api_keys={"mapbox": api_key} if api_key else None
    ))

if __name__ == "__main__":
    main()
