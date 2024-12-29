import streamlit as st
import requests
from time import sleep
import hashlib
import os
from PIL import Image
from googletrans import Translator
import time

# Настройка заголовка страницы
st.set_page_config(
    page_title="Вопросы и ответы",
    page_icon="💬",
    layout="wide"
)

# Максимальное количество ответов от API
MAX_API_RESPONSES = 5

# Папка с изображениями профиля
PROFILE_IMAGES_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', 'profile_images'))
ASSISTANT_ICON_PATH = os.path.join(PROFILE_IMAGES_DIR, 'assistant_icon.png')

# Загрузка аватара ассистента
if os.path.exists(ASSISTANT_ICON_PATH):
    try:
        assistant_avatar = Image.open(ASSISTANT_ICON_PATH)
    except Exception as e:
        st.error(f"Ошибка при открытии изображения ассистента: {e}")
        assistant_avatar = "🤖"
else:
    assistant_avatar = "🤖"

def get_user_profile_image(username):
    """Получение изображения профиля пользователя"""
    for ext in ['png', 'jpg', 'jpeg']:
        image_path = os.path.join(PROFILE_IMAGES_DIR, f"{username}.{ext}")
        if os.path.exists(image_path):
            try:
                return Image.open(image_path)
            except Exception as e:
                st.error(f"Ошибка при открытии изображения {image_path}: {e}")
                return "👤"
    return "👤"

def get_user_chat_id():
    """Получение уникального идентификатора чата для пользователя"""
    user_email = st.session_state.get("email", "")
    if not user_email:
        return "default-chat-session"
    
    # Создаем уникальный chat_id на основе email пользователя
    chat_id = hashlib.md5(user_email.encode()).hexdigest()
    return f"chat-{chat_id}"

def get_user_messages_key():
    """Получение ключа для хранения сообщений конкретного пользователя"""
    user_email = st.session_state.get("email", "")
    if not user_email:
        return "messages"
    return f"messages_{hashlib.md5(user_email.encode()).hexdigest()}"

def get_api_url():
    """Получение URL API из секретов"""
    try:
        # Проверяем наличие необходимых параметров
        if not hasattr(st.secrets, 'flowise'):
            st.error("Секция 'flowise' не найдена в secrets.toml")
            return None
            
        if not hasattr(st.secrets.flowise, 'api_base_url'):
            st.error("Параметр 'api_base_url' не найден в секции flowise")
            return None
            
        if not hasattr(st.secrets.flowise, 'simple_chat_id'):
            st.error("Параметр 'simple_chat_id' не найден в секции flowise")
            return None

        # Получаем базовый URL API и ID чата из секретов
        api_base_url = st.secrets.flowise.api_base_url
        chat_id = st.secrets.flowise.simple_chat_id
        
        # Выводим отладочную информацию
        print(f"API Base URL: {api_base_url}")
        print(f"Chat ID: {chat_id}")
        
        # Формируем полный URL
        full_url = f"{api_base_url}/{chat_id}"
        print(f"Full URL: {full_url}")
        
        return full_url
    except Exception as e:
        st.error(f"Ошибка при получении URL API: {str(e)}")
        # Выводим дополнительную отладочную информацию
        print(f"Доступные секции в secrets: {dir(st.secrets)}")
        if hasattr(st.secrets, 'flowise'):
            print(f"Доступные параметры в flowise: {dir(st.secrets.flowise)}")
        return None

