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
from flowise import Flowise
from typing import List

# Сначала конфигурация страницы
st.set_page_config(
    page_title="Бизнес-Идея",
    page_icon="💡",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Затем настройка страниц
setup_pages()

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
    st.error("Пользователь не найден")
    st.session_state.authenticated = False
    setup_pages()
    switch_page("Вход/Регистрация")

# Инициализируем базы данных
chat_db = ChatDatabase(st.session_state.username)

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
            payload = {
                "question": user_input
            }
            response = requests.post(
                st.secrets["flowise"]["api_url"],
                json=payload,
                timeout=100  # Добавляем таймаут
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
                user_avatar = get_user_profile_image(st.session_state.username)
                with st.chat_message("user", avatar=user_avatar):
                    st.write(user_input)
                chat_db.add_message("user", user_input)

            if assistant_hash not in st.session_state.message_hashes:
                st.session_state.message_hashes.add(assistant_hash)
                with st.chat_message("assistant", avatar=assistant_avatar):
                    st.write(translated_text)
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
        st.error(f"Ошибка при перевод: {str(e)}")
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

chat_bot_html = """
<div style="height: 600px; width: 100%;">
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
                backgroundColor: "#000000",
                right: 20,
                bottom: 20,
                size: 48, // small | medium | large | number
                dragAndDrop: true,
                iconColor: "white",
                customIconSrc: "https://raw.githubusercontent.com/walkxcode/dashboard-icons/main/svg/google-messages.svg",
                autoWindowOpen: {
                    autoOpen: true,      // Автоматически открывать окно чата
                    openDelay: 0,        // Задержка открытия в секундах (0 - без задержки)
                    autoOpenOnMobile: true, // Автоматически открывать на мобильных устройствах
                },
            },
            tooltip: {
                showTooltip: true,
                tooltipMessage: 'Привет!',
                tooltipBackgroundColor: 'black',
                tooltipTextColor: 'white',
                tooltipFontSize: 16,
            },
            chatWindow: {
                showTitle: true,
                title: 'Поддержка/Советы',
                titleAvatarSrc: '',
                showAgentMessages: true,
                welcomeMessage: 'Привет! Я помогу вам с вопросами.',
                errorMessage: 'This is a custom error message',
                backgroundColor: "#ffffff",
                backgroundImage: 'enter image path or link', // If set, this will overlap the background color of the chat window.
                height: 700,
                width: 400,
                fontSize: 16,
                //starterPrompts: ['What is a bot?', 'Who are you?'], // It overrides the starter prompts set by the chat flow passed
                starterPromptFontSize: 15,
                clearChatOnReload: false, // If set to true, the chat will be cleared when the page reloads.
                botMessage: {
                    backgroundColor: "#f7f8ff",
                    textColor: "#303235",
                    showAvatar: false,
                    showBotName: true,
                    botName: "Bot",
                    botNameColor: "#303235"
                },
                userMessage: {
                    backgroundColor: "#000000",
                    textColor: "#ffffff",
                    showAvatar: false,
                    showUserName: true,
                    userName: "User",
                    userNameColor: "#ffffff"
                },
                textInput: {
                    placeholder: 'Введите ваш вопрос',
                    backgroundColor: '#ffffff',
                    textColor: '#303235',
                    sendButtonColor: '#000000',
                    maxChars: 50,
                    maxCharsWarningMessage: 'You exceeded the characters limit. Please input less than 50 characters.',
                    autoFocus: true, // If not used, autofocus is disabled on mobile and enabled on desktop. true enables it on both, false disables it on both.
                    sendMessageSound: true,
                    // sendSoundLocation: "send_message.mp3", // If this is not used, the default sound effect will be played if sendSoundMessage is true.
                    receiveMessageSound: true,
                    // receiveSoundLocation: "receive_message.mp3", // If this is not used, the default sound effect will be played if receiveSoundMessage is true. 
                },
                feedback: {
                    color: '#303235',
                },
                footer: {
                    textColor: '#303235',
                    text: '',
                    company: '',
                    companyLink: '',
                }
            }
        }
    })
</script>
</div>
"""

def main():
    st.title("Бизнес-Идея")

    # Отображаем количество генераций в начале
    display_remaining_generations()

    # Добавляем кнопк очистки чата
    if st.sidebar.button("Очистить чат"):
        clear_chat_history()
        st.rerun()

    # Добавляем разделитель в боковом меню
    st.sidebar.markdown("---")
    
    # Перемещаем чат-бот в конец бокового меню
    st.sidebar.markdown("### Чат поддержки ")
    with st.sidebar:
        components.html(
            chat_bot_html,
            height=600,
            width=None,
            scrolling=False
        )

    # Отображение истории сообщений в основной части
    chat_history = chat_db.get_history()
    for idx, msg in enumerate(chat_history):
        if msg["role"] == "user":
            avatar = get_user_profile_image(st.session_state.username)
        else:
            avatar = assistant_avatar
        with st.chat_message(msg["role"], avatar=avatar):
            st.write(msg["content"])

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
