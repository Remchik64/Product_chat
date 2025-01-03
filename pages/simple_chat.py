import streamlit as st
import requests
from time import sleep
import hashlib
import os
from PIL import Image
from googletrans import Translator

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
    """Получение изображения профиля польз��вателя"""
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
    """Получение URL API OpenRouter"""
    return "https://openrouter.ai/api/v1/chat/completions"

def query(question):
    """Отправка запроса к API"""
    try:
        api_url = get_api_url()
        if not api_url:
            st.error("API URL не найден в конфигурации")
            return None

        # Обновленные заголовки
        headers = {
            "Authorization": f"Bearer {st.secrets['openrouter']['api_key']}",
            "HTTP-Referer": "https://github.com/cursor-ai",
            "X-Title": "Cursor AI Assistant",
            "Content-Type": "application/json"
        }

        # Обновляем URL для OpenRouter API
        api_url = "https://openrouter.ai/api/v1/chat/completions"
        
        # Обновленный payload для OpenRouter API
        payload = {
            "model": "google/gemini-flash-1.5",
            "messages": [
                {
                    "role": "system",
                    "content": "Вы - полезный ассистент. Отвечайте на русском языке."
                },
                {
                    "role": "user",
                    "content": question
                }
            ],
            "max_tokens": 2048,
            "temperature": 0.7,
            "top_p": 0.9
        }
        
        # Отправляем запрос с увеличенным timeout
        response = requests.post(
            api_url, 
            json=payload, 
            headers=headers, 
            timeout=60
        )
        
        if response.status_code == 200:
            response_data = response.json()
            if 'choices' in response_data and len(response_data['choices']) > 0:
                assistant_message = response_data['choices'][0]['message']['content']
                return {
                    "text": assistant_message,
                    "sourceDocuments": []
                }
            else:
                st.error("Неожиданный формат ответа от API")
                return None
        else:
            st.error(f"Ошибка API (код {response.status_code}): {response.text}")
            return None
            
    except Exception as e:
        st.error(f"Ошибка при отправке запроса: {str(e)}")
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

def translate_text(text, target_lang='ru'):
    """
    Переводит текст на указанный я��ык
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
        
        # Создаем placeholder для сообщения в первой колонке
        with cols[0]:
            message_placeholder = st.empty()
            current_state = st.session_state[translation_key]
            
            # Показываем текущий текст в зависимости от состояния перевода
            if current_state["is_translated"] and current_state["translated_text"]:
                message_placeholder.markdown(current_state["translated_text"])
            else:
                message_placeholder.markdown(current_state["original_text"])
            
        # Кнопка перевода во второй колонке
        with cols[1]:
            if st.button("🔄", key=f"translate_{message_hash}", help="Перевести сообщение"):
                current_state = st.session_state[translation_key]
                
                if current_state["is_translated"]:
                    # Возвращаемся к оригинальному тексту
                    message_placeholder.markdown(current_state["original_text"])
                    st.session_state[translation_key]["is_translated"] = False
                else:
                    # Переводим текст
                    if not current_state["translated_text"]:
                        translated_text = translate_text(current_state["original_text"])
                        st.session_state[translation_key]["translated_text"] = translated_text
                    
                    message_placeholder.markdown(st.session_state[translation_key]["translated_text"])
                    st.session_state[translation_key]["is_translated"] = True

def get_message_hash(role, content):
    """Создает уникальный хэш для сообщения"""
    return hashlib.md5(f"{role}:{content}".encode()).hexdigest()

def main():
    """Основная функция приложения"""
    # Инциализация ключа для сообщений
    messages_key = get_user_messages_key()
    if messages_key not in st.session_state:
        st.session_state[messages_key] = []
    
    # Отображение боковой панели
    sidebar_content()
    
    # Отображение заголовка
    st.title("💬 Бесплатный чат")
    
    # Отображение истории сообщений
    for message in st.session_state[messages_key]:
        display_message_with_translation(message)
    
    # Проверяем лимит ответов
    if count_api_responses() >= MAX_API_RESPONSES:
        st.warning("⚠️ Достигнут лимит ответов. Пожалуйста, очистите историю чата для продолжения общения.")
        return
    
    # Поле ввода сообщения
    user_input = st.chat_input("Введите ваш вопрос...")
    
    if user_input:
        # Добавляем сообщение пользователя в историю
        user_message = {"role": "user", "content": user_input}
        st.session_state[messages_key].append(user_message)
        
        # Получаем ответ от API
        with st.spinner("Думаю..."):
            response = query(user_input)
            
            if response:
                full_response = response.get("text", "Извините, произошла ошибка при получении ответа")
                # Добавление ответа ассистента в историю
                assistant_message = {"role": "assistant", "content": full_response}
                st.session_state[messages_key].append(assistant_message)
                st.rerun()  # Перезагружаем страницу для отображения нового сообщения
            else:
                st.error("Не удалось получить ответ от API")

if __name__ == "__main__":
    main() 