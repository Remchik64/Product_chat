import streamlit as st
import requests
import hashlib
from streamlit_extras.switch_page_button import switch_page
from googletrans import Translator
import os
from PIL import Image
import streamlit.components.v1 as components
from tinydb import TinyDB, Query
User = Query()  # Добавьте эту строку после импорта Query
from utils.utils import update_remaining_generations
from utils.chat_database import ChatDatabase
from utils.page_config import PAGE_CONFIG, setup_pages
from typing import List
from utils.context_manager import ContextManager

# Ключ для настроек основного чата
MAIN_CHAT_SETTINGS_KEY = "main_chat_context_settings"

# Сначала конфигурация страницы
st.set_page_config(
    page_title="Бизнес-Идея",
    page_icon="💡",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Затем настройка страниц
setup_pages()

# Инициализация менеджера контекста
context_manager = ContextManager()

# Проверка аутентификации
if "authenticated" not in st.session_state or not st.session_state.authenticated:
    st.warning("Пожалуйста, войдите в систему")
    switch_page(PAGE_CONFIG["registr"]["name"])
    st.stop()

# Инициализация session state
if 'username' not in st.session_state:
    st.warning("Пожалуйста, войдите в систему")
    # Сначала устанавливаем состояние аутентификации в False
    st.session_state.authenticated = False
    # Затем обновляем страницы
    setup_pages()
    # И только потом переключаем страницу
    switch_page("Вход/Регистрация")
    st.stop()

# Проверяем наличие активного токена и доступа
user_db = TinyDB('user_database.json')
user_data = user_db.search(User.username == st.session_state.username)

if user_data:
    user_data = user_data[0]
    
    # Синхронизируем session state с данными из базы
    st.session_state.active_token = user_data.get('active_token')
    st.session_state.remaining_generations = user_data.get('remaining_generations', 0)
    st.session_state.access_granted = bool(user_data.get('active_token'))
    
    # Проверяем токен и статус доступа
    if not st.session_state.active_token:
        st.warning("Пожалуйста, введите ключ доступа")
        switch_page("Ввод/Покупка токена")
else:
    st.error("Пользователь н найден")
    st.session_state.authenticated = False
    setup_pages()
    switch_page("Вход/Регистрация")

# Инициализируем базы данных
chat_db = ChatDatabase(f"{st.session_state.username}_main_chat")  # Добавляем суффикс для главной страницы

# Папка с изображениями профиля (исправленный путь)
PROFILE_IMAGES_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', 'profile_images'))
ASSISTANT_ICON_PATH = os.path.join(PROFILE_IMAGES_DIR, 'assistant_icon.png')  # Путь к иконке ассистента

# Проверем существование фал иконки ассстента
if os.path.exists(ASSISTANT_ICON_PATH):
    try:
        assistant_avatar = Image.open(ASSISTANT_ICON_PATH)
    except Exception as e:
        st.error(f"Оибка при открытии изображения ассистента: {e}")
        assistant_avatar = "🤖"  # Используем эмодзи по умолчанию
else:
    assistant_avatar = "🤖"  # Используем эмодзи по умолчанию

# Функция для получения объекта изображения профиля пользователя
def get_user_profile_image(username):
    for ext in ['png', 'jpg', 'jpeg']:
        image_path = os.path.join(PROFILE_IMAGES_DIR, f"{username}.{ext}")
        if os.path.exists(image_path):
            try:
                return Image.open(image_path)
            except Exception as e:
                st.error(f"Ошибка при открытии изображения {image_path}: {e}")
                return "👤"
    return "👤"  # Возвращаем эмодзи, если изображение не найдено

def get_message_hash(role, content):
    return hashlib.md5(f"{role}:{content}".encode()).hexdigest()

def display_remaining_generations():
    if "remaining_generations" in st.session_state:
        st.sidebar.write(f"Осталось генераций: {st.session_state.remaining_generations}")

def submit_question():
    if not verify_user_access():
        return
        
    user_input = st.session_state.get('user_input', '')
    if not user_input:
        st.warning("Пожалуйста, введите ваш вопрос.")
        return
    
    # Проверяем количество оставшихся генераций
    if st.session_state.remaining_generations <= 0:
        st.error("У вас закончились генерации. Пожалуйста, активируйте новый токен.")
        switch_page("Вход/Регистрация")
        return
        
    # Добавляем индикатор загрузки
    with st.spinner('Отправляем ваш запрос...'):
        try:
            # Получаем настройки контекста для основного чата
            settings = st.session_state.get(MAIN_CHAT_SETTINGS_KEY, {
                "use_context": True,
                "context_messages": 10
            })
            
            # Получаем контекст для сообщения с учетом настроек
            if settings["use_context"]:
                enhanced_message = context_manager.get_context(
                    st.session_state.username,
                    user_input,
                    last_n_messages=settings["context_messages"]
                )
            else:
                enhanced_message = user_input
            
            payload = {
                "question": enhanced_message
            }
            response = requests.post(
                st.secrets["flowise"]["api_url"],
                json=payload,
                timeout=100
            )
            
            # Проверяем статус ответа
            if response.status_code != 200:
                st.error(f"Ошибка API: {response.status_code}")
                return
                
            output = response.json()
            response_text = output.get('text', '')
            
            if not response_text:
                st.warning("Получен пустой ответ от API.")
                return

            translated_text = translate_text(response_text)
            if not translated_text:
                st.warning("Ошибка при переводе ответа.")
                return

            # Обновляем количество генераций
            st.session_state.remaining_generations -= 1
            user_db.update({
                'remaining_generations': st.session_state.remaining_generations,
                'token_generations': st.session_state.remaining_generations
            }, User.username == st.session_state.username)
            
            # Добавляем сообщения в чат
            user_hash = get_message_hash("user", user_input)
            assistant_hash = get_message_hash("assistant", translated_text)

            if "message_hashes" not in st.session_state:
                st.session_state.message_hashes = set()

            # Добавляем сообщения и обновляем интерфейс
            if user_hash not in st.session_state.message_hashes:
                st.session_state.message_hashes.add(user_hash)
                display_user_message(user_input)
                chat_db.add_message("user", user_input)

            if assistant_hash not in st.session_state.message_hashes:
                st.session_state.message_hashes.add(assistant_hash)
                display_assistant_message(translated_text)
                chat_db.add_message("assistant", translated_text)

            # Очищаем поле ввода
            st.session_state.user_input = ""
            
        except requests.exceptions.Timeout:
            st.error("Превышено время ожидания ответа от сервера")
        except Exception as e:
            st.error(f"Ошибка при обработке запроса: {str(e)}")

def translate_text(text):
    try:
        translator = Translator()
        # Проверяем входной текст
        if text is None or not isinstance(text, str) or text.strip() == '':
            return "Получен п отет от API"
            
        translation = translator.translate(text, dest='ru')
        if translation and hasattr(translation, 'text') and translation.text:
            return translation.text
        return "Ошиба пеевода: некорректный ответ от переводчика"
        
    except Exception as e:
        st.error(f"шибка при еревод: {str(e)}")
        # овращаем оригинальный текст в случае ошибки
        return f"Оригинальный текст: {text}"

def clear_chat_history():
    chat_db.clear_history()  # Очистка базы данных истории чата
    if "message_hashes" in st.session_state:
        del st.session_state["message_hashes"]  # Сброс хэшей сообщений

def verify_user_access():
    # Проверяем наличие пользователя и активного токен
    if 'username' not in st.session_state:
        st.warning("Пожалуйста, войдите в систему")
        switch_page("Вход/Регистрация")
        return False
        
    user_data = user_db.search(User.username == st.session_state.username)
    if not user_data:
        st.error("Пользователь не найден")
        switch_page("Вход/Регистрация")
        return False
        
    if not user_data[0].get('active_token'):
        st.warning("Пожалуйста, введите ключ доступа")
        switch_page("Вход/Регистрация")
        return False
        
    return True



def display_assistant_message(content):
    with st.chat_message("assistant", avatar=assistant_avatar):
        st.write(content)

def display_user_message(content):
    user_avatar = get_user_profile_image(st.session_state.username)
    with st.chat_message("user", avatar=user_avatar):
        st.write(content)

def main():
    # Инициализируем базу данных чата в начале функции main
    chat_db = ChatDatabase(f"{st.session_state.username}_main_chat")
    
    # Получаем историю чата
    chat_history = chat_db.get_history()
    
    # Отображаем историю чата
    for message in chat_history:
        if message["role"] == "assistant":
            display_assistant_message(message["content"])
        else:
            display_user_message(message["content"])
    
    st.title("Бизнес-Идея")

    # Отображаем количество генераций в начале
    display_remaining_generations()

    # Добавляем кнопк очистки чата
    if st.sidebar.button("Очистить чат"):
        chat_db.clear_history()
        st.rerun()

    # Добавляем разделитель в боковом меню
    st.sidebar.markdown("---")
    
    # Настройки контекста в боковой панели
    st.sidebar.title("Настройки контекста для истории")

    # Инициализация настроек в session_state если их нет
    if MAIN_CHAT_SETTINGS_KEY not in st.session_state:
        st.session_state[MAIN_CHAT_SETTINGS_KEY] = {
            "use_context": True,
            "context_messages": 10
        }

    # Настройки контекста
    use_context = st.sidebar.checkbox(
        "Использовать контекст истории",
        value=st.session_state[MAIN_CHAT_SETTINGS_KEY]["use_context"],
        key=f"{MAIN_CHAT_SETTINGS_KEY}_use_context"
    )

    if use_context:
        context_messages = st.sidebar.slider(
            "Количество сообщений для анализа",
            min_value=3,
            max_value=30,
            value=st.session_state[MAIN_CHAT_SETTINGS_KEY]["context_messages"],
            key=f"{MAIN_CHAT_SETTINGS_KEY}_slider",
            help="Количество последних сообщений, которые будут анализироваться для создания контекста."
        )

    # Обновляем настройки в session_state
    st.session_state[MAIN_CHAT_SETTINGS_KEY].update({
        "use_context": use_context,
        "context_messages": context_messages if use_context else 10
    })

    # Поле ввода с формой в основной части
    with st.form(key='question_form', clear_on_submit=True):
        st.text_area("Введите ваш вопрос", key="user_input", height=100)
        submit_button = st.form_submit_button("Отправить")

    if submit_button:
        submit_question()
        st.rerun()

    st.write(f"Streamlit version: {st.__version__}")

if __name__ == "__main__":
    main()
