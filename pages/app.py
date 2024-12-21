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
user_db = TinyDB(get_data_file_path('user_database.json'))
user_data = user_db.search(User.username == st.session_state.username)

if user_data:
    user_data = user_data[0]
    
    # Синхронизируем session state с данными из базы
    st.session_state.active_token = user_data.get('active_token')
    st.session_state.remaining_generations = user_data.get('remaining_generations', 0)
    st.session_state.access_granted = bool(user_data.get('active_token'))
    
    # Проверяем токен  статус доступа
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
    """Создает уникальный хэш для сообщения"""
    return hashlib.md5(f"{role}:{content}".encode()).hexdigest()

def display_remaining_generations():
    if "remaining_generations" in st.session_state:
        st.sidebar.write(f"Осталось генераций: {st.session_state.remaining_generations}")

def submit_question():
    if not verify_user_access():
        return
        
    # Получаем настройки контекста из session_state
    settings = st.session_state.get(MAIN_CHAT_SETTINGS_KEY, {
        "use_context": True,
        "context_messages": 10
    })
    use_context = settings["use_context"]
    context_messages = settings["context_messages"]
    
    user_input = st.session_state.get('message_input', '')
    if not user_input:
        st.warning("Пожалуйста, введите ваш вопрос.")
        return
    
    # Проверяем количество оставшихся генераций
    if st.session_state.remaining_generations <= 0:
        st.error("У вас закончились генерации. Пожалуйста, активируйте новый токен.")
        switch_page("Вход/Регистрация")
        return
        
    with st.spinner('Отправляем ваш запрос...'):
        try:
            # Инициализируем менеджер контекста для основного чата
            chat_context_manager = ContextManager()
            
            # Получаем контекст из истории основного чата
            if use_context:
                enhanced_message = chat_context_manager.get_context(
                    username=st.session_state.username,
                    message=user_input,
                    flow_id=None  # Явно указываем None для основного чата
                )
            else:
                enhanced_message = user_input
            
            payload = {
                "question": enhanced_message
            }
            
            # Отправляем запрос
            response = requests.post(
                st.secrets["flowise"]["api_url"],
                json=payload,
                timeout=100,
                headers={'Content-Type': 'application/json'}
            )
            
            # Расширенная проверка статуса ответа
            if response.status_code != 200:
                error_message = f"Ошибка сервера (код {response.status_code})"
                try:
                    error_details = response.json()
                    if isinstance(error_details, dict):
                        error_message += f": {error_details.get('error', '')}"
                except:
                    try:
                        error_message += f": {response.text}"
                    except:
                        pass
                
                st.error(error_message)
                
                # Добавляем информацию для отладки
                print(f"API URL: {st.secrets['flowise']['api_url']}")
                print(f"Response status: {response.status_code}")
                print(f"Response headers: {response.headers}")
                try:
                    print(f"Response content: {response.text}")
                except:
                    pass
                
                return
            
            try:
                output = response.json()
            except ValueError as e:
                st.error(f"Ошибка при разборе ответа: {str(e)}")
                return
                
            response_text = output.get('text', '')
            
            if not response_text:
                st.warning("Получен пустой ответ от API")
                return

            # Переводим ответ
            translated_text = translate_text(response_text)
            if not translated_text:
                st.warning("Ошибка при переводе ответа")
                return

            # Добавляем сообщения в чат
            user_hash = get_message_hash("user", user_input)
            assistant_hash = get_message_hash("assistant", translated_text)

            if "message_hashes" not in st.session_state:
                st.session_state.message_hashes = set()

            # Добавля��м сообщения в базу данных и отображаем их
            if user_hash not in st.session_state.message_hashes:
                st.session_state.message_hashes.add(user_hash)
                chat_db.add_message("user", user_input)
                with st.chat_message("user", avatar=get_user_profile_image(st.session_state.username)):
                    st.markdown(user_input)

            if assistant_hash not in st.session_state.message_hashes:
                st.session_state.message_hashes.add(assistant_hash)
                chat_db.add_message("assistant", translated_text)
                with st.chat_message("assistant", avatar=assistant_avatar):
                    st.markdown(translated_text)

            # Обновляем количество генераций
            update_remaining_generations(st.session_state.username, -1)
            
            # Вместо прямого изменения session_state используем callback
            st.session_state['_message_input_temp'] = ""  # Временная переменная
            st.rerun()  # Перезагружаем страницу
            
        except requests.exceptions.ConnectionError:
            st.error("Ошибка подключения к серверу. Проверьте подключение к интернету")
        except requests.exceptions.Timeout:
            st.error("Превышено время ожидания ответа")
        except requests.exceptions.RequestException as e:
            st.error(f"Ошибка при отправке запроса: {str(e)}")
        except Exception as e:
            st.error(f"Ошибка: {str(e)}")
            print(f"Детальная информация об ошибке: {type(e).__name__}: {str(e)}")

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
        return f"Оригиналный текст: {text}"

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



