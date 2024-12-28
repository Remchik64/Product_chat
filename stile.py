import streamlit as st

st.set_page_config(
    page_title="Your App",
    page_icon="🧊",
    layout="wide",
    initial_sidebar_state="expanded",
)

# Установка темы программно
st.markdown("""
    <style>
    .stApp {
        background-color: #FFFFFF;
        color: #262730;
    }
    </style>
    """, unsafe_allow_html=True)
