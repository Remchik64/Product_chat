import streamlit as st
import json
import os
from utils.utils import load_access_keys
from utils.page_config import setup_pages

# Настраиваем страницы
setup_pages()

# Проверка доступа
if "access_granted" not in st.session_state or not st.session_state.access_granted:
    st.error("Доступ запрещён. Пожалуйста, введите правильный токен на странице ввода ключа.")
    st.stop()

st.title("Новый чат")

# Логика для чата
user_input = st.text_input("Введите ваше сообщение")
if st.button("Отправить"):
    st.write(f"Вы: {user_input}")
    # Здесь можно добавить логику для обработки сообщений
