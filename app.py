import streamlit as st
import pandas as pd
import pydeck as pdk
from geopy.geocoders import Nominatim
from geopy.extra.rate_limiter import RateLimiter
import time

# Configure page
st.set_page_config(page_title="Address Mapper", layout="wide")
st.title("📍 Address Mapping Tool")

@st.cache_resource
def init_geocoder():
    return RateLimiter(Nominatim(user_agent="address_mapper").geocode, min_delay_seconds=1)

def main():
    geocode = init_geocoder()
    
    with st.sidebar:
        st.header("Upload CSV")
        uploaded_file = st.file_uploader(
            "Choose CSV file", 
            type=["csv"],
            help="Must contain 'name' and 'address' columns"
        )
        
        if uploaded_file:
            try:
                # Validate file before processing
                if uploaded_file.size == 0:
                    st.error("File is empty")
                    st.stop()
                
                # Try multiple encodings
                try:
                    preview = pd.read_csv(uploaded_file, nrows=1)
                except:
                    uploaded_file.seek(0)
                    preview = pd.read_csv(uploaded_file, nrows=1, encoding='latin1')
                
                st.info(f"Preview:\nName: {preview['name'].values[0]}\nAddress: {preview['address'].values[0]}")
                
            except Exception as e:
                st.error(f"Invalid file format: {str(e)}")
                st.stop()

    if uploaded_file:
        try:
            # Read with error handling
            uploaded_file.seek(0)
            try:
                df = pd.read_csv(uploaded_file)
            except:
                uploaded_file.seek(0)
                df = pd.read_csv(uploaded_file, encoding='latin1')
            
            # Validate columns
            if not all(col in df.columns for col in ['name', 'address']):
                st.error("CSV must contain 'name' and 'address' columns")
                st.dataframe(df.head())  # Show what was detected
                st.stop()
            
            # Geocode with progress
            with st.status("Processing addresses...") as status:
                progress_bar = st.progress(0)
                df['coordinates'] = df['address'].apply(
                    lambda x: geocode(x) if pd.notnull(x) else None
                )
                progress_bar.progress(100)
            
            # Clean results
            df = df.dropna(subset=['coordinates'])
            df['latitude'] = df['coordinates'].apply(lambda x: x.latitude)
            df['longitude'] = df['coordinates'].apply(lambda x: x.longitude)
            
            # Show map
            st.pydeck_chart(pdk.Deck(
                map_style='mapbox://styles/mapbox/light-v9',
                initial_view_state=pdk.ViewState(
                    latitude=df['latitude'].mean(),
                    longitude=df['longitude'].mean(),
                    zoom=11,
                    pitch=50,
                ),
                layers=[
                    pdk.Layer(
                        'ScatterplotLayer',
                        data=df,
                        get_position='[longitude, latitude]',
                        get_color='[200, 30, 0, 160]',
                        get_radius=100,
                        pickable=True,
                        auto_highlight=True,
                    ),
                ],
                tooltip={
                    "html": "<b>Name:</b> {name}<br/><b>Address:</b> {address}",
                    "style": {
                        "backgroundColor": "white",
                        "color": "black"
                    }
                },
            ))
            
        except Exception as e:
            st.error(f"Processing error: {str(e)}")

if __name__ == "__main__":
    main()
