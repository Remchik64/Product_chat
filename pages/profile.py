import streamlit as st
from streamlit_extras.switch_page_button import switch_page
from tinydb import TinyDB, Query
import os
from PIL import Image
from utils.utils import check_token_status, format_database
from utils.page_config import setup_pages, PAGE_CONFIG
import hashlib
import io
import mimetypes
from utils.security import hash_password, is_strong_password
import requests
from googletrans import Translator
from utils.chat_database import ChatDatabase
from utils.context_manager import ContextManager
from utils.utils import update_remaining_generations
import streamlit.components.v1 as components

# После импортов и перед st.set_page_config()
def is_valid_image(file_content):
    """Проверяет, является ли файл изображением"""
    try:
        Image.open(io.BytesIO(file_content))
        return True
    except Exception:
        return False

# Первым делом настройка страницы (должна быть в самом начале!)
st.set_page_config(
    page_title="Профиль",
    page_icon="👤",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Настройка страниц
setup_pages()

# HTML для чат-бота
chat_bot_html = """
<!DOCTYPE html>
<html>
<head>
    <meta charset="utf-8">
    <meta name="viewport" content="width=device-width, initial-scale=1">
</head>
<body>
    <div id="chatbot-container" style="width: 100%; height: 600px;">
        <script type="module">
            import Chatbot from "https://cdn.jsdelivr.net/npm/flowise-embed/dist/web.js"
            Chatbot.init({
                chatflowid: "28d13206-3a4d-4ef8-80e6-50b671b5766c",
                apiHost: "https://flowise-renataraev64.amvera.io",
                chatflowConfig: {
                    // topK: 2
                },
                theme: {
                    button: {
                        backgroundColor: "#32333f",
                        right: 20,
                        bottom: 20,
                        size: 48,
                        dragAndDrop: true,
                        iconColor: "#fffcfc",
                        customIconSrc: "",
                        autoWindowOpen: {
                            autoOpen: true,
                            openDelay: 0,
                            autoOpenOnMobile: true,
                        },
                    },
                    chatWindow: {
                        showTitle: true,
                        title: 'Вопросы по работе веб-приложения',
                        titleAvatarSrc: '',
                        showAgentMessages: true,
                        welcomeMessage: 'Здравствуйте! Чем могу помочь?',
                        errorMessage: 'Произошла ошибка. Попробуйте позже.',
                        backgroundColor: "#32333f",
                        height: 700,
                        width: 400,
                        fontSize: 16,
                        showCloseButton: false,
                        alwaysOpen: true,
                        starterPromptFontSize: 15,
                        clearChatOnReload: false,
                        botMessage: {
                            backgroundColor: "#1e1e2d",
                            textColor: "#fffcfc",
                            showAvatar: false,
                            avatarSrc: "",
                        },
                        userMessage: {
                            backgroundColor: "#444654",
                            textColor: "#fffcfc",
                            showAvatar: true,
                            avatarSrc: "https://raw.githubusercontent.com/zahidkhawaja/langchain-chat-nextjs/main/public/usericon.png",
                        },
                        textInput: {
                            placeholder: 'Введите ваш вопрос',
                            backgroundColor: '#1e1e2d',
                            textColor: '#fffcfc',
                            sendButtonColor: '#32333f',
                            maxChars: 1000,
                            maxCharsWarningMessage: 'Превышен лимит символов. Пожалуйста, введите меньше 1000 символов.',
                            autoFocus: true,
                            sendMessageSound: true,
                            receiveMessageSound: true,
                        },
                        feedback: {
                            color: '#fffcfc',
                        },
                        footer: {
                            textColor: '#fffcfc',
                            text: '',
                            company: '',
                            companyLink: 'https://startintellect.ru',
                        }
                    }
                }
            })

        </script>
    </div>
</body>
</html>
"""

# Добавляем чат-бота в боковую панель
with st.sidebar:
    st.title("Поддержка")
    components.html(chat_bot_html, height=700, scrolling=True)

# Проверка аутентификации
if "authenticated" not in st.session_state or not st.session_state.authenticated:
    st.error("Пожалуйста, войдите в систему")
    setup_pages()
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
    st.session_state.is_admin = False
    st.rerun()  # Используем rerun вместо switch_page

user_data = user_data[0]
# Синхронизируем session state с данными из базы
if user_data.get('active_token'):
    st.session_state.active_token = user_data['active_token']
    st.session_state.remaining_generations = user_data.get('remaining_generations', 0)

st.title(f"Личный кабинет {user_data['username']}")

# Отображение информации о пользователе
st.header("")
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

# Загрузка новой фотографии профиля
new_profile_image = st.file_uploader("Загрузить новую фотографию профиля", type=["png", "jpg", "jpeg"])
if new_profile_image is not None:
    st.image(new_profile_image, width=150)
    updates = {}
    needs_reload = False

    try:
        # Проверяем размер файла
        MAX_FILE_SIZE = 2 * 1024 * 1024  # 2MB
        if new_profile_image.size > MAX_FILE_SIZE:
            st.error("Размер файла превышает 2MB.")
            st.stop()

        # Проверяем, является ли файл изображением
        if not is_valid_image(new_profile_image.getbuffer()):
            st.error("Файл не является допустимым изображением.")
            st.stop()

        # Генерируем имя файла с расширением оригинального файла
        file_extension = os.path.splitext(new_profile_image.name)[1].lower()
        image_filename = f"{user_data['username']}{file_extension}"
        image_path = os.path.join(PROFILE_IMAGES_DIR, image_filename)

        # Удаляем старое изображение, если оно существует
        old_image_path = user_data.get('profile_image')
        if old_image_path and old_image_path != os.path.join(PROFILE_IMAGES_DIR, "default_user_icon.png"):
            if os.path.exists(old_image_path):
                try:
                    os.remove(old_image_path)
                except Exception as e:
                    st.warning(f"Не удалось удалить старое изображение: {e}")

        # Сохраняем новое изображение
        with open(image_path, "wb") as f:
            f.write(new_profile_image.getbuffer())

        # Проверяем валидность изображения
        try:
            img = Image.open(new_profile_image)
            img.verify()
            updates['profile_image'] = image_path
            needs_reload = True
        except Exception as e:
            st.error("Файл не является допустимым изображением.")
            if os.path.exists(image_path):
                os.remove(image_path)
            st.stop()

    except Exception as e:
        st.error(f"Ошибка при обработке изображения: {e}")
        st.stop()

if st.button("Обновить данные"):
    updates = {}
    needs_reload = False
    old_username = user_data['username']

    # Обработка изменения имени пользователя и email
    if new_username and new_username != old_username:
        existing_user = user_db.get(User.username == new_username)
        if existing_user:
            st.error("Пользователь с таким именем уже существует")
        else:
            updates['username'] = new_username
            needs_reload = True

    if new_email and new_email != user_data['email']:
        updates['email'] = new_email
        needs_reload = True

    # Обработка изменения пароля
    if new_password:
        if new_password != confirm_password:
            st.error("Проли не совпадают")
        else:
            is_strong, message = is_strong_password(new_password)
            if not is_strong:
                st.error(message)
            else:
                updates['password'] = hash_password(new_password)
                needs_reload = True

    # Обработка новой фотографии профиля
    if new_profile_image is not None:
        try:
            # Проверяем размер файла
            if new_profile_image.size > 2 * 1024 * 1024:  # 2MB
                st.error("Размер файла превышает 2MB.")
                st.stop()

            # Генерируем имя файла
            file_extension = os.path.splitext(new_profile_image.name)[1].lower()
            image_filename = f"{old_username}{file_extension}"
            image_path = os.path.join(PROFILE_IMAGES_DIR, image_filename)

            # Удаляем старое изображение
            old_image_path = user_data.get('profile_image')
            if old_image_path and old_image_path != os.path.join(PROFILE_IMAGES_DIR, "default_user_icon.png"):
                if os.path.exists(old_image_path):
                    try:
                        os.remove(old_image_path)
                    except Exception as e:
                        st.warning(f"Не удалось удалить старое изображение: {e}")

            # Сохраняем новое изображение
            with open(image_path, "wb") as f:
                f.write(new_profile_image.getbuffer())

            # Проверяем валидность изображения
            img = Image.open(new_profile_image)
            img.verify()
            updates['profile_image'] = image_path
            needs_reload = True

        except Exception as e:
            st.error(f"Ошибка при обработке изображения: {e}")
            if 'image_path' in locals() and os.path.exists(image_path):
                os.remove(image_path)
            st.stop()

    # Применяем все обновления
    if updates:
        try:
            user_db.update(updates, User.username == old_username)
            format_database()
            
            if 'username' in updates:
                st.session_state.username = updates['username']
            
            st.success("Данные успешно обновлен")
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

# Стили для увеличения ширины боковой панели
st.markdown(
    """
    <style>
        section[data-testid="stSidebar"] {
            width: 450px !important;
            max-width: 450px !important;
        }
        section[data-testid="stSidebarContent"] {
            width: 400px !important;
            max-width: 400px !important;
        }
    </style>
    """,
    unsafe_allow_html=True,
)

# Настройка страниц
setup_pages()

# Проверка аутентификации
if "authenticated" not in st.session_state or not st.session_state.authenticated:
    st.warning("Пожалуйста, войдите в систему")
    st.stop()

# Инициализация базы данных
user_db = TinyDB('user_database.json')
User = Query()

# Инициализация менеджера контекста
context_manager = ContextManager()

# Инициализация базы данных чата для профиля
chat_db = ChatDatabase(f"{st.session_state.username}_profile_chat")

# Папка с изображениями профиля
PROFILE_IMAGES_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', 'profile_images'))
ASSISTANT_ICON_PATH = os.path.join(PROFILE_IMAGES_DIR, 'assistant_icon.png')

# Загрузка аватара ассистента
if os.path.exists(ASSISTANT_ICON_PATH):
    try:
        assistant_avatar = Image.open(ASSISTANT_ICON_PATH)
    except Exception as e:
        assistant_avatar = "🤖"
else:
    assistant_avatar = "🤖"

def get_user_profile_image(username):
    for ext in ['png', 'jpg', 'jpeg']:
        image_path = os.path.join(PROFILE_IMAGES_DIR, f"{username}.{ext}")
        if os.path.exists(image_path):
            try:
                return Image.open(image_path)
            except Exception as e:
                return "👤"
    return "👤"

def get_message_hash(role, content):
    return hashlib.md5(f"{role}:{content}".encode()).hexdigest()

def translate_text(text):
    try:
        translator = Translator()
        if text is None or not isinstance(text, str) or text.strip() == '':
            return "Получен пустой ответ от API"
            
        translation = translator.translate(text, dest='ru')
        if translation and hasattr(translation, 'text') and translation.text:
            return translation.text
        return "Ошибка перевода: некорректный ответ от переводчика"
        
    except Exception as e:
        st.error(f"Ошибка при переводе: {str(e)}")
        return f"Оригинальный текст: {text}"

# Настройки контекста
PROFILE_CHAT_SETTINGS_KEY = "profile_chat_context_settings"

# Инициализация настроек в session_state если их нет
if PROFILE_CHAT_SETTINGS_KEY not in st.session_state:
    st.session_state[PROFILE_CHAT_SETTINGS_KEY] = {
        "use_context": True,
        "context_messages": 10
    }

# Основной контейнер
main_container = st.container()

# Основной контент
with main_container:
    # Отображение истории чата
    chat_history = chat_db.get_history()
    for message in chat_history:
        if message["role"] == "assistant":
            with st.chat_message("assistant", avatar=assistant_avatar):
                st.markdown(message["content"])
        else:
            with st.chat_message("user", avatar=get_user_profile_image(st.session_state.username)):
                st.markdown(message["content"])

    # Функция отправки сообщения
    def submit_message(user_input):
        if not user_input:
            st.warning("Пожалуйста, введите сообщение")
            return
            
        if remaining_generations <= 0:
            st.error("У вас закончились генераций. Пожалуйста, активируйте новый токен.")
            return
            
        # Сохраняем и отображаем сообщение пользователя
        user_hash = get_message_hash("user", user_input)
        if "message_hashes" not in st.session_state:
            st.session_state.message_hashes = set()
            
        if user_hash not in st.session_state.message_hashes:
            st.session_state.message_hashes.add(user_hash)
            with st.chat_message("user", avatar=get_user_profile_image(st.session_state.username)):
                st.markdown(user_input)
            chat_db.add_message("user", user_input)
        
        # Получаем и оображаем ответ от ассистента
        with st.chat_message("assistant", avatar=assistant_avatar):
            with st.spinner('Получаем ответ...'):
                try:
                    # Получаем контекст для сообщения
                    use_context = st.session_state[PROFILE_CHAT_SETTINGS_KEY]["use_context"]
                    context_messages = st.session_state[PROFILE_CHAT_SETTINGS_KEY]["context_messages"]
                    
                    if use_context:
                        enhanced_message = context_manager.get_context(
                            st.session_state.username,
                            user_input,
                            last_n_messages=context_messages
                        )
                    else:
                        enhanced_message = user_input
                    
                    # Отправляем запрос к API
                    payload = {
                        "question": enhanced_message
                    }
                    
                    response = requests.post(
                        "https://flow.simplegpt.ru/api/v1/prediction/7bd1a0a0-4315-4b56-bb6d-0d5738eed59d",
                        json=payload,
                        timeout=100
                    )
                    
                    if response.status_code != 200:
                        st.error(f"Ошибка API: {response.status_code}")
                        return
                        
                    output = response.json()
                    response_text = output.get('text', '')
                    
                    if not response_text:
                        st.warning("Получен пустой ответ от API")
                        return
                    
                    # Переводим ответ
                    translated_text = translate_text(response_text)
                    
                    # Отображаем и сохраняем ответ
                    st.markdown(translated_text)
                    
                    assistant_hash = get_message_hash("assistant", translated_text)
                    if assistant_hash not in st.session_state.message_hashes:
                        st.session_state.message_hashes.add(assistant_hash)
                        chat_db.add_message("assistant", translated_text)
                    
                    # Обновляем количество геераций
                    update_remaining_generations(st.session_state.username, -1)
                    st.rerun()
                    
                except Exception as e:
                    st.error(f"Ошибка при получении ответа: {str(e)}")

    # Поле ввода сообщения

