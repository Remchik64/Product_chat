import streamlit as st
from streamlit_extras.switch_page_button import switch_page
from tinydb import TinyDB, Query
import os
from PIL import Image
from utils.page_config import setup_pages, PAGE_CONFIG
from utils.utils import format_database, get_data_file_path
from utils.security import hash_password, is_strong_password, verify_password, check_login_attempts, increment_login_attempts, reset_login_attempts
from datetime import datetime

# Сначала конфигурация страницы
st.set_page_config(page_title="Вход/Регистрация", layout="wide", initial_sidebar_state="collapsed")

# Затем настройка страниц
setup_pages()

# Инициализация базы данных пользователей
user_db = TinyDB(get_data_file_path('user_database.json'))

# Убедимся, что папка для хранения изображений профиля существует
PROFILE_IMAGES_DIR = 'profile_images'
if not os.path.exists(PROFILE_IMAGES_DIR):
    os.makedirs(PROFILE_IMAGES_DIR)

# Функция для регистрации пользователя
def register_user(username, email, password, profile_image_path=None):
    User = Query()
    if user_db.search(User.username == username):
        return False, "Пользователь с таким именем уже существует"
    if user_db.search(User.email == email):
        return False, "Пользователь с таким email уже существует"
        
    # Проверка надежности пароля
    is_strong, message = is_strong_password(password)
    if not is_strong:
        return False, message
        
    # Хеширование пароля
    hashed_password = hash_password(password)
    
    user_data = {
        'username': username,
        'email': email,
        'password': hashed_password,
        'profile_image': profile_image_path if profile_image_path else "profile_images/default_user_icon.png",
        'remaining_generations': 0,
        'is_admin': False,
        'created_at': datetime.now().isoformat()
    }
    user_db.insert(user_data)
    format_database()
    return True, "Регистрация успешна"

# Функция для входа в систему
def login(username, password):
    User = Query()
    
    # Проверка попыток входа
    can_login, message = check_login_attempts(username)
    if not can_login:
        st.error(message)
        return False
    
    user = user_db.get(User.username == username)
    if user and verify_password(password, user['password']):
        st.session_state.authenticated = True
        st.session_state.username = username
        st.session_state.is_admin = user.get('is_admin', False)
        reset_login_attempts(username)
        setup_pages()
        return True
    
    # Увеличиваем счетчик неудачных попыток
    success, message = increment_login_attempts(username)
    if not success:
        st.error(message)
    return False

# Заголовок
st.title("Вход в систему")

# Добавляем предупреждение о сохранении паролей
#st.warning("Внимание! Пароль не сохраняется в базе данных. Пожалуйста, сохраните его в надежном месте.")

# Форма для входа
username = st.text_input("Имя пользователя")
password = st.text_input("Пароль", type="password")

# Кнопки для входа и регистрации
if st.button("Login"):
    if username and password:  # Проверка на пустые поля
        if username == st.secrets["admin"]["admin_username"] and password == st.secrets["admin"]["admin_password"]:
            st.session_state.authenticated = True
            st.session_state.username = username
            st.session_state.is_admin = True
            st.success("Вход выполнен успешно!")
            setup_pages()
            switch_page(PAGE_CONFIG["key_input"]["name"])
        elif login(username, password):
            User = Query()
            user = user_db.get(User.username == username)
            st.session_state.authenticated = True 
            st.session_state.username = username
            st.session_state.is_admin = user.get('is_admin', False)
            setup_pages()
            switch_page(PAGE_CONFIG["key_input"]["name"])
        else:
            st.error("Неправильный логин или пароль.")
    else:
        st.error("Пожалуйста, введите имя пользователя и пароль.")

# Кнопка для регистрации
if not st.session_state.get("authenticated", False):
    if st.button("Вход/Регистрация"):
        st.session_state.show_registration_form = True

# Проверка состояния для отображения формы регистрации
if "show_registration_form" not in st.session_state:
    st.session_state.show_registration_form = False

if st.session_state.show_registration_form:
    with st.form("registration_form"):
        # Добавляем предупреждение о сохранении паролей в форме регистрации
        st.warning("Пожалуйста, сохраните свой логин и пароль в надежном месте. Восстановление логина и пароля не предусмотрено.")
        
        reg_username = st.text_input("Имя пользователя для регистрации")
        reg_email = st.text_input("Email")
        reg_password = st.text_input("Пароль", type="password")
        reg_confirm_password = st.text_input("Подтвердите пароль", type="password")
        
        submit_button = st.form_submit_button("Вход")
        
        if submit_button:
            if not reg_username or not reg_email or not reg_password or not reg_confirm_password:
                st.error("Пожалуйста, заполните все поля.")
            elif reg_password != reg_confirm_password:
                st.error("Пароли не совпадают")
            else:
                # Используем стандартный аватар для всех новых пользователей
                default_image_path = os.path.join(PROFILE_IMAGES_DIR, "default_user_icon.png")
                
                success, message = register_user(reg_username, reg_email, reg_password, default_image_path)
                if success:
                    st.success(message)
                    st.session_state.username = reg_username
                    st.session_state.authenticated = True
                    setup_pages() 
                    switch_page(PAGE_CONFIG["key_input"]["name"])
                else:
                    st.error(message)

# Добавление CSS для нопок
st.markdown(
    """
    <style>
    .stButton {
        margin-left: 0px;  /* Установите отрицательный отступ для сдвига влево */
        margin-right: 0px;  /* Установите положительный отступ для сдвига вправо */
    }
    </style>
    """,
    unsafe_allow_html=True
)

# Убедитесь, что пользователь аутентифицирован
if "authenticated" in st.session_state and st.session_state.authenticated:
    switch_page(PAGE_CONFIG["key_input"]["name"])
