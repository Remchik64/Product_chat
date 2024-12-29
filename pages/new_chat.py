import streamlit as st
import requests
import json
import os
from PIL import Image
import hashlib
from utils.utils import verify_user_access, update_remaining_generations, get_data_file_path
from utils.chat_database import ChatDatabase
from tinydb import TinyDB, Query
from googletrans import Translator
from utils.context_manager import ContextManager
from datetime import datetime
from utils.page_config import setup_pages
import time
from utils.translation import translate_text, display_message_with_translation

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

# Инициализация менеджера контекста с проверкой
context_manager = ContextManager()
# Проверка наличия ключа OpenRouter API
if "openrouter" not in st.secrets or "api_key" not in st.secrets["openrouter"]:
    st.error("Ошибка: API ключ OpenRouter не настроен. Пожалуйста, обратитесь к администратору.")
    st.stop()

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

def get_message_hash(role, content):
    """Создает уникальный хэш для сообщения"""
    return hashlib.md5(f"{role}:{content}".encode()).hexdigest()

def get_user_profile_image(username):
    for ext in ['png', 'jpg', 'jpeg']:
        image_path = os.path.join(PROFILE_IMAGES_DIR, f"{username}.{ext}")
        if os.path.exists(image_path):
            try:
                return Image.open(image_path)
            except Exception as e:
                return "👤"
    return "👤"

def display_message(message, role):
    """Отображает сообщение с кнопками управления"""
    message_hash = get_message_hash(role, message["content"])
    avatar = assistant_avatar if role == "assistant" else get_user_profile_image(st.session_state.username)
    
    # Добавляем уникальный идентификатор для каждого сообщения в текущем чате
    chat_id = st.session_state.current_chat_flow['id']
    message_key = f"{chat_id}_{message_hash}"
    
    if 'message_ids' not in st.session_state:
        st.session_state.message_ids = {}
    
    if message_key not in st.session_state.message_ids:
        st.session_state.message_ids[message_key] = len(st.session_state.message_ids)
    
    # Добавляем номер сообщения
    if 'message_counter' not in st.session_state:
        st.session_state.message_counter = 1
    else:
        st.session_state.message_counter += 1
    
    # Добавляем номер сообщения в конец контента
    message_with_number = {
        "role": message["role"],
        "content": f"{message['content']}\n\n*Сообщение #{st.session_state.message_counter}*"
    }
    
    # Создаем уникальный ключ для кнопки перевода
    button_key = f"translate_{message_key}_{st.session_state.message_ids[message_key]}_{role}"
    
    # Используем функцию из utils.translation с пронумерованным сообщением
    if display_message_with_translation(message_with_number, message_hash, avatar, role, button_key):
        current_chat_db = ChatDatabase(f"{st.session_state.username}_{st.session_state.current_chat_flow['id']}")
        current_chat_db.delete_message(message_hash)
        if "message_hashes" in st.session_state:
            if message_hash in st.session_state.message_hashes:
                st.session_state.message_hashes.remove(message_hash)
            translation_key = f"translation_{message_hash}"
            if translation_key in st.session_state:
                del st.session_state[translation_key]
        st.rerun()

# Функция для сохранения нового чат-потока
def save_chat_flow(username, flow_id, flow_name=None):
    user = user_db.get(User.username == username)
    if not user:
        return False
        
    chat_flows = user.get('chat_flows', [])
    
    if not flow_name:
        flow_name = f"Чат {len(chat_flows) + 1}"
    else:
        try:
            if not isinstance(flow_name, str):
                flow_name = str(flow_name)
            flow_name = flow_name.encode('utf-8').decode('utf-8')
        except:
            try:
                flow_name = flow_name.encode('cp1251').decode('utf-8')
            except:
                pass
    
    # Добавляем настройки контекста при создании чата
    new_flow = {
        'id': flow_id,
        'name': flow_name,
        'created_at': datetime.now().isoformat(),
        'context_settings': {
            "use_context": True,
            "context_range": (1, 10)
        }
    }
    
    chat_flows.append(new_flow)
    user_db.update({'chat_flows': chat_flows}, User.username == username)
    return True

