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
from utils.utils import update_remaining_generations, get_data_file_path
from utils.chat_database import ChatDatabase
from utils.page_config import PAGE_CONFIG, setup_pages
from typing import List
from utils.context_manager import ContextManager
import json
import time
from utils.translation import translate_text, display_message_with_translation

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

# Проверка аутентификации и доступа к API
if "authenticated" not in st.session_state or not st.session_state.authenticated:
    st.warning("Пожалуйста, войдите в систему")
    switch_page(PAGE_CONFIG["registr"]["name"])
    st.stop()

# Инициализация менеджера контекста с проверкой
context_manager = ContextManager()
# Проверка наличия ключа OpenRouter API
if "openrouter" not in st.secrets or "api_key" not in st.secrets["openrouter"]:
    st.error("Ошибка: API ключ OpenRouter не настроен. Пожалуйста, обратитесь к администратору.")
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
user_db = TinyDB(get_data_file_path('user_database.json'))
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
        switch_page(PAGE_CONFIG["key_input"]["name"])  # Используем название из конфигурации
else:
    st.error("Пользователь не найден")
    st.session_state.authenticated = False
    setup_pages()
    switch_page(PAGE_CONFIG["registr"]["name"])

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
    """Создает уникальный хэш для сообщения"""
    return hashlib.md5(f"{role}:{content}".encode()).hexdigest()

def display_remaining_generations():
    if "remaining_generations" in st.session_state:
        st.sidebar.write(f"Осталось генераций: {st.session_state.remaining_generations}")

def display_timer():
    """Отображает анимированный секундомер"""
    placeholder = st.empty()
    for seconds in range(60):
        time_str = f"⏱️ {seconds}с"
        placeholder.markdown(f"""
            <div style='
                font-size: 1.2em;
                font-weight: bold;
                color: #1E88E5;
                padding: 10px;
                border-radius: 8px;
                background-color: #E3F2FD;
                text-align: center;
                animation: pulse 1s infinite;
            '>
                {time_str}
            </div>
            <style>
                @keyframes pulse {{
                    0% {{ opacity: 1.0; }}
                    50% {{ opacity: 0.6; }}
                    100% {{ opacity: 1.0; }}
                }}
            </style>
        """, unsafe_allow_html=True)
        time.sleep(1)
        if not st.session_state.get('waiting_response', True):
            break
    placeholder.empty()

def submit_question():
    if not verify_user_access():
        return

    user_input = st.session_state.get('message_input', '').strip()
    if not user_input:
        st.warning("Пожалуйста, введите ваш вопрос.")
        return

    try:
        # Инициализация message_hashes
        if "message_hashes" not in st.session_state:
            st.session_state.message_hashes = set()

        # Сохраняем сообщение пользователя
        chat_db.add_message("user", user_input)
        display_message({"role": "user", "content": user_input}, "user")

        with st.spinner('Обрабатываем ваш запрос...'):
            # 1. Сначала получаем контекст через OpenRouter
            context_manager = ContextManager()
            enhanced_message = context_manager.get_context(
                st.session_state.username, 
                user_input
            )

            # 2. Затем отправляем запрос в Flowise
            flowise_url = f"{st.secrets['flowise']['api_base_url']}{st.secrets['flowise']['main_chat_id']}"
            
            payload = {
                "question": enhanced_message  # Используем сообщение с контекстом
            }

            response = requests.post(flowise_url, json=payload)
            response_data = response.json()

            if response_data and isinstance(response_data, dict) and 'text' in response_data:
                assistant_response = response_data['text'].strip()
                
                # Добавляем проверку языка и перевод
                try:
                    translator = Translator()
                    detected_lang = translator.detect(assistant_response).lang
                    
                    # Если ответ не на русском, переводим его
                    if detected_lang != 'ru':
                        translated_response = translator.translate(assistant_response, dest='ru')
                        assistant_response = translated_response.text
                except Exception as e:
                    st.error(f"Ошибка при переводе: {str(e)}")
                
                # Проверяем, что ответ не пустой
                if assistant_response:
                    chat_db.add_message("assistant", assistant_response)
                    display_message({
                        "role": "assistant", 
                        "content": assistant_response
                    }, "assistant")
                    update_remaining_generations(st.session_state.username, -1)
                    st.rerun()

    except Exception as e:
        st.error(f"Ошибка: {str(e)}")

def clear_input():
    """Очистка поля ввода"""
    st.session_state.message_input = ""

def display_message(message, role):
    """Отображает сообщение с кнопками управления"""
    message_hash = get_message_hash(role, message["content"])
    avatar = assistant_avatar if role == "assistant" else get_user_profile_image(st.session_state.username)
    
    # Закомментируем нумерацию сообщений
    # if 'message_counter' not in st.session_state:
    #     st.session_state.message_counter = 1
    # else:
    #     st.session_state.message_counter += 1
    
    # Закомментируем добавление номера в контент
    # message_with_number = {
    #     "role": message["role"],
    #     "content": f"{message['content']}\n\n*Сообщение #{st.session_state.message_counter}*"
    # }
    
    # Отображаем сообщение с кнопкой удаления
    with st.chat_message(role, avatar=avatar):
        cols = st.columns([0.95, 0.05])
        with cols[0]:
            st.markdown(message["content"])
        with cols[1]:
            if st.button("🗑", key=f"delete_{message_hash}", help="Удалить сообщение"):
                chat_db.delete_message(message_hash)
                if "message_hashes" in st.session_state:
                    if message_hash in st.session_state.message_hashes:
                        st.session_state.message_hashes.remove(message_hash)
                st.rerun()