def display_assistant_message(content, message_hash):
    with st.chat_message("assistant", avatar=assistant_avatar):
        col1, col2 = st.columns([0.95, 0.05])
        with col1:
            st.write(content)
        with col2:
            if st.button("🗑️", key=f"del_{message_hash}", help="Удалить сообщение"):
                chat_db.delete_message(message_hash)
                # Проверяем наличие хэша перед удалением
                if "message_hashes" in st.session_state and message_hash in st.session_state.message_hashes:
                    st.session_state.message_hashes.remove(message_hash)
                st.rerun()

def display_user_message(content, message_hash):
    user_avatar = get_user_profile_image(st.session_state.username)
    with st.chat_message("user", avatar=user_avatar):
        col1, col2 = st.columns([0.95, 0.05])
        with col1:
            st.write(content)
        with col2:
            if st.button("🗑️", key=f"del_{message_hash}", help="Удалить сообщение"):
                chat_db.delete_message(message_hash)
                # Проверяем наличие хэша перед удалением
                if "message_hashes" in st.session_state and message_hash in st.session_state.message_hashes:
                    st.session_state.message_hashes.remove(message_hash)
                st.rerun()

def main():
    # Инициализируем базу данных чата
    chat_db = ChatDatabase(f"{st.session_state.username}_main_chat")
    
    # Получаем историю чата
    chat_history = chat_db.get_history()
    
    # Инициализируем message_hashes, если его нет
    if "message_hashes" not in st.session_state:
        st.session_state.message_hashes = set()
        # Добавляем все существующие хэши
        for message in chat_history:
            message_hash = get_message_hash(message["role"], message["content"])
            st.session_state.message_hashes.add(message_hash)
    
    # Отображаем историю чата
    for message in chat_history:
        message_hash = get_message_hash(message["role"], message["content"])
        if message["role"] == "assistant":
            display_assistant_message(message["content"], message_hash)
        else:
            display_user_message(message["content"], message_hash)
    
    st.title("Бизнес-Идея")

    # Отображаем количество генераций в начале
    display_remaining_generations()

    # Добаляем кнопк очистки чата
    if "main_clear_chat_confirm" not in st.session_state:
        st.session_state.main_clear_chat_confirm = False

    # Заменяем простую кнопку очистки на кнопку с подтверждением
    if st.sidebar.button(
        "Очистить чат" if not st.session_state.main_clear_chat_confirm else "⚠️ Нажмите еще раз для подтверждения",
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

    # Нстройк контекста
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
            help="Количество последних сообений, которые будут анализироваться для создания контекста."
        )

    # Обновлем настройки в session_state
    st.session_state[MAIN_CHAT_SETTINGS_KEY].update({
        "use_context": use_context,
        "context_messages": context_messages if use_context else 10
    })

    # Создаем контейнер для поля ввода
    input_container = st.container()

    def clear_input():
        st.session_state.message_input = ""

    # Инициализируем значение поля ввода из временной переменной
    if '_message_input_temp' in st.session_state:
        st.session_state.message_input = st.session_state._message_input_temp
        del st.session_state._message_input_temp

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
        cancel_button = st.button("Отменить", key="cancel_request", use_container_width=True)

    # Отправка сообщения при нажатии кнопки или Ctrl+Enter
    if send_button or (user_input and user_input.strip() != "" and st.session_state.get('_last_input') != user_input):
        st.session_state['_last_input'] = user_input
        submit_question()

    st.write(f"Streamlit version: {st.__version__}")

if __name__ == "__main__":
    main()
