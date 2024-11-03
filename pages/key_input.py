import streamlit as st
from streamlit_extras.switch_page_button import switch_page
from utils.utils import load_access_keys, remove_used_key
from tinydb import TinyDB, Query
from utils.page_config import setup_pages

# Настраиваем страницы
setup_pages()

# Инициализация базы данных
user_db = TinyDB('user_database.json')
User = Query()

# Проверка аутентификации
if "authenticated" not in st.session_state or not st.session_state.authenticated:
    st.error("Пожалуйста, войдите в систему, чтобы получить доступ к этой странице.")
    switch_page("Вход/Регистрация")  # Используем display name
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
    
    if token in access_keys:
        user_db.update({
            'active_token': token,
            'remaining_generations': 500
        }, User.username == username)
        return True, "Токен активирован"
    
    return False, "Недействительный токен"

# Проверка токена
if st.button("Проверить токен"):
    success, message = verify_token(access_token, st.session_state.username)
    if success:
        st.success(message)
        st.session_state.access_granted = True
        switch_page("Главная")  # Используем display name
    else:
        st.error(message)

# Кнопка для покупки токена
if st.button("Купить токен", key="buy_link"):
    st.markdown('<a href="https://t.me/StartIntellectbot" target="_blank">Перейти к боту</a>', unsafe_allow_html=True)
