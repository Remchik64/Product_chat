import streamlit as st
from streamlit_extras.switch_page_button import switch_page
from tinydb import TinyDB, Query
import os
from PIL import Image
from utils.utils import check_token_status, format_database
from utils.page_config import setup_pages, PAGE_CONFIG
import magic  # Добавьте в начало файла
import hashlib
from PIL import Image
import io
from utils.security import hash_password, is_strong_password

# Настраиваем страницы
setup_pages()

# Конфигурация страницы должна быть в начале
st.set_page_config(page_title="Личный кабинет", layout="wide")

# Проверка аутентификации
if "authenticated" not in st.session_state or not st.session_state.authenticated:
    st.error("Пожалуйста, войдите в систему")
    switch_page(PAGE_CONFIG["registr"]["name"])
    st.stop()

# Инициализация базы данных пользователей
user_db = TinyDB('user_database.json')

# Папка с изображениями профиля
PROFILE_IMAGES_DIR = 'profile_images'  # Используем относительный путь
if not os.path.exists(PROFILE_IMAGES_DIR):
    os.makedirs(PROFILE_IMAGES_DIR)

# Получение данных пользователя
User = Query()
user_data = user_db.search(User.username == st.session_state.username)
if not user_data:
    st.error("Пользователь не найден.")
    st.session_state.authenticated = False
    st.session_state.username = None
    switch_page(PAGE_CONFIG["registr"]["name"])
    st.stop()

user_data = user_data[0]
# Синхронизируем session state с данными из базы
if user_data.get('active_token'):
    st.session_state.active_token = user_data['active_token']
    st.session_state.remaining_generations = user_data.get('remaining_generations', 0)

st.title(f"Личный кабинет {user_data['username']}")

# Отображение информации о пользователе
st.header("Личная информация")
st.write(f"Email: {user_data['email']}")

# Отображение текущей фотографии профиля
st.subheader("Фотография профиля")
if user_data.get('profile_image') and os.path.exists(user_data['profile_image']):
    st.image(user_data['profile_image'], width=150)
    # Добавляем кнопку для уаления аватара
    if st.button("Удалить фотографию профиля"):
        old_image_path = user_data.get('profile_image')
        if old_image_path and old_image_path != os.path.join(PROFILE_IMAGES_DIR, "default_user_icon.png"):
            if os.path.exists(old_image_path):
                try:
                    os.remove(old_image_path)
                    st.success("Старое изображение успешно удалено.")
                except Exception as e:
                    st.error(f"Ошибка при удалении файла: {e}")
        # Обновляем данные пользователя в базе
        user_db.update({'profile_image': None}, User.username == st.session_state.username)
        st.success("Фотография профиля удалена")
        st.rerun()  # Перезагружаем страницу для обновления изменений
else:
    st.write("Фотография профиля не установлена.")

# Отображение токена и количества генераций
if user_data.get('active_token'):
    st.subheader("Доступные генерации")
    remaining_generations = user_data.get('remaining_generations', 0)
    
    if remaining_generations > 0:
        st.success(f"Осталось генераций: {remaining_generations}")
    else:
        st.warning("Генерации закончились. Пожалуйста, активируйте новый токен.")
else:
    st.warning("У вас нет активного токена. Для использования сервиса необходимо активировать токен.")
    if st.button("Активировать токен"):
        switch_page(PAGE_CONFIG["key_input"]["name"])

# Зона для обновления данных
st.header("Обновление данных")
new_username = st.text_input("Новое имя пользователя", value=user_data['username'])
new_email = st.text_input("Новый email", value=user_data['email'])
new_password = st.text_input("Новый пароль", type="password")
confirm_password = st.text_input("Подтвердите новый пароль", type="password")

if st.button("Обновить данные"):
    updates = {}
    needs_reload = False
    old_username = user_data['username']

    if new_username and new_username != old_username:
        # Проверяем, не занято ли новое имя пользователя
        existing_user = user_db.get(User.username == new_username)
        if existing_user:
            st.error("Пользователь с таким именем уже существует")
        else:
            updates['username'] = new_username
            needs_reload = True

    if new_email and new_email != user_data['email']:
        updates['email'] = new_email
        needs_reload = True

    if new_password:
        if new_password != confirm_password:
            st.error("Пароли не совпадают")
        else:
            is_strong, message = is_strong_password(new_password)
            if not is_strong:
                st.error(message)
            else:
                updates['password'] = hash_password(new_password)
                needs_reload = True

    # Применяем обновления
    if updates:
        try:
            # Обновляем данные в базе, используя старое имя пользователя для поиска
            user_db.update(updates, User.username == old_username)
            format_database()
            
            # Обновляем session_state только после успешного обновления базы
            if 'username' in updates:
                st.session_state.username = updates['username']
            
            st.success("Данные успешно обновлены")
            if needs_reload:
                st.rerun()
        except Exception as e:
            st.error(f"Ошибка при обновлении данных: {e}")
    else:
        st.info("Нет изменений для обновления")

# Зона для выхода из аккаунта
if st.button("Выйти"):
    st.session_state.authenticated = False
    st.session_state.username = None
    st.session_state.active_token = None
    st.session_state.remaining_generations = 0
    st.session_state.is_admin = False  # Удаляем статус администратора
    setup_pages()
    switch_page(PAGE_CONFIG["registr"]["name"])
