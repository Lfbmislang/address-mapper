import streamlit as st
import pandas as pd
import pydeck as pdk
from geopy.geocoders import Nominatim, GoogleV3
from geopy.extra.rate_limiter import RateLimiter
import time

# Configure page
st.set_page_config(page_title="Address Mapper Pro", layout="wide")
st.title("📍 Address Mapping Tool")

def is_valid_address(address):
    """Basic address validation"""
    return (isinstance(address, str) 
            and len(address.split(',')) >= 3 
            and any(char.isdigit() for char in address))

@st.cache_resource
def init_geocoder():
    """Initialize geocoder with fallback options"""
    try:
        geolocator = Nominatim(user_agent="streamlit_address_mapper_pro")
        return RateLimiter(geolocator.geocode, min_delay_seconds=1)
    except Exception as e:
        st.warning(f"Nominatim initialization failed: {str(e)}")
        try:
            if 'GOOGLE_API_KEY' in st.secrets:
                st.warning("Falling back to Google Geocoding API")
                return GoogleV3(api_key=st.secrets["GOOGLE_API_KEY"]).geocode
            else:
                st.error("No Google API key found in secrets")
                return None
        except Exception as e:
            st.error(f"Geocoder initialization failed: {str(e)}")
            return None

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

def process_addresses(df, geocode_func):
    """Process addresses with enhanced error handling"""
    with st.status("Geocoding addresses...", expanded=True) as status:
        progress_bar = st.progress(0)
        coordinates = []
        failed_addresses = []
        valid_count = 0
        
        for i, row in df.iterrows():
            address = str(row['address']).strip()
            try:
                if not is_valid_address(address):
                    st.warning(f"Invalid address format: {address}")
                    failed_addresses.append(address)
                    coordinates.append({
                        'name': row['name'],
                        'address': address,
                        'latitude': None,
                        'longitude': None,
                        'status': 'Invalid format'
                    })
                    continue
                
                location = geocode_func(address)
                if location:
                    valid_count += 1
                    coordinates.append({
                        'name': row['name'],
                        'address': address,
                        'latitude': location.latitude,
                        'longitude': location.longitude,
                        'raw': location.raw,
                        'status': 'Success'
                    })
                else:
                    failed_addresses.append(address)
                    coordinates.append({
                        'name': row['name'],
                        'address': address,
                        'latitude': None,
                        'longitude': None,
                        'status': 'No results'
                    })
            except Exception as e:
                failed_addresses.append(address)
                coordinates.append({
                    'name': row['name'],
                    'address': address,
                    'latitude': None,
                    'longitude': None,
                    'status': f'Error: {str(e)}'
                })
            
            progress_bar.progress((i + 1) / len(df))
            time.sleep(1.1)  # Conservative rate limiting
        
        status.update(
            label=f"Geocoding complete! ({valid_count} successful, {len(failed_addresses)} failed)",
            state="complete"
        )
        
        return pd.DataFrame(coordinates), failed_addresses

def main():
    geocode_func = init_geocoder()
    if not geocode_func:
        st.error("Geocoding service unavailable. Please try again later.")
        return
    
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
            
            # Process addresses
            geo_df, failed_addresses = process_addresses(df, geocode_func)
            
            if geo_df.empty:
                st.error("No addresses were successfully geocoded")
                st.stop()
            
            # Show results
            col1, col2 = st.columns(2)
            
            with col1:
                with st.expander("✅ Successful Geocodes", expanded=True):
                    success_df = geo_df[geo_df['latitude'].notnull()]
                    st.dataframe(success_df)
                    st.download_button(
                        label="Download Successful Geocodes",
                        data=success_df.to_csv(index=False),
                        file_name="successful_geocodes.csv",
                        mime="text/csv"
                    )
            
            with col2:
                if failed_addresses:
                    with st.expander("⚠️ Failed Geocodes", expanded=True):
                        failed_df = geo_df[geo_df['latitude'].isnull()]
                        st.dataframe(failed_df)
                        st.download_button(
                            label="Download Failed Geocodes",
                            data=failed_df.to_csv(index=False),
                            file_name="failed_geocodes.csv",
                            mime="text/csv"
                        )
            
            # Display map only with successful geocodes
            display_map(geo_df[geo_df['latitude'].notnull()])
            
        except Exception as e:
            st.error(f"Processing error: {str(e)}")
            st.stop()

if __name__ == "__main__":
    main()