# Функция для обновления настроек контекста чата
def update_chat_context_settings(username, flow_id, settings):
    user = user_db.get(User.username == username)
    if not user:
        return False
    
    chat_flows = user.get('chat_flows', [])
    for flow in chat_flows:
        if flow['id'] == flow_id:
            flow['context_settings'] = settings
            user_db.update({'chat_flows': chat_flows}, User.username == username)
            return True
    return False

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
    """Очистка истории конкретного чата"""
    chat_db = ChatDatabase(f"{username}_{flow_id}")
    chat_db.clear_history()
    
    # Очищаем все связанные состояния
    keys_to_delete = []
    for key in st.session_state.keys():
        # Удаляем все состояния, связанные с сообщениями
        if any(key.startswith(prefix) for prefix in [
            "message_hashes",
            "message_counter",
            "message_ids",
            "translation_state_",
            "translation_states",
            "_last_input"
        ]):
            keys_to_delete.append(key)
    
    # Удаляем все найденные ключи
    for key in keys_to_delete:
        del st.session_state[key]
    
    # Принудительно сбрасываем счетчик сообщений
    st.session_state.message_counter = 0
    
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
user_db = TinyDB(get_data_file_path('user_database.json'))
User = Query()

st.title("Личный помощник")

# Отображение оставшихся генераций
user = user_db.get(User.username == st.session_state.username)
if user:
    remaining_generations = user.get('remaining_generations', 0)
    st.sidebar.metric("Осталось генераций:", remaining_generations)
    
    if remaining_generations <= 0:
        st.error("У вас закончились генераций. Пожалуйста, активируйте новый токен.")
        st.stop()

# Ключ для хранения настроек нового чата
NEW_CHAT_SETTINGS_KEY = "new_chat_context_settings"

# Настройки контекста в боковой панели
st.sidebar.title("Настройки контекста для истории")

# Инициализация настроек в session_state если их нет
if NEW_CHAT_SETTINGS_KEY not in st.session_state:
    st.session_state[NEW_CHAT_SETTINGS_KEY] = {
        "use_context": True,
        "context_range": (1, 10)  # Устанавливаем начальное значение диапазона
    }

# Настройки контекста
use_context = st.sidebar.checkbox(
    "Использовать контекст истории",
    value=st.session_state[NEW_CHAT_SETTINGS_KEY]["use_context"],
    key=f"{NEW_CHAT_SETTINGS_KEY}_use_context"
)

if use_context:
    # Получаем количество сообщений в текущем чате
    if 'current_chat_flow' in st.session_state:  # Проверяем наличие текущего чата
        current_chat_db = ChatDatabase(f"{st.session_state.username}_{st.session_state.current_chat_flow['id']}")
        history = current_chat_db.get_history()
        max_messages = len(history) if history else 60
        
        # Получаем текущий диапазон из session_state или используем значение по умолчанию
        current_range = st.session_state[NEW_CHAT_SETTINGS_KEY].get("context_range", (1, 10))
        
        context_range = st.sidebar.slider(
            "Диапазон сообщений для анализа:",
            min_value=1,
            max_value=max(30, max_messages),
            value=current_range,  # Используем текущее значение
            step=1,
            key=f"{NEW_CHAT_SETTINGS_KEY}_range",
            help="Выберите диапазон сообщений для анализа контекста"
        )

        # Обновляем настройки в session_state
        st.session_state[NEW_CHAT_SETTINGS_KEY].update({
            "use_context": use_context,
            "context_range": context_range
        })
    else:
        st.sidebar.warning("Создайте новый чат для настройки контекста")