def verify_user_access():
    """Проверка доступа пользователя"""
    # Проверяем наличие пользователя и активного токена
    if 'username' not in st.session_state:
        st.warning("Пожалуйста, войдите в систему")
        switch_page(PAGE_CONFIG["registr"]["name"])
        return False
        
    user_data = user_db.search(User.username == st.session_state.username)
    if not user_data:
        st.error("Пользователь не найден")
        switch_page(PAGE_CONFIG["registr"]["name"])
        return False
        
    if not user_data[0].get('active_token'):
        st.warning("Пожалуйста, введите ключ доступа")
        switch_page(PAGE_CONFIG["key_input"]["name"])
        return False
        
    return True

def clear_chat_history():
    """Очистка истории чата"""
    chat_db.clear_history()  # Очистка базы данных истории чата
    if "message_hashes" in st.session_state:
        del st.session_state["message_hashes"]  # Сброс хэшей сообщений
    if "message_counter" in st.session_state:  # Добавляем сброс счетчика
        del st.session_state.message_counter

def main():
    # Инициализируем базу данных чата
    chat_db = ChatDatabase(f"{st.session_state.username}_main_chat")
    
    # Получаем историю чата
    chat_history = chat_db.get_history()
    
    # Инициализируем message_hashes и message_counter
    if "message_hashes" not in st.session_state:
        st.session_state.message_hashes = set()
        # Добавляем все существующие хэши
        for message in chat_history:
            message_hash = get_message_hash(message["role"], message["content"])
            st.session_state.message_hashes.add(message_hash)
    
    # Сбрасываем счетчик сообщений перед отображением истории
    st.session_state.message_counter = 0
    
    # Отображаем историю чата
    for message in chat_history:
        display_message(message, message["role"])
    
    st.title("Бизнес-Идея")

    # Отображаем количество генераций в начале
    display_remaining_generations()

    # Добаляем кнопку очистки чата
    if "main_clear_chat_confirm" not in st.session_state:
        st.session_state.main_clear_chat_confirm = False

    # Заменяем простую кнопку очистки на кнопку с подтверждением
    if st.sidebar.button(
        "Очистить чат" if not st.session_state.main_clear_chat_confirm else "⚠ Нажмите еще раз для подтверждения",
        type="secondary" if not st.session_state.main_clear_chat_confirm else "primary",
        key="main_clear_chat_button"
    ):
        if st.session_state.main_clear_chat_confirm:
            # Выполняем очистку
            chat_db.clear_history()
            st.session_state.main_clear_chat_confirm = False
            st.rerun()
        else:
            # Первое нажатие - показываем предупреждение
            st.session_state.main_clear_chat_confirm = True
            st.sidebar.warning("⚠️ Вы уверены? Это действие нельзя отменить!")

    # Добавляем кнопку отмены, если показано предупреждение
    if st.session_state.main_clear_chat_confirm:
        if st.sidebar.button("Отмена", key="main_cancel_clear"):
            st.session_state.main_clear_chat_confirm = False
            st.rerun()

    # обавляем разделитель в боковом меню
    st.sidebar.markdown("---")
    
    # Настройки контекста в боковой панели
    st.sidebar.title("Настройки контекста для истории")

    # Инициализаци настроек в session_state если их нет
    if MAIN_CHAT_SETTINGS_KEY not in st.session_state:
        st.session_state[MAIN_CHAT_SETTINGS_KEY] = {
            "use_context": True,
            "context_messages": 10
        }

    # Нстройк котекста
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

    # Обновлем настройки в session_state
    st.session_state[MAIN_CHAT_SETTINGS_KEY].update({
        "use_context": use_context,
        "context_messages": context_messages if use_context else 10
    })

    # Поле ввода с возможностью растягивания
    user_input = st.text_area(
        "Введите ваше сообщение",
        height=100,
        key="message_input",
        placeholder="Введите текст сообщения здесь..."
    )

    # Создаем три колонки для кнопок
    col1, col2, col3 = st.columns(3)
    
    with col1:
        send_button = st.button("Отправить", key="send_message", use_container_width=True)
    with col2:
        clear_button = st.button("Очистить", key="clear_input", on_click=clear_input, use_container_width=True)
    with col3:
        cancel_button = st.button("Отменить", key="cancel_request", on_click=clear_input, use_container_width=True)

    # Обработка отправки сообщения
    if send_button and user_input and user_input.strip():
        st.session_state['_last_input'] = user_input
        with st.spinner('Отправляем ваш запрос...'):
            submit_question()

    # JavaScript для обработки Ctrl+Enter
    st.markdown("""
        <script>
        document.addEventListener('keydown', function(e) {
            if (e.ctrlKey && e.key === 'Enter') {
                window.parent.postMessage({
                    type: 'streamlit:setComponentValue',
                    key: 'ctrl_enter_pressed',
                    value: true
                }, '*');
            }
        });
        </script>
        """, unsafe_allow_html=True)

    st.write(f"Streamlit version: {st.__version__}")

if __name__ == "__main__":
    main()
