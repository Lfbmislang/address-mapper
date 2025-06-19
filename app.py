import streamlit as st
import pandas as pd
import pydeck as pdk
from geopy.geocoders import Nominatim, GoogleV3
from geopy.extra.rate_limiter import RateLimiter
import time
import os

# Configure environment and page
os.environ["MAPBOX_API_KEY"] = "no-token-needed"
st.set_page_config(
    page_title="Address Mapper Pro", 
    layout="wide", 
    initial_sidebar_state="expanded"
)
st.title("📍 Address Mapping Tool")

def is_valid_address(address):
    """Enhanced address validation"""
    if not isinstance(address, str):
        return False
    parts = address.split(',')
    return (len(parts) >= 3 
            and any(char.isdigit() for char in address)
            and any(char.isalpha() for char in address))

@st.cache_resource
def init_geocoder():
    """Initialize geocoder with robust fallback options"""
    try:
        geolocator = Nominatim(user_agent="address_mapper_v2")
        return RateLimiter(geolocator.geocode, min_delay_seconds=1)
    except Exception as e:
        st.warning(f"Nominatim initialization failed: {str(e)}")
        try:
            if 'GOOGLE_API_KEY' in st.secrets:
                st.success("Using Google Geocoding API")
                google_geocoder = GoogleV3(api_key=st.secrets["GOOGLE_API_KEY"])
                return RateLimiter(google_geocoder.geocode, min_delay_seconds=0.1)
            else:
                st.error("No Google API key found in secrets")
                return None
        except Exception as e:
            st.error(f"Geocoder initialization failed: {str(e)}")
            return None

def display_map(df):
    """Display map with small precise pins"""
    valid_df = df.dropna(subset=['latitude', 'longitude']).copy()
    
    if valid_df.empty:
        st.warning("No valid coordinates to display")
        return
    
    try:
        # Convert to numeric (safety check)
        valid_df['latitude'] = pd.to_numeric(valid_df['latitude'])
        valid_df['longitude'] = pd.to_numeric(valid_df['longitude'])
        
        # Calculate viewport
        avg_lat = valid_df['latitude'].mean()
        avg_lon = valid_df['longitude'].mean()
        
        # Create layer with small pins
        layer = pdk.Layer(
            "ScatterplotLayer",
            data=valid_df,
            get_position=["longitude", "latitude"],
            get_radius=25,  # Small pin size (original: 100-500)
            get_fill_color=[255, 0, 0, 220],  # Red with opacity
            get_line_color=[0, 0, 0],  # Black outline
            line_width_min_pixels=1,  # Thin border
            pickable=True,
            auto_highlight=True,
        )
        
        # Set zoom level based on data
        zoom = 14 if len(valid_df) == 1 else 11
        
        st.pydeck_chart(pdk.Deck(
            map_style="road",  # Lightweight base map
            initial_view_state=pdk.ViewState(
                latitude=avg_lat,
                longitude=avg_lon,
                zoom=zoom,
                pitch=0,  # 2D view (original had 50° tilt)
            ),
            layers=[layer],
            tooltip={
                "html": "<b>{name}</b><br>{address}",
                "style": {
                    "backgroundColor": "white",
                    "color": "black",
                    "fontSize": "14px"
                }
            }
        ))
        
    except Exception as e:
        st.error(f"Detailed map failed: {str(e)}")
        # Fallback to simple map
        st.map(valid_df[['latitude', 'longitude']])

def process_addresses(df, geocode_func):
    """Process addresses with comprehensive tracking"""
    with st.status("Geocoding addresses...", expanded=True) as status:
        progress_bar = st.progress(0)
        results = []
        stats = {'success': 0, 'failed': 0}
        
        for i, row in df.iterrows():
            address = str(row['address']).strip()
            result = {
                'name': row['name'],
                'address': address,
                'latitude': None,
                'longitude': None,
                'status': 'Pending'
            }
            
            try:
                if not is_valid_address(address):
                    result['status'] = 'Invalid format'
                    stats['failed'] += 1
                else:
                    location = geocode_func(address)
                    if location:
                        result.update({
                            'latitude': location.latitude,
                            'longitude': location.longitude,
                            'status': 'Success'
                        })
                        stats['success'] += 1
                    else:
                        result['status'] = 'No results'
                        stats['failed'] += 1
                
            except Exception as e:
                result.update({
                    'status': f'Error: {str(e)[:100]}',
                    'error': str(e)
                })
                stats['failed'] += 1
            
            results.append(result)
            progress_bar.progress((i + 1) / len(df))
            time.sleep(0.2)  # Rate limiting
            
        status.update(
            label=f"Completed: {stats['success']} success, {stats['failed']} failed",
            state="complete"
        )
        return pd.DataFrame(results), stats

def main():
    # Initialize
    geocode_func = init_geocoder()
    if not geocode_func:
        st.error("Geocoding service unavailable")
        return
    
    # File upload
    st.sidebar.header("Data Input")
    uploaded_file = st.sidebar.file_uploader(
        "Upload CSV", 
        type=["csv"],
        help="Requires 'name' and 'address' columns"
    )
    
    if uploaded_file:
        try:
            # Read CSV
            df = pd.read_csv(uploaded_file)
            
            # Validate columns
            if not all(col in df.columns for col in ['name', 'address']):
                st.error("Missing required columns: 'name' and 'address'")
                st.write("Found columns:", df.columns.tolist())
                return
            
            # Process data
            geo_df, stats = process_addresses(df, geocode_func)
            
            # Show results
            col1, col2 = st.columns(2)
            with col1:
                with st.expander("✅ Successful Geocodes", expanded=True):
                    success_df = geo_df[geo_df['status'] == 'Success']
                    st.dataframe(success_df)
                    
                    st.download_button(
                        "Download Successes",
                        success_df.to_csv(index=False),
                        "successful_addresses.csv"
                    )
            
            with col2:
                with st.expander("⚠️ Failed Geocodes", expanded=True):
                    failed_df = geo_df[geo_df['status'] != 'Success']
                    st.dataframe(failed_df)
                    
                    st.download_button(
                        "Download Failures",
                        failed_df.to_csv(index=False),
                        "failed_addresses.csv"
                    )
            
            # Display map
            st.header("📍 Interactive Map")
            display_map(geo_df)
            
        except Exception as e:
            st.error(f"Processing error: {str(e)}")

if __name__ == "__main__":
    main()
