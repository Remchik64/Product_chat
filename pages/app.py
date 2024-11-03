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
from utils.page_config import setup_pages

# Настраиваем страницы
setup_pages()

# Инициализация session state
if 'username' not in st.session_state:
    st.warning("Пожалуйста, войдите в систему")
    switch_page("Вход/Регистрация")  # Используем display name
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
        switch_page("Ввод токена")  # Используем display name
else:
    st.error("Пользователь не найден")
    switch_page("Вход/Регистрация")  # Используем display name

# Инициализируем базы данных
chat_db = ChatDatabase(st.session_state.username)

# Папка с изображениями профиля (исправленный путь)
PROFILE_IMAGES_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', 'profile_images'))
ASSISTANT_ICON_PATH = os.path.join(PROFILE_IMAGES_DIR, 'assistant_icon.png')  # Путь к иконке ассистента

# Проверем существование файла иконки ассистента
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
        switch_page("Ввод токена")
        return
        
    try:
        payload = {"question": user_input}
        response = requests.post('https://flowise-renataraev64.amvera.io/api/v1/prediction/4a4a3f5c-9ebf-4243-8d4f-b3b69dd57313', json=payload)
        output = response.json()
        
        response_text = output.get('text', '')
        if not response_text:
            st.warning("Получен пустой ответ от API.")
            return

        translated_text = translate_text(response_text)
        if not translated_text:
            st.warning("Ошибка при переводе ответа.")
            return

        # Обновляем количество генераций в базе данных и session state
        st.session_state.remaining_generations -= 1
        user_db.update({
            'remaining_generations': st.session_state.remaining_generations,
            'token_generations': st.session_state.remaining_generations
        }, User.username == st.session_state.username)
        
        if st.session_state.remaining_generations <= 0:
            user_db.update({
                'active_token': None,
                'remaining_generations': 0,
                'token_generations': 0
            }, User.username == st.session_state.username)
            st.warning("Это была последняя доступная генерация. Токен деактивирован.")
            
        # Обновляем отображение
        display_remaining_generations()
        
        # Проверка дубликатов
        user_hash = get_message_hash("user", user_input)
        assistant_hash = get_message_hash("assistant", translated_text)

        if "message_hashes" not in st.session_state:
            st.session_state.message_hashes = set()

        # Добавляем сообщение пользователя
        if user_hash not in st.session_state.message_hashes:
            st.session_state.message_hashes.add(user_hash)
            user_avatar = get_user_profile_image(st.session_state.username)
            with st.chat_message("user", avatar=user_avatar):
                st.write(user_input)
            chat_db.add_message("user", user_input)

        # Добавляем сообщение ассистента (только один раз)
        if assistant_hash not in st.session_state.message_hashes:
            st.session_state.message_hashes.add(assistant_hash)
            with st.chat_message("assistant", avatar=assistant_avatar):
                st.write(translated_text)
            chat_db.add_message("assistant", translated_text)
    except Exception as e:
        st.error(f"Ошибка при обработке запроса: {str(e)}")
        return

def translate_text(text):
    try:
        translator = Translator()
        # Проверяем входной текст
        if text is None or not isinstance(text, str) or text.strip() == '':
            return "Получен пустой или некорректный ответ от API"
            
        translation = translator.translate(text, dest='ru')
        if translation and hasattr(translation, 'text') and translation.text:
            return translation.text
        return "Ошибка пе��евода: некорректный ответ от переводчика"
        
    except Exception as e:
        st.error(f"Ошибка при переводе: {str(e)}")
        # овращаем оригинальный текст в случае ошибки
        return f"Оригинальный текст: {text}"

def clear_chat_history():
    chat_db.clear_history()  # Очистка базы данных истории чата
    if "message_hashes" in st.session_state:
        del st.session_state["message_hashes"]  # Сброс хэшей сообщений

def verify_user_access():
    # Проверяем наличие пользователя и активного токена
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
        switch_page("Ввод токена")
        return False
        
    return True

st.title("Бизнес-Идея")

# Отображаем количество генераций в начале
display_remaining_generations()

# Добавляем кнопку очистки чата
if st.sidebar.button("Очистить чат"):
    clear_chat_history()
    st.rerun()  # Обновляем страницу для отображения изменений

# Отображение истории сообщений
chat_history = chat_db.get_history()
for idx, msg in enumerate(chat_history):
    if msg["role"] == "user":
        avatar = get_user_profile_image(st.session_state.username)
    else:
        avatar = assistant_avatar
    with st.chat_message(msg["role"], avatar=avatar):
        st.write(msg["content"])

# Поле вода с формой
with st.form(key='question_form'):
    st.text_input("Введите ваш вопрос", key="user_input")
    submit_button = st.form_submit_button("Отправить")

if submit_button:
    submit_question()

st.write(f"Streamlit version: {st.__version__}")

# Внедрение ат-бота
chat_bot_html = """
<div id="chatbot-container" style="position: fixed; bottom: 20px; right: 20px; z-index: 1000;">
    <div id="flowise-container"></div>
</div>

<script type="module">
    import Chatbot from "https://cdn.jsdelivr.net/npm/flowise-embed/dist/web.js"
    Chatbot.init({
        chatflowid: "d3dcc759-d88b-4dce-85c0-2b64d984e863",
        apiHost: "https://flowise-renataraev64.amvera.io",
        chatflowConfig: {
            // topK: 2
        },
        theme: {
            button: {
                backgroundColor: "#3B81F6",
                right: 20,
                bottom: 20,
                size: 52,
                dragAndDrop: true,
                iconColor: "white",
                customIconSrc: "https://raw.githubusercontent.com/walkxcode/dashboard-icons/main/svg/google-messages.svg",
            },
            tooltip: {
                showTooltip: true,
                tooltipMessage: 'Поддержка',
                tooltipBackgroundColor: 'red',
                tooltipTextColor: 'white',
                tooltipFontSize: 18,
            },
            chatWindow: {
                showTitle: true,
                title: 'Вопрос-ответ',
                titleAvatarSrc: 'https://raw.githubusercontent.com/walkxcode/dashboard-icons/main/svg/google-messages.svg',
                showAgentMessages: true,
                welcomeMessage: 'Привет, здесь можно задать вопрос по работе приложения',
                errorMessage: 'This is a custom error message',
                backgroundColor: "#ffffff",
                height: 400,
                width: 400,
                fontSize: 16,
                expandable: true,
                resizable: true,
                position: 'bottom',
            }
        }
    })

    // Функция для обновления позиции чат-бота
    function updateChatbotPosition() {
        const chatbot = document.getElementById('chatbot-container');
        const scrollY = window.scrollY;
        
        // Изменяем позицию чат-бота в зависимости от прокрутки
        chatbot.style.bottom = (20 + scrollY) + 'px';
    }

    // Добавляем обработчик события прокрутки
    window.addEventListener('scroll', updateChatbotPosition);
</script>
"""

# Вставляем HTML и JavaScript в приложение
components.html(chat_bot_html, height=480)
