import streamlit as st
from streamlit_extras.switch_page_button import switch_page
from utils.utils import generate_and_save_token
from utils.page_config import setup_pages

# Настраиваем страницы
setup_pages()

# Проверка аутентификации
if "authenticated" not in st.session_state or not st.session_state.authenticated:
    switch_page("Вход/Регистрация")
else:
    switch_page("Главная")
