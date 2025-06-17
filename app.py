import streamlit as st
import pandas as pd
import pydeck as pdk
from geopy.geocoders import Nominatim
from geopy.extra.rate_limiter import RateLimiter
import time

# Configure page
st.set_page_config(page_title="Address Mapper Pro", layout="wide")
st.title("📍 Address Mapping Tool")

@st.cache_resource
def init_geocoder():
    geolocator = Nominatim(user_agent="streamlit_address_mapper_pro")
    return RateLimiter(geolocator.geocode, min_delay_seconds=1)

def main():
    geocode = init_geocoder()
    
    with st.sidebar:
        st.header("Data Input")
        uploaded_file = st.file_uploader(
            "Upload CSV file", 
            type=["csv"],
            help="Must contain 'name' and 'address' columns"
        )
        
        if uploaded_file:
            try:
                # Preview first row
                uploaded_file.seek(0)
                preview = pd.read_csv(uploaded_file, nrows=1)
                st.info(f"Sample data:\nName: {preview['name'].values[0]}\nAddress: {preview['address'].values[0]}")
            except Exception as e:
                st.error(f"Preview error: {str(e)}")
                st.stop()

    if uploaded_file:
        try:
            # Read CSV with encoding fallback
            uploaded_file.seek(0)
            try:
                df = pd.read_csv(uploaded_file)
            except UnicodeDecodeError:
                uploaded_file.seek(0)
                df = pd.read_csv(uploaded_file, encoding='latin1')
            
            # Validate columns
            if not all(col in df.columns for col in ['name', 'address']):
                st.error("CSV must contain 'name' and 'address' columns")
                st.dataframe(df.head())
                st.stop()
            
            # Geocode with proper error handling
            with st.status("Geocoding addresses...", expanded=True) as status:
                progress_bar = st.progress(0)
                coordinates = []
                
                for i, row in df.iterrows():
                    try:
                        location = geocode(row['address'])
                        if location:
                            coordinates.append({
                                'name': row['name'],
                                'address': row['address'],
                                'latitude': location.latitude,
                                'longitude': location.longitude,
                                'raw': location.raw  # Store raw response
                            })
                        else:
                            st.warning(f"Could not geocode: {row['address']}")
                            coordinates.append({
                                'name': row['name'],
                                'address': row['address'],
                                'latitude': None,
                                'longitude': None
                            })
                    except Exception as e:
                        st.warning(f"Error geocoding {row['address']}: {str(e)}")
                        coordinates.append({
                            'name': row['name'],
                            'address': row['address'],
                            'latitude': None,
                            'longitude': None
                        })
                    
                    progress_bar.progress((i + 1) / len(df))
                    time.sleep(0.1)  # Rate limiting
                
                status.update(label="Geocoding complete!", state="complete")
            
            # Create DataFrame from successful geocodes
            geo_df = pd.DataFrame([c for c in coordinates if c['latitude'] is not None])
            
            if geo_df.empty:
                st.error("No addresses were successfully geocoded")
                st.stop()
            
            # Show processed data
            with st.expander("Geocoded Data", expanded=True):
                st.dataframe(geo_df)
            
            # Display map
            display_map(geo_df)
            
        except Exception as e:
            st.error(f"Processing error: {str(e)}")
            st.stop()

def display_map(df):
    """Display interactive map with markers"""
    layer = pdk.Layer(
        "ScatterplotLayer",
        data=df,
        get_position=["longitude", "latitude"],
        get_radius=100,
        get_fill_color=[255, 0, 0, 160],
        pickable=True,
        auto_highlight=True,
    )
    
    tooltip = {
        "html": """
        <div style="padding: 10px; background: white; color: black; border-radius: 5px;">
            <b>{name}</b><br/>
            <small>{address}</small><br/>
            <small>Lat: {latitude:.4f}, Lng: {longitude:.4f}</small>
        </div>
        """,
        "style": {
            "backgroundColor": "white",
            "color": "black"
        }
    }
    
    st.pydeck_chart(pdk.Deck(
        map_style="mapbox://styles/mapbox/light-v9",
        initial_view_state=pdk.ViewState(
            latitude=df["latitude"].mean(),
            longitude=df["longitude"].mean(),
            zoom=11,
            pitch=50,
        ),
        layers=[layer],
        tooltip=tooltip
    ))

if __name__ == "__main__":
    main()
