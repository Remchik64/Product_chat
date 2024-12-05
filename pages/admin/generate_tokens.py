import streamlit as st
from utils.utils import generate_and_save_token, get_data_file_path
from utils.page_config import setup_pages
import os
import json

# Настраиваем страницы
setup_pages()

# Проверка прав администратора
if not st.session_state.get("is_admin", False):
    st.error("Доступ запрещен. Страница доступна только администраторам.")
    st.stop()

# Дополнительная проверка имени пользователя и пароля администратора
if "admin_verified" not in st.session_state:
    admin_username = st.text_input("Введите имя пользователя администратора")
    admin_password = st.text_input("Введите пароль администратора", type="password")
    
    if admin_username != st.secrets["admin"]["admin_username"] or admin_password != st.secrets["admin"]["admin_password"]:
        st.error("Неверное имя пользователя или пароль администратора")
        st.stop()
    
    st.session_state.admin_verified = True

# Проверяем и создаем папку chat если её нет
chat_dir = os.path.join(os.path.dirname(__file__), '..', '..', 'chat')
os.makedirs(chat_dir, exist_ok=True)

# Проверяем существование файла
keys_file = get_data_file_path('access_keys.json')
if not os.path.exists(keys_file):
    with open(keys_file, 'w') as f:
        json.dump({"keys": [], "generations": {}}, f)

st.title("Генерация токенов (Админ панель)")

with st.form("token_generation"):
    num_tokens = st.number_input("Количество токенов", min_value=1, max_value=10, value=1)
    generations = st.number_input("Количество генераций на токен", 
                                min_value=10, max_value=1000, value=500)
    submit = st.form_submit_button("Сгенерировать")

if submit:
    for _ in range(num_tokens):
        new_token = generate_and_save_token(generations)
        st.code(new_token)
        st.write(f"Токен успешно создан с {generations} генерациями")

