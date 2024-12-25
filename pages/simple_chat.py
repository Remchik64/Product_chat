import streamlit as st
import requests
from time import sleep
import hashlib
import os
from PIL import Image

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
        # Получаем полный URL API
        api_url = get_api_url()
        if not api_url:
            st.error("API URL не найден в конфигурации")
            return None

        # Формируем payload для Flowise с дополнительными параметрами
        payload = {
            "question": question,
            "overrideConfig": {
                "temperature": 0.7,
                "modelName": "mistral",  # Указываем модель
                "maxTokens": 2000,       # Максимальное количество токенов
                "systemMessage": "Вы - полезный ассистент, который отвечает на русском языке."
            }
        }
        
        # Добавляем заголовки
        headers = {
            "Content-Type": "application/json",
            "Accept": "application/json"
        }

        # Добавляем API ключ Together AI
        if "together" in st.secrets and "api_key" in st.secrets["together"]:
            headers["Authorization"] = f"Bearer {st.secrets.together.api_key}"
        
        # Отладочная информация
        print(f"Sending request to: {api_url}")
        print(f"Payload: {payload}")
        print(f"Headers: {headers}")
        
        # Отправляем запрос с увеличенным timeout
        response = requests.post(api_url, json=payload, headers=headers, timeout=60)
        
        # Подробная обработка ошибок
        if response.status_code == 500:
            error_data = response.json()
            error_message = error_data.get('message', 'Unknown error')
            st.error(f"Ошибка сервера: {error_message}")
            print(f"Server error details: {error_data}")
            return None
            
        if response.status_code != 200:
            st.error(f"Ошибка API (код {response.status_code}): {response.text}")
            return None
            
        try:
            result = response.json()
            if not result or 'text' not in result:
                st.error("Получен некорректный ответ от API")
                print(f"API response: {result}")
                return None
            return result
        except Exception as e:
            st.error(f"Ошибка при обработке ответа: {str(e)}")
            print(f"Response content: {response.text}")
            return None
            
    except requests.exceptions.RequestException as e:
        st.error(f"Ошибка сети при отправке запроса: {str(e)}")
        print(f"Request error details: {str(e)}")
        return None
    except Exception as e:
        st.error(f"Неожиданная ошибка: {str(e)}")
        print(f"Unexpected error details: {str(e)}")
        return None

def count_api_responses():
    """Подсчет количества ответов от API в истории"""
    messages_key = get_user_messages_key()
    return sum(1 for msg in st.session_state[messages_key] if msg["role"] == "assistant")

def sidebar_content():
    """Содержимое боковой панели"""
    with st.sidebar:
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
        
        # Кнопка очистки истории
        if st.button("Очистить историю чата", use_container_width=True):
            messages_key = get_user_messages_key()
            st.session_state[messages_key] = []
            st.rerun()

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
    st.title("💬 Простой чат")
    st.markdown("---")

    # Получаем ключ для сообщений конкретного пользователя
    messages_key = get_user_messages_key()

    # Инициализация истории чата в session state для конкретного пользователя
    if messages_key not in st.session_state:
        st.session_state[messages_key] = []
        
    # Отображаем боковую панель
    sidebar_content()

    # Отображение истории сообщений с аватарами
    for message in st.session_state[messages_key]:
        if message["role"] == "assistant":
            with st.chat_message("assistant", avatar=assistant_avatar):
                st.markdown(message["content"])
        else:
            user_avatar = get_user_profile_image(st.session_state.get("username", ""))
            with st.chat_message("user", avatar=user_avatar):
                st.markdown(message["content"])

    # Проверяем лимит ответов
    if count_api_responses() >= MAX_API_RESPONSES:
        st.warning("⚠️ Достигнут лимит ответов. Пожалуйста, очистите историю чата для продолжения общения.")
        return

    # Поле ввода сообщения
    if prompt := st.chat_input("Введите ваше сообщение..."):
        # Добавление сообщения пользователя
        st.session_state[messages_key].append({"role": "user", "content": prompt})
        user_avatar = get_user_profile_image(st.session_state.get("username", ""))
        with st.chat_message("user", avatar=user_avatar):
            st.markdown(prompt)

        # Получение ответа от API
        with st.chat_message("assistant", avatar=assistant_avatar):
            message_placeholder = st.empty()
            with st.spinner("Обработка запроса..."):
                response = query(prompt)
                
                if response:
                    full_response = response.get("text", "Извините, произошла ошибка при получении ответа")
                    message_placeholder.markdown(full_response)
                    # Добавление ответа ассистента в историю
                    st.session_state[messages_key].append({"role": "assistant", "content": full_response})
                else:
                    message_placeholder.markdown("Произошла ошибка при получении ответа")

if __name__ == "__main__":
    main() 