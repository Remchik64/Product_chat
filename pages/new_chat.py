import streamlit as st
import requests
import json
import os
from PIL import Image
import hashlib
from utils.utils import verify_user_access, update_remaining_generations
from utils.chat_database import ChatDatabase
from tinydb import TinyDB, Query
from googletrans import Translator
from utils.context_manager import ContextManager
from datetime import datetime
from utils.page_config import setup_pages

# Настройка страницы
st.set_page_config(
    page_title="Личный помощник",
    page_icon="🤖",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Настройка страниц
setup_pages()

# Проверка аутентификации
if "authenticated" not in st.session_state or not st.session_state.authenticated:
    st.warning("Пожалуйста, войдите в систему")
    st.stop()

# Инициализация менеджера контекста
context_manager = ContextManager()

# Инициализация путей для аватаров
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

# Функция для сохранения нового чат-потока
def save_chat_flow(username, flow_id, flow_name=None):
    user = user_db.get(User.username == username)
    if not user:
        return False
        
    chat_flows = user.get('chat_flows', [])
    
    if not flow_name:
        flow_name = f"Чат {len(chat_flows) + 1}"
    else:
        # Убеждаемся, что имя в правильной кодировке
        try:
            # Если строка уже в UTF-8, оставляем как есть
            if not isinstance(flow_name, str):
                flow_name = str(flow_name)
            flow_name = flow_name.encode('utf-8').decode('utf-8')
        except:
            try:
                flow_name = flow_name.encode('cp1251').decode('utf-8')
            except:
                pass
    
    new_flow = {
        'id': flow_id,
        'name': flow_name,
        'created_at': datetime.now().isoformat()
    }
    
    chat_flows.append(new_flow)
    user_db.update({'chat_flows': chat_flows}, User.username == username)
    return True

# Функция для получения списка чат-потоков пользователя
def get_user_chat_flows(username):
    user = user_db.get(User.username == username)
    if not user:
        return []
    
    chat_flows = user.get('chat_flows', [])
    # Исправляем кодировку имен чатов
    for flow in chat_flows:
        try:
            name = flow['name']
            if not isinstance(name, str):
                name = str(name)
            # Если строка уже в UTF-8, оставляем как есть
            flow['name'] = name.encode('utf-8').decode('utf-8')
        except:
            try:
                flow['name'] = name.encode('cp1251').decode('utf-8')
            except:
                pass
    
    return chat_flows

# Функция для очистки истории конкретного чата
def clear_chat_history(username, flow_id):
    chat_db = ChatDatabase(f"{username}_{flow_id}")
    chat_db.clear_history()
    if "message_hashes" in st.session_state:
        del st.session_state.message_hashes
    st.rerun()

# Добавьте эту функцию после функции clear_chat_history

def delete_chat_flow(username, flow_id):
    # Получаем текущего пользователя
    user = user_db.get(User.username == username)
    if not user:
        return False
    
    # Получаем список чатов
    chat_flows = user.get('chat_flows', [])
    
    # Удаляем чат из списка
    chat_flows = [flow for flow in chat_flows if flow['id'] != flow_id]
    
    # Обновляем список чатов в базе данных
    user_db.update({'chat_flows': chat_flows}, User.username == username)
    
    # Удаляем историю чата
    chat_db = ChatDatabase(f"{username}_{flow_id}")
    chat_db.clear_history()
    
    return True

# Инициализация базы данных
user_db = TinyDB('user_database.json')
User = Query()

st.title("Личный помощник")

# Отображение оставшихся генераций
user = user_db.get(User.username == st.session_state.username)
if user:
    remaining_generations = user.get('remaining_generations', 0)
    st.sidebar.metric("Осталось генераций:", remaining_generations)
    
    if remaining_generations <= 0:
        st.error("У вас закончились генерации. Пожалуйста, активируйте новый токен.")
        st.stop()

# Ключ для хранения настроек нового чата
NEW_CHAT_SETTINGS_KEY = "new_chat_context_settings"

# Настройки контекста в боковой панели
st.sidebar.title("Настройки контекста для истории")

# Инициализация настроек в session_state если их нет
if NEW_CHAT_SETTINGS_KEY not in st.session_state:
    st.session_state[NEW_CHAT_SETTINGS_KEY] = {
        "use_context": True,
        "context_messages": 10
    }

# Настройки контекста для нового чата
use_context = st.sidebar.checkbox(
    "Использовать контекст истории",
    value=st.session_state[NEW_CHAT_SETTINGS_KEY]["use_context"],
    key=f"{NEW_CHAT_SETTINGS_KEY}_use_context"
)

if use_context:
    context_messages = st.sidebar.slider(
        "Количество сообщений для анализа",
        min_value=3,
        max_value=30,
        value=st.session_state[NEW_CHAT_SETTINGS_KEY]["context_messages"],
        key=f"{NEW_CHAT_SETTINGS_KEY}_slider",
        help="Количество последних сообщений, которые будут анализироваться для создания контекста"
    )
# Обновляем настройки в session_state
st.session_state[NEW_CHAT_SETTINGS_KEY].update({
    "use_context": use_context,
    "context_messages": context_messages if use_context else 10
})

# Добавляем разделитель
st.sidebar.markdown("---")

# Управление чат-потоками в боковой панели
st.sidebar.title("Управление чат-потоками")

# Выбор существующего чат-потока
chat_flows = get_user_chat_flows(st.session_state.username)
if chat_flows:
    flow_names = [flow['name'] for flow in chat_flows]
    
    # Определяем текущий индекс
    current_index = 0
    if 'current_chat_flow' in st.session_state:
        try:
            current_flow_name = st.session_state.current_chat_flow['name']
            if current_flow_name in flow_names:
                current_index = flow_names.index(current_flow_name)
        except:
            current_index = 0
    
    selected_flow_name = st.sidebar.radio(
        "Выберите чат:",
        flow_names,
        index=current_index
    )
    
    selected_flow = next(
        (flow for flow in chat_flows if flow['name'] == selected_flow_name),
        chat_flows[0]
    )
    
    st.session_state.current_chat_flow = selected_flow
    chat_db = ChatDatabase(f"{st.session_state.username}_{selected_flow['id']}")

# Создание нового чат-потока
st.sidebar.markdown("---")
with st.sidebar.expander("Создать новый чат"):
    new_flow_name = st.text_input("Название чата:")
    new_flow_id = st.text_input(
        "ID чат-потока:",
        help="Например: 28d13206-3a4d-4ef8-80e6-50b671b5766c"
    )
    
    if st.button("Создать") and new_flow_id:
        if save_chat_flow(st.session_state.username, new_flow_id, new_flow_name):
            st.session_state.current_chat_flow = {
                'id': new_flow_id,
                'name': new_flow_name or f"Чат {len(chat_flows) + 1}"
            }
            chat_db = ChatDatabase(f"{st.session_state.username}_{new_flow_id}")
            st.success("Новый чат создан!")
            st.rerun()

# Кнопка очистки текущего чата
if st.sidebar.button("Очистить текущий чат"):
    if 'current_chat_flow' in st.session_state:
        clear_chat_history(st.session_state.username, st.session_state.current_chat_flow['id'])

# Кнопка удаления текущего чта
if st.sidebar.button("🗑️ Удалить текущий чат", type="secondary", key="sidebar_delete_chat"):
    if 'current_chat_flow' in st.session_state:
        if delete_chat_flow(st.session_state.username, st.session_state.current_chat_flow['id']):
            st.sidebar.success("Чат успешно удален!")
            # Очищаем текущий чат из session_state
            if 'current_chat_flow' in st.session_state:
                del st.session_state.current_chat_flow
            if 'message_hashes' in st.session_state:
                del st.session_state.message_hashes
            st.rerun()
        else:
            st.sidebar.error("Ошибка при удалении чата")

# Проверяем наличие текущего чат-потока
if 'current_chat_flow' not in st.session_state:
    st.info("Создайте новый чат для начала общения")
    st.stop()

# Отображение текущего чата
if 'current_chat_flow' in st.session_state:
    chat_name = st.session_state.current_chat_flow['name']
    try:
        if not isinstance(chat_name, str):
            chat_name = str(chat_name)
        # Если строка уже в UTF-8, оставляем как есть
        chat_name = chat_name.encode('utf-8').decode('utf-8')
    except:
        try:
            chat_name = chat_name.encode('cp1251').decode('utf-8')
        except:
            pass
    
    st.markdown(f"### 💬 {chat_name}")
    st.markdown("---")

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
        st.error("У вас закончились генераций. Пжалуйста, активируйте новый токен.")
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
    
    # Получаем и отображаем ответ от ассистента
    with st.chat_message("assistant", avatar=assistant_avatar):
        with st.spinner('Получаем ответ...'):
            try:
                # Получаем контекст для сообщения
                if use_context:
                    enhanced_message = context_manager.get_context(
                        st.session_state.username,
                        user_input,
                        last_n_messages=context_messages
                    )
                else:
                    enhanced_message = user_input
                
                # Формируем URL с использованием ID текущего чата
                chat_id = st.session_state.current_chat_flow['id']
                api_url = f"{st.secrets['flowise']['base_url']}/api/v1/prediction/{chat_id}"
                
                payload = {
                    "question": enhanced_message
                }
                
                response = requests.post(
                    api_url,
                    json=payload,
                    timeout=100
                )
                
                if response.status_code != 200:
                    st.error("Ошибка при получении ответа от сервера")
                    return
                
                try:
                    output = response.json()
                except json.JSONDecodeError:
                    st.error("Ошибка при обработке ответа")
                    return
                    
                response_text = output.get('text', '')
                
                if not response_text:
                    st.warning("Получен пустой ответ")
                    return
                
                # Переводим ответ
                translated_text = translate_text(response_text)
                
                # Отображаем и сохраняем ответ
                st.markdown(translated_text)
                
                assistant_hash = get_message_hash("assistant", translated_text)
                if assistant_hash not in st.session_state.message_hashes:
                    st.session_state.message_hashes.add(assistant_hash)
                    chat_db.add_message("assistant", translated_text)
                
                # Обновляем количество генераций
                update_remaining_generations(st.session_state.username, -1)
                st.rerun()
                
            except requests.exceptions.ConnectionError:
                st.error("Ошибка подключения к серверу. Проверьте подключение к интернету")
            except requests.exceptions.Timeout:
                st.error("Превышено время ожидания ответа")
            except requests.exceptions.RequestException:
                st.error("Ошибка при отправке запроса")
            except Exception:
                st.error("Произошла непредвиденная ошибка")

# Создаем контейнер для поля ввода
input_container = st.container()

# Поле ввода с возможностью растягивания
user_input = st.text_area(
    "Введите ваше сообщение",
    height=100,
    key="message_input",
    placeholder="Введите текст сообщения здесь..."  
)

# Кнопка отправки внизу
send_button = st.button("Отправить", key="send_message", use_container_width=True)

# Отправка сообщения при нажатии кнопки или Ctrl+Enter
if send_button or (user_input and user_input.strip() != "" and st.session_state.get('_last_input') != user_input):
    st.session_state['_last_input'] = user_input
    submit_message(user_input)