else:
    # Если контекст выключен, сохраняем значение по умолчанию
    st.session_state[NEW_CHAT_SETTINGS_KEY].update({
        "use_context": False,
        "context_range": (1, 10)
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
    
    # Проверяем, изменился ли выбранный чат
    if ('current_chat_flow' not in st.session_state or 
        st.session_state.current_chat_flow['id'] != selected_flow['id']):
        # Обноляем текущий чат
        st.session_state.current_chat_flow = selected_flow
        # Очищаем историю сообщений предыдущего чата
        if "message_hashes" in st.session_state:
            del st.session_state.message_hashes
        # Перезагружаем страницу для отображения новой истории
        st.rerun()

# Создание нового чат-потока
st.sidebar.markdown("---")
with st.sidebar.expander("Создать новый чат"):
    new_flow_name = st.text_input("Название чата:")
    new_flow_id = st.text_input(
        "ID чат-потока:",
        help="Введите например: 28d13206-3a4d-4ef8-80e6-50b671b5766c или закжите сборку чата в https://t.me/startintellect"
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

# Добавляем состояния подтверждения с уникальными ключами
if "new_chat_clear_confirm" not in st.session_state:  # Изменили ключ
    st.session_state.new_chat_clear_confirm = False   # Изменили ключ
if "new_chat_delete_confirm" not in st.session_state: # Изменили ключ
    st.session_state.new_chat_delete_confirm = False  # Изменили ключ

# Заменяем кнопку очистки чата
if st.sidebar.button(
    "Очистить текущий чат" if not st.session_state.new_chat_clear_confirm else "⚠️ Нажмите еще раз для подтверждения",
    type="secondary" if not st.session_state.new_chat_clear_confirm else "primary",
    key="new_chat_clear_button"  # Изменили ключ
):
    if st.session_state.new_chat_clear_confirm:
        if 'current_chat_flow' in st.session_state:
            clear_chat_history(st.session_state.username, st.session_state.current_chat_flow['id'])
            st.session_state.new_chat_clear_confirm = False  # Изменили ключ
            st.rerun()
    else:
        st.session_state.new_chat_clear_confirm = True  # Изменили ключ
        st.sidebar.warning("⚠️ Вы уверены? Это действие нельзя отменить!")

# Заменяем кнопку удаления чата
if st.sidebar.button(
    "🗑️ Удалить текущий чат" if not st.session_state.new_chat_delete_confirm else "⚠️ Подтвердите удаление чата",
    type="secondary" if not st.session_state.new_chat_delete_confirm else "primary",
    key="new_chat_delete_button"  # Изменили ключ
):
    if st.session_state.new_chat_delete_confirm:
        if 'current_chat_flow' in st.session_state:
            if delete_chat_flow(st.session_state.username, st.session_state.current_chat_flow['id']):
                st.sidebar.success("Чат успешно удален!")
                if 'current_chat_flow' in st.session_state:
                    del st.session_state.current_chat_flow
                if 'message_hashes' in st.session_state:
                    del st.session_state.message_hashes
                st.session_state.new_chat_delete_confirm = False  # Изменили ключ
                st.rerun()
    else:
        st.session_state.new_chat_delete_confirm = True  # Изменили ключ
        st.sidebar.warning("⚠️ Вы уверены, что хотите удалить этот чат? Это действие нельзя отменить!")

# Добавляем кнопки отмены для обоих действий
if st.session_state.new_chat_clear_confirm or st.session_state.new_chat_delete_confirm:  # Изменили ключи
    if st.sidebar.button("Отмена", key="new_chat_cancel_action"):  # Изменили ключ
        st.session_state.new_chat_clear_confirm = False   # Изменили ключ
        st.session_state.new_chat_delete_confirm = False  # Изменили ключ
        st.rerun()

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

    # Инициализируем базу данных для текущего чата
    current_chat_db = ChatDatabase(f"{st.session_state.username}_{st.session_state.current_chat_flow['id']}")
    
    # Отображение истории текущего чата
    chat_history = current_chat_db.get_history()
    for message in chat_history:
        display_message(message, message["role"])

# Функция отправки сообщения
def display_timer():
    """Отображает анимированный секундомер"""
    placeholder = st.empty()
    for seconds in range(60):
        time_str = f"⏱️ {seconds}с"
        placeholder.markdown(f"""
            <div style='animation: blink 1s infinite'>
                {time_str}
            </div>
            <style>
                div {{
                    font-size: 1.2em;
                    font-weight: bold;
                    color: #1E88E5;
                    padding: 10px;
                    border-radius: 8px;
                    background-color: #E3F2FD;
                    text-align: center;
                }}
                @keyframes blink {{
                    0%, 100% {{ opacity: 1.0 }}
                    50% {{ opacity: 0.5 }}
                }}
            </style>
        """, unsafe_allow_html=True)
        time.sleep(1)
        if not st.session_state.get('waiting_response', True):
            break
    placeholder.empty()

def submit_message(user_input):
    if not user_input:
        st.warning("Пожалуйста, введите сообщение")
        return

    try:
        # Инициализация message_hashes
        if "message_hashes" not in st.session_state:
            st.session_state.message_hashes = set()

        # Сохраняем сообщение пользователя
        current_chat_db = ChatDatabase(f"{st.session_state.username}_{st.session_state.current_chat_flow['id']}")
        current_chat_db.add_message("user", user_input)
        display_message({"role": "user", "content": user_input}, "user")

        with st.spinner('Получаем ответ...'):
            # 1. Сначала получаем контекст через OpenRouter
            context_manager = ContextManager()
            enhanced_message = context_manager.get_context(
                st.session_state.username, 
                user_input,
                st.session_state.current_chat_flow['id']
            )

            # 2. Затем отправляем запрос в Flowise
            flowise_url = f"{st.secrets['flowise']['api_base_url']}{st.session_state.current_chat_flow['id']}"
            
            payload = {
                "question": enhanced_message  # Используем сообщение с контекстом
            }

            response = requests.post(flowise_url, json=payload)
            response_data = response.json()

            if response_data and isinstance(response_data, dict) and 'text' in response_data:
                assistant_response = response_data['text'].strip()  # Берем только текст и убираем лишние пробелы
                
                # Проверяем, что ответ не пустой
                if assistant_response:
                    # Сохраняем ТОЛЬКО текст ответа
                    current_chat_db.add_message("assistant", assistant_response)
                    display_message({
                        "role": "assistant", 
                        "content": assistant_response
                    }, "assistant")
                    update_remaining_generations(st.session_state.username, -1)
                    st.rerun()

    except Exception as e:
        st.error(f"Ошибка: {str(e)}")

# Создаем контейнер для поля ввода
input_container = st.container()

def clear_input():
    # Используем callback для очистки
    st.session_state.message_input = ""

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
    # Используем on_click для очистки
    clear_button = st.button("Очистить", key="clear_input", on_click=clear_input, use_container_width=True)
with col3:
    # Для кнопки отмены используем тот же callback
    cancel_button = st.button("Отменить", key="cancel_request", on_click=clear_input, use_container_width=True)

# Изменяем логику отправки сообщения
if send_button:  # Отправляем только при явном нажатии кнопки
    if user_input and user_input.strip():
        st.session_state['_last_input'] = user_input
        submit_message(user_input)

# Изменяем часть кода с настройками контекста в боковой панели
if 'current_chat_flow' in st.session_state:
    current_flow = st.session_state.current_chat_flow
    
    # Получаем сохраненные настройки для текущего чата
    current_settings = current_flow.get('context_settings', {
        "use_context": True,
        "context_range": (1, 10)
    })
    
    # Настройки контекста
    use_context = st.sidebar.checkbox(
        "Использовать контекст истории",
        value=current_settings["use_context"],
        key=f"context_use_{current_flow['id']}"
    )

    if use_context:
        current_chat_db = ChatDatabase(f"{st.session_state.username}_{current_flow['id']}")
        history = current_chat_db.get_history()
        max_messages = len(history) if history else 60
        
        context_range = st.sidebar.slider(
            "Диапазон сообщений для анализа:",
            min_value=1,
            max_value=max(30, max_messages),
            value=current_settings["context_range"],
            step=1,
            key=f"context_range_{current_flow['id']}",
            help="Выберите диапазон сообщений для анализа контекста"
        )
        
        # Сохраняем обновленные настройки
        new_settings = {
            "use_context": use_context,
            "context_range": context_range
        }
        
        if new_settings != current_settings:
            update_chat_context_settings(
                st.session_state.username,
                current_flow['id'],
                new_settings
            )
            # Обновляем настройки в текущем чате
            st.session_state.current_chat_flow['context_settings'] = new_settings
    else:
        # Сохраняем настройки с выключенным контекстом
        new_settings = {
            "use_context": False,
            "context_range": current_settings["context_range"]
        }
        if new_settings != current_settings:
            update_chat_context_settings(
                st.session_state.username,
                current_flow['id'],
                new_settings
            )
            st.session_state.current_chat_flow['context_settings'] = new_settings