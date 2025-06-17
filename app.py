import streamlit as st
import pandas as pd
import io  # Add this import at the top

# ... (keep your existing imports and initial setup code)

# Replace your current file uploader and CSV reading code with this:
uploaded_file = st.file_uploader("Upload CSV file (columns: Name, Address)", type="csv")

if uploaded_file is not None:
    try:
        # Use StringIO to properly handle the file object
        df = pd.read_csv(io.StringIO(uploaded_file.getvalue().decode('utf-8')))
        
        # Alternatively, you can try this version which works for both Excel and CSV:
        # if uploaded_file.name.endswith('.csv'):
        #     df = pd.read_csv(uploaded_file)
        # else:
        #     df = pd.read_excel(uploaded_file)
        
        # Rest of your processing code...
        
    except UnicodeDecodeError:
        st.error("File encoding error. Please save your CSV as UTF-8 encoded.")
    except pd.errors.EmptyDataError:
        st.error("The file is empty.")
    except pd.errors.ParserError:
        st.error("Error parsing the file. Please check if it's a valid CSV.")
    except Exception as e:
        st.error(f"An unexpected error occurred: {str(e)}")

# app.py
import streamlit as st
import pandas as pd
import folium
from geopy.geocoders import Nominatim
from geopy.extra.rate_limiter import RateLimiter
from sklearn.cluster import DBSCAN
import numpy as np
from streamlit_folium import st_folium

# App title and description
st.title("🌍 Address Mapping Tool")
st.markdown("""
Upload a CSV with addresses to automatically:
- Geocode addresses to latitude/longitude
- Cluster nearby locations
- Visualize on an interactive map
""")

# File upload
uploaded_file = st.file_uploader("Upload CSV file (columns: Name, Address)", type="csv")

if uploaded_file is not None:
    # Read CSV
    df = pd.read_csv(uploaded_file)
    
    # Check required columns
    if not all(col in df.columns for col in ['Name', 'Address']):
        st.error("CSV must contain 'Name' and 'Address' columns")
        st.stop()
    
    with st.spinner('Geocoding addresses... Please wait...'):
        # Initialize geocoder
        geolocator = Nominatim(user_agent="address_mapper")
        geocode = RateLimiter(geolocator.geocode, min_delay_seconds=1)
        
        def get_coordinates(address):
            try:
                location = geocode(address + ", Philippines")
                if location:
                    return (location.latitude, location.longitude)
                return (None, None)
            except:
                return (None, None)
        
        # Geocode addresses
        df[['latitude', 'longitude']] = df['Address'].apply(
            lambda x: pd.Series(get_coordinates(x))
        )
    
    # Split into successful and failed geocoding
    success_df = df.dropna(subset=['latitude', 'longitude'])
    failed_df = df[df['latitude'].isna() | df['longitude'].isna()]
    
    # Show results summary
    st.success(f"✅ Successfully geocoded {len(success_df)}/{len(df)} addresses")
    
    # Show successful geocoding in an expandable section
    with st.expander("Show successfully geocoded addresses", expanded=True):
        if not success_df.empty:
            st.dataframe(success_df[['Name', 'Address', 'latitude', 'longitude']])
        else:
            st.warning("No addresses were successfully geocoded")
    
    # Show failed geocoding in an expandable section
    with st.expander("Show addresses that failed geocoding", expanded=False):
        if not failed_df.empty:
            st.dataframe(failed_df[['Name', 'Address']])
            
            # Add manual coordinate input option
            st.markdown("**Manually add coordinates for failed addresses:**")
            selected_failed = st.selectbox(
                "Select address to fix", 
                failed_df['Address'],
                key='failed_select'
            )
            
            col1, col2 = st.columns(2)
            with col1:
                lat = st.number_input("Latitude", key='lat_input')
            with col2:
                lon = st.number_input("Longitude", key='lon_input')
            
            if st.button("Add Coordinates"):
                idx = failed_df[failed_df['Address'] == selected_failed].index[0]
                df.at[idx, 'latitude'] = lat
                df.at[idx, 'longitude'] = lon
                st.experimental_rerun()
        else:
            st.info("All addresses were successfully geocoded")
    
    # Only proceed if we have some successful geocoding
    if not success_df.empty:
        # Clustering
        coords = success_df[['latitude', 'longitude']].to_numpy()
        
        if len(coords) > 1:  # Need at least 2 points for clustering
            # Convert to radians for haversine metric
            coords_rad = np.radians(coords)
            kms_per_radian = 6371.0088
            epsilon = 2 / kms_per_radian  # 2km radius
            
            db = DBSCAN(eps=epsilon, min_samples=2, metric='haversine')
            success_df['cluster'] = db.fit_predict(coords_rad)
        else:
            success_df['cluster'] = -1  # No clusters with single point
        
        # Create map
        map_center = [success_df['latitude'].mean(), success_df['longitude'].mean()]
        m = folium.Map(location=map_center, zoom_start=12)
        
        # Add markers
        for _, row in success_df.iterrows():
            color = 'red' if row['cluster'] == -1 else 'blue'
            
            popup = folium.Popup(
                f"<b>Name:</b> {row['Name']}<br>"
                f"<b>Address:</b> {row['Address']}<br>"
                f"<b>Coordinates:</b> {row['latitude']:.6f}, {row['longitude']:.6f}",
                max_width=300
            )
            
            folium.Marker(
                [row['latitude'], row['longitude']],
                popup=popup,
                icon=folium.Icon(color=color, icon='info-sign')
            ).add_to(m)
        
        # Display map
        st.subheader("Interactive Map")
        st_folium(m, width=700, height=500)
        
        # Download button for successful geocodes
        st.download_button(
            label="Download Geocoded Data",
            data=success_df.to_csv(index=False),
            file_name='geocoded_addresses.csv',
            mime='text/csv'
        )

# Sidebar info
st.sidebar.markdown("""
### Instructions
1. Prepare a CSV with columns:
   - `Name` - Location name
   - `Address` - Full address
2. Upload the file
3. Wait for geocoding to complete
4. View the interactive map

### Tips for better geocoding:
- Include city and country in addresses
- Avoid abbreviations when possible
- For Philippine addresses, include "Philippines"
""")
