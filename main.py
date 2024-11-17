import streamlit as st
from streamlit_extras.switch_page_button import switch_page
from utils.page_config import PAGE_CONFIG, setup_pages

# Настраиваем страницы
setup_pages()

# Проверяем аутентификацию
if "authenticated" in st.session_state and st.session_state.authenticated:
    switch_page("Главная")
else:
    switch_page(PAGE_CONFIG["registr"]["name"])
