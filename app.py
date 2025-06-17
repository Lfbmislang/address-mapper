import streamlit as st
import pandas as pd
import geopandas as gpd
import pydeck as pdk
from typing import Optional

def main():
    st.set_page_config(page_title="Address Mapper", layout="wide")
    st.title("📍 Address Mapping Tool")
    
    # Sidebar for uploads and settings
    with st.sidebar:
        st.header("Data Input")
        uploaded_file = st.file_uploader(
            "Upload CSV with addresses", 
            type=["csv"],
            help="File should contain 'address' or 'latitude/longitude' columns"
        )
        
        map_style = st.selectbox(
            "Map Style",
            ["road", "satellite", "terrain"],
            index=0
        )
    
    # Main content area
    tab1, tab2 = st.tabs(["Map View", "Data View"])
    
    with tab1:
        if uploaded_file is not None:
            try:
                # Process the uploaded file
                df = pd.read_csv(uploaded_file)
                
                # Validate data
                if not validate_data(df):
                    st.warning("Data must contain either 'address' or both 'latitude' and 'longitude' columns")
                    return
                
                # Geocode if needed
                geo_df = process_data(df)
                
                # Display map
                display_map(geo_df, map_style)
                
            except Exception as e:
                st.error(f"An error occurred: {str(e)}")
                st.stop()
        else:
            st.info("Please upload a CSV file to get started")
    
    with tab2:
        if uploaded_file is not None:
            try:
                st.dataframe(df, use_container_width=True)
            except NameError:
                pass

def validate_data(df: pd.DataFrame) -> bool:
    """Check if dataframe contains required location columns"""
    has_coords = all(col in df.columns for col in ['latitude', 'longitude'])
    has_address = 'address' in df.columns
    return has_coords or has_address

def process_data(df: pd.DataFrame) -> gpd.GeoDataFrame:
    """Convert raw data to geodataframe"""
    if 'latitude' in df.columns and 'longitude' in df.columns:
        # Directly use coordinates
        return gpd.GeoDataFrame(
            df,
            geometry=gpd.points_from_xy(df.longitude, df.latitude)
        )
    else:
        # Geocode addresses (simplified example)
        st.warning("Geocoding functionality would go here")
        raise NotImplementedError("Full geocoding not implemented in this example")

def display_map(gdf: gpd.GeoDataFrame, map_style: str = "road"):
    """Create interactive map visualization"""
    layer = pdk.Layer(
        "ScatterplotLayer",
        data=gdf,
        get_position=["longitude", "latitude"],
        get_radius=100,
        get_fill_color=[255, 0, 0, 160],
        pickable=True,
        auto_highlight=True
    )
    
    view_state = pdk.ViewState(
        latitude=gdf["latitude"].mean(),
        longitude=gdf["longitude"].mean(),
        zoom=11
    )
    
    st.pydeck_chart(pdk.Deck(
        layers=[layer],
        initial_view_state=view_state,
        map_style=f"mapbox://styles/mapbox/{map_style}-v9"
    ))

if __name__ == "__main__":
    main()
