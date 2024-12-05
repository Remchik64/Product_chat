import streamlit as st
from streamlit_extras.switch_page_button import switch_page
from utils.utils import load_access_keys, remove_used_key, format_database, get_data_file_path
from tinydb import TinyDB, Query
from utils.page_config import PAGE_CONFIG, setup_pages
import os
import json

# Сначала конфигурация страницы
st.set_page_config(
    page_title="Ввод токена",
    page_icon="🔑",
    layout="wide",
    initial_sidebar_state="collapsed"
)

# Затем настройка страниц
setup_pages()

# Инициализация базы данных
user_db = TinyDB(get_data_file_path('user_database.json'))
User = Query()

# Проверка аутентификации
if "authenticated" not in st.session_state or not st.session_state.authenticated:
    st.warning("Пожалуйста, войдите в систему")
    switch_page(PAGE_CONFIG["registr"]["name"])  # Используем ключ из конфигурации
    st.stop()

st.title("Ввод токена")

# Поле для ввода токена
access_token = st.text_input("Вставьте токен доступа (например: b99176c5-8bca-4be9-b066-894e4103f32c)")

# Загрузка ключей доступа
access_keys = load_access_keys()

# Добавить функцию проверки токена
def verify_token(token, username):
    User = Query()
    user = user_db.get(User.username == username)
    
    if not user:
        return False, "Пользователь не найден"
    
    # Проверка использования токена
    existing_user = user_db.search(User.active_token == token)
    if existing_user and existing_user[0]['username'] != username:
        return False, "Токен уже используется другим пользователем"
    
    access_keys = load_access_keys()
    if token in access_keys:
        # Получаем количество генераций для данного токена
        with open(os.path.join('chat', 'access_keys.json'), 'r') as f:
            data = json.load(f)
            generations = data["generations"].get(token, 500)
        
        user_db.update({
            'active_token': token,
            'remaining_generations': generations  # Используем сохраненное количество генераций
        }, User.username == username)
        format_database()  # Добавляем форматирование
        return True, "Токен активирован"
    
    return False, "Недействительный токен"

# Проверка токена
if st.button("Активировать токен"):
    success, message = verify_token(access_token, st.session_state.username)
    if success:
        st.success(message)
        st.session_state.access_granted = True
        switch_page(PAGE_CONFIG["app"]["name"])  # Используем display name
    else:
        st.error(message)

# Кнопка для покупки токена
if st.button("Купить токен", key="buy_link"):
    st.markdown('<a href="https://startintellect.ru/products" target="_blank">Перейти на сайт</a>', unsafe_allow_html=True)