def query(question):
    """Отправка запроса к API"""
    try:
        api_url = get_api_url()
        if not api_url:
            st.error("API URL не найден в конфигурации")
            return None

        # Обновленный payload с корректными параметрами
        payload = {
            "question": question,
            "overrideConfig": {
                "temperature": 0.7,
                "modelName": "mistral",
                "maxTokens": 2000,
                "systemMessage": "Вы - полезный ассистент. Отвечайте на русском языке."
            }
        }
        
        # Добавляем историю сообщений, если она есть
        messages_key = get_user_messages_key()
        if messages_key in st.session_state:
            payload["history"] = st.session_state[messages_key]
        
        # Обновленные заголовки
        headers = {
            "Content-Type": "application/json",
            "Accept": "application/json"
        }

        # Пробуем отправить запрос с повторными попытками
        for attempt in range(3):  # 3 попытки
            try:
                response = requests.post(
                    api_url, 
                    json=payload, 
                    headers=headers, 
                    timeout=60
                )
                
                # Проверяем статус ответа
                if response.status_code == 200:
                    return response.json()
                elif response.status_code == 500:
                    # Если это последняя попытка
                    if attempt == 2:
                        st.error(f"Сервис временно недоступен. Пожалуйста, попробуйте позже.")
                        return None
                    # Если есть еще попытки, ждем и пробуем снова
                    time.sleep(2)
                    continue
                else:
                    st.error(f"Неожиданный ответ сервера (код {response.status_code})")
                    return None
                    
            except requests.exceptions.Timeout:
                if attempt == 2:
                    st.error("Превышено время ожидания ответа")
                    return None
                time.sleep(2)
                continue
                
            except requests.exceptions.RequestException as e:
                if attempt == 2:
                    st.error(f"Ошибка сети: {str(e)}")
                    return None
                time.sleep(2)
                continue
            
    except Exception as e:
        st.error(f"Общая ошибка: {str(e)}")
        return None

    return None

def count_api_responses():
    """Подсчет количества ответов от API в истории"""
    messages_key = get_user_messages_key()
    return sum(1 for msg in st.session_state[messages_key] if msg["role"] == "assistant")

def sidebar_content():
    """Содержимое боковой панели"""
    with st.sidebar:
        # Добавляем постоянный стиль для кнопки
        st.markdown("""
            <style>
            div[data-testid="stButton"] > button[kind="secondary"] {
                background: none;
                color: inherit;
                border: 1px solid;
                padding: 6px 12px;
                font-size: 14px;
                border-radius: 4px;
                margin: 0;
                width: 100%;
            }
            </style>
        """, unsafe_allow_html=True)
        
        st.header("Управление чатом")
        
        # Отображение информации о пользователе
        if st.session_state.get("email"):
            user_avatar = get_user_profile_image(st.session_state.get("username", ""))
            col1, col2 = st.columns([1, 3])
            with col1:
                st.image(user_avatar, width=50)
            with col2:
                st.info(f"Пользователь: {st.session_state.get('email')}")
        
        # Отображение информации о лимите
        responses_count = count_api_responses()
        st.write(f"Использовано ответов: {responses_count}/{MAX_API_RESPONSES}")
        
        # Индикатор прогресса
        progress = responses_count / MAX_API_RESPONSES
        st.progress(progress)
        
        # Кнопка очистки истории с постоянным стилем
        if st.button("Очистить историю чата", 
                     use_container_width=True, 
                     type="secondary",
                     key="clear_history_button"):
            messages_key = get_user_messages_key()
            st.session_state[messages_key] = []
            st.rerun()

def translate_text(text, target_lang='ru'):
    """
    Переводит текст на указанный язык
    target_lang: 'ru' для русского или 'en' для английского
    """
    try:
        translator = Translator()
        
        if text is None or not isinstance(text, str) or text.strip() == '':
            return "Пустой текст для перевода"
            
        # Определяем язык текста
        detected_lang = translator.detect(text).lang
        
        # Если текст уже на целевом языке, меняем язык перевода
        if detected_lang == target_lang:
            target_lang = 'en' if target_lang == 'ru' else 'ru'
            
        translation = translator.translate(text, dest=target_lang)
        if translation and hasattr(translation, 'text') and translation.text:
            return translation.text
            
        return f"Ошибка перевода: некорректный ответ от переводчика"
        
    except Exception as e:
        st.error(f"Ошибка при переводе: {str(e)}")
        return text

