import streamlit as st
import pandas as pd
import pydeck as pdk
from geopy.geocoders import Nominatim, GoogleV3
from geopy.extra.rate_limiter import RateLimiter
import time
import os

# Configure environment and page
os.environ["MAPBOX_API_KEY"] = "no-token-needed"  # Required for pydeck even if not using Mapbox
st.set_page_config(page_title="Address Mapper Pro", layout="wide", initial_sidebar_state="expanded")
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
        geolocator = Nominatim(user_agent="streamlit_address_mapper_pro_v1")
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
    """Robust map display with multiple fallback options"""
    # First validate data
    valid_df = df.dropna(subset=['latitude', 'longitude']).copy()
    
    if valid_df.empty:
        st.warning("No valid coordinates to display on map")
        return
    
    # Ensure coordinates are numeric
    valid_df['latitude'] = pd.to_numeric(valid_df['latitude'], errors='coerce')
    valid_df['longitude'] = pd.to_numeric(valid_df['longitude'], errors='coerce')
    valid_df = valid_df.dropna(subset=['latitude', 'longitude'])
    
    if valid_df.empty:
        st.warning("No valid numeric coordinates available")
        return
    
    # Try PyDeck first
    try:
        # Calculate viewport
        avg_lat = valid_df['latitude'].mean()
        avg_lon = valid_df['longitude'].mean()
        
        # Handle single point case
        if len(valid_df) == 1:
            avg_lat += 0.01  # Small offset for better visibility
            zoom_level = 14
        else:
            zoom_level = 11
            
        # Create layer
        layer = pdk.Layer(
            "ScatterplotLayer",
            data=valid_df,
            get_position=["longitude", "latitude"],
            get_radius=500,
            get_fill_color=[255, 0, 0, 200],
            pickable=True,
            auto_highlight=True,
        )
        
        # Render map
        st.pydeck_chart(pdk.Deck(
            map_style="road",  # Simple style that always works
            initial_view_state=pdk.ViewState(
                latitude=avg_lat,
                longitude=avg_lon,
                zoom=zoom_level,
                pitch=50,
            ),
            layers=[layer],
            tooltip={
                "html": "<b>{name}</b><br/>{address}",
                "style": {
                    "backgroundColor": "steelblue",
                    "color": "white"
                }
            }
        ))
        return
    
    except Exception as e:
        st.warning(f"PyDeck map failed: {str(e)}")
        # Fall through to alternative map display

    # Fallback to Streamlit's native map
    try:
        st.map(valid_df[['latitude', 'longitude']])
    except Exception as e:
        st.error(f"All map rendering failed: {str(e)}")
        st.write("Debug - Valid coordinates data:", valid_df)

def process_addresses(df, geocode_func):
    """Robust address processing with detailed status tracking"""
    with st.status("Geocoding addresses...", expanded=True) as status:
        progress_bar = st.progress(0)
        results = []
        stats = {
            'success': 0,
            'invalid_format': 0,
            'no_results': 0,
            'errors': 0
        }
        
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
                # Validate address format
                if not is_valid_address(address):
                    result['status'] = 'Invalid format'
                    stats['invalid_format'] += 1
                    results.append(result)
                    continue
                
                # Geocode the address
                location = geocode_func(address)
                
                if location:
                    result.update({
                        'latitude': location.latitude,
                        'longitude': location.longitude,
                        'status': 'Success',
                        'raw': str(location.raw)[:200] + '...'  # Truncate long responses
                    })
                    stats['success'] += 1
                else:
                    result['status'] = 'No results'
                    stats['no_results'] += 1
                
            except Exception as e:
                result.update({
                    'status': f'Error: {str(e)}',
                    'error_details': str(e)
                })
                stats['errors'] += 1
            
            results.append(result)
            progress_bar.progress((i + 1) / len(df))
            time.sleep(0.2)  # Conservative rate limiting
        
        # Final status update
        status.update(
            label=(
                f"Geocoding complete! "
                f"{stats['success']} success, "
                f"{stats['invalid_format']} invalid, "
                f"{stats['no_results']} no results, "
                f"{stats['errors']} errors"
            ),
            state="complete"
        )
        
        return pd.DataFrame(results), stats

def main():
    # Initialize geocoder
    st.sidebar.header("Configuration")
    geocode_func = init_geocoder()
    
    if not geocode_func:
        st.error("Geocoding service unavailable. Please try again later.")
        return
    
    # File upload
    st.sidebar.header("Data Input")
    uploaded_file = st.sidebar.file_uploader(
        "Upload CSV file", 
        type=["csv"],
        help="Must contain 'name' and 'address' columns"
    )
    
    if uploaded_file:
        try:
            # Read CSV with encoding fallback
            uploaded_file.seek(0)
            try:
                df = pd.read_csv(uploaded_file)
            except UnicodeDecodeError:
                uploaded_file.seek(0)
                df = pd.read_csv(uploaded_file, encoding='latin1')
            
            # Validate required columns
            if not all(col in df.columns for col in ['name', 'address']):
                st.error("CSV must contain 'name' and 'address' columns")
                st.write("Columns found:", df.columns.tolist())
                return
            
            # Show preview
            with st.expander("📄 Uploaded Data Preview", expanded=True):
                st.dataframe(df.head(3))
            
            # Process addresses
            geo_df, stats = process_addresses(df, geocode_func)
            
            # Show results
            col1, col2 = st.columns(2)
            
            with col1:
                with st.expander("✅ Successful Geocodes", expanded=True):
                    success_df = geo_df[geo_df['status'] == 'Success']
                    st.dataframe(success_df)
                    
                    if not success_df.empty:
                        st.download_button(
                            label="Download Successful Geocodes",
                            data=success_df.to_csv(index=False),
                            file_name="successful_geocodes.csv",
                            mime="text/csv"
                        )
            
            with col2:
                with st.expander("⚠️ Failed Geocodes", expanded=True):
                    failed_df = geo_df[geo_df['status'] != 'Success']
                    st.dataframe(failed_df)
                    
                    if not failed_df.empty:
                        st.download_button(
                            label="Download Failed Geocodes",
                            data=failed_df.to_csv(index=False),
                            file_name="failed_geocodes.csv",
                            mime="text/csv"
                        )
            
            # Display map
            st.header("📍 Interactive Map")
            display_map(geo_df)
            
        except Exception as e:
            st.error(f"Processing error: {str(e)}")
            st.write("Debug info:", str(e))

if __name__ == "__main__":
    main()
