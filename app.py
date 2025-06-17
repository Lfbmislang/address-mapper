import streamlit as st
import pandas as pd

st.title("Test App")

uploaded_file = st.file_uploader("Upload CSV")
if uploaded_file:
    try:
        df = pd.read_csv(uploaded_file)
        st.success("File loaded successfully!")
        st.write(df.head())
    except Exception as e:
        st.error(f"Error: {str(e)}")