def display_message_with_translation(message):
    """Отображает сообщение с кнопкой перевода"""
    message_hash = get_message_hash(message["role"], message["content"])
    avatar = assistant_avatar if message["role"] == "assistant" else get_user_profile_image(st.session_state.get("username", ""))
    
    # Добавляем уникальный идентификатор сообщения
    if 'message_ids' not in st.session_state:
        st.session_state.message_ids = {}
    
    if message_hash not in st.session_state.message_ids:
        st.session_state.message_ids[message_hash] = len(st.session_state.message_ids)
    
    # Инициализируем состояние перевода для этого сообщения
    translation_key = f"translation_state_{message_hash}"
    if translation_key not in st.session_state:
        st.session_state[translation_key] = {
            "is_translated": False,
            "original_text": message["content"],
            "translated_text": None
        }
    
    with st.chat_message(message["role"], avatar=avatar):
        cols = st.columns([0.9, 0.1])
        
        with cols[0]:
            message_placeholder = st.empty()
            current_state = st.session_state[translation_key]
            
            if current_state["is_translated"] and current_state["translated_text"]:
                message_placeholder.markdown(current_state["translated_text"])
            else:
                message_placeholder.markdown(current_state["original_text"])
            
        with cols[1]:
            st.markdown(
                """
                <style>
                div.stButton > button {
                    width: 40px;
                    height: 40px;
                    padding: 0px;
                    border-radius: 50%;
                }
                </style>
                """,
                unsafe_allow_html=True
            )
            # Используем комбинацию хэша, ID сообщения и роли для уникального ключа
            button_key = f"translate_{message_hash}_{st.session_state.message_ids[message_hash]}_{message['role']}"
            if st.button("🔄", key=button_key, help="Перевести сообщение"):
                current_state = st.session_state[translation_key]
                
                if current_state["is_translated"]:
                    message_placeholder.markdown(current_state["original_text"])
                    st.session_state[translation_key]["is_translated"] = False
                else:
                    if not current_state["translated_text"]:
                        translated_text = translate_text(current_state["original_text"])
                        st.session_state[translation_key]["translated_text"] = translated_text
                    
                    message_placeholder.markdown(st.session_state[translation_key]["translated_text"])
                    st.session_state[translation_key]["is_translated"] = True

def get_message_hash(role, content):
    """Создает уникальный хэш для сообщения"""
    return hashlib.md5(f"{role}:{content}".encode()).hexdigest()

def main():
    # Проверка аутентификации
    if not st.session_state.get("authenticated", False):
        st.warning("Пожалуйста, войдите в систему")
        return

    # Проверка наличия API URL
    if not get_api_url():
        st.error("Ошибка конфигурации: API URL не настроен")
        return

    # Основной заголовок
    st.title("💬 Вопросы и ответы")
    st.markdown("---")

    # Получаем ключ для сообщений конкретного пользователя
    messages_key = get_user_messages_key()

    # Инициализация истории чата в session state для конкретного пользователя
    if messages_key not in st.session_state:
        st.session_state[messages_key] = []
        
    # Отображаем боковую панель
    sidebar_content()

    # Отображение истории сообщений
    for message in st.session_state[messages_key]:
        display_message_with_translation(message)

    # Проверяем лимит ответов
    if count_api_responses() >= MAX_API_RESPONSES:
        st.warning("⚠️ Достигнут лимит ответов. Пожалуйста, очистите историю чата для продолжения общения.")
        return

    # Поле ввода сообщения
    if prompt := st.chat_input("Введите ваше сообщение..."):
        # Добавление сообщения пользователя
        st.session_state[messages_key].append({"role": "user", "content": prompt})
        display_message_with_translation({"role": "user", "content": prompt})

        # Получение ответа от API
        with st.spinner("Обработка запроса..."):
            response = query(prompt)
            
            if response:
                full_response = response.get("text", "Извините, произошла ошибка при получении ответа")
                # Добавление ответа ассистента в историю
                assistant_message = {"role": "assistant", "content": full_response}
                st.session_state[messages_key].append(assistant_message)
                display_message_with_translation(assistant_message)
            else:
                st.error("Произошла ошибка при получении ответа")

if __name__ == "__main__":
    main() 