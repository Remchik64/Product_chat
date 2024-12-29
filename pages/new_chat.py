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
import unicodedata

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
    
    # Получаем номер сообщения
    current_chat_db = ChatDatabase(f"{st.session_state.username}_{st.session_state.current_chat_flow['id']}")
    history = current_chat_db.get_history()
    message_number = history.index(message) + 1
    
    with st.chat_message(role, avatar=avatar):
        cols = st.columns([0.85, 0.1, 0.05])  # Изменили пропорции для кнопки удаления
        
        with cols[0]:
            message_placeholder = st.empty()
            translation_key = f"translation_state_{message_hash}"
            
            if translation_key not in st.session_state:
                st.session_state[translation_key] = {
                    "is_translated": False,
                    "original_text": message["content"],
                    "translated_text": None
                }
            
            current_state = st.session_state[translation_key]
            if current_state["is_translated"] and current_state["translated_text"]:
                message_placeholder.markdown(current_state["translated_text"])
            else:
                message_placeholder.markdown(current_state["original_text"])
        
        with cols[1]:
            if st.button("🔄", key=f"translate_{message_hash}", help="Перевести сообщение"):
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
                    
        # Добавляем кнопку удаления
        with cols[2]:
            if st.button("🗑️", key=f"delete_{message_hash}", help="Удалить сообщение"):
                current_chat_db.delete_message(message_hash)
                if "message_hashes" in st.session_state:
                    if message_hash in st.session_state.message_hashes:
                        st.session_state.message_hashes.remove(message_hash)
                    translation_key = f"translation_{message_hash}"
                    if translation_key in st.session_state:
                        del st.session_state[translation_key]
                st.rerun()
        
        # Добавляем номер сообщения
        st.markdown(f"<div style='text-align: right; color: gray; font-size: 0.8em; margin-top: 5px;'>Сообщение #{message_number}</div>", unsafe_allow_html=True)

# Функция для сохранения нового чат-потока
def save_chat_flow(username, flow_id, flow_name=None):
    """Сохраняет новый чат-поток"""
    user = user_db.get(User.username == username)
    if not user:
        return False
        
    chat_flows = user.get('chat_flows', [])
    
    # Используем пользовательское имя или создаем стандартное
    if not flow_name or flow_name.strip() == "":
        flow_name = f"Чат {len(chat_flows) + 1}"
    
    new_flow = {
        'id': flow_id,
        'name': flow_name,  # Сохраняем имя как есть
        'created_at': datetime.now().isoformat()
    }
    
    chat_flows.append(new_flow)
    user_db.update({'chat_flows': chat_flows}, User.username == username)
    return True

# Функция для получения списка чат-потоков пользователя
def get_user_chat_flows(username):
    """Получение списка чат-потоков пользователя"""
    user = user_db.get(User.username == username)
    if not user:
        return []
    
    return user.get('chat_flows', [])  # Возвращаем чаты как есть, без модификации

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
    # Определяем текущий индекс
    current_index = 0
    if 'current_chat_flow' in st.session_state:
        current_flow = st.session_state.current_chat_flow
        for i, flow in enumerate(chat_flows):
            if flow['id'] == current_flow['id']:
                current_index = i
                break

    # Отображаем только имена чатов
    selected_flow = st.sidebar.radio(
        "Выберите чат:",
        options=chat_flows,
        format_func=lambda x: x.get('name', 'Новый чат'),  # Показываем только имя чата
        index=current_index
    )
    
    # Обновляем текущий чат при выборе
    if ('current_chat_flow' not in st.session_state or 
        st.session_state.current_chat_flow['id'] != selected_flow['id']):
        st.session_state.current_chat_flow = selected_flow
        if "message_hashes" in st.session_state:
            del st.session_state.message_hashes
        st.rerun()

# Создание нового чат-потока
st.sidebar.markdown("---")
with st.sidebar.expander("Создать новый чат"):
    new_flow_name = st.text_input("Название чата:")
    new_flow_id = st.text_input(
        "ID чата:",
        help="Введите ID чата или закажите сборку в https://t.me/startintellect",
        type="password"  # Скрываем ID от пользователя
    )
    
    if st.button("Создать") and new_flow_id:
        if save_chat_flow(st.session_state.username, new_flow_id, new_flow_name):
            st.session_state.current_chat_flow = {
                'id': new_flow_id,
                'name': new_flow_name if new_flow_name else f"Чат {len(chat_flows) + 1}"
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
        
    if remaining_generations <= 0:
        st.error("У вас нет активных генераций. Пожалуйста, активируйте новый токен.")
        return
        
    try:
        progress_container = st.empty()
        start_time = time.time()
        
        with st.spinner('Получаем ответ...'):
            api_url = "https://openrouter.ai/api/v1/chat/completions"
            
            # Получаем историю чата
            current_chat_id = st.session_state.current_chat_flow['id']
            chat_db = ChatDatabase(f"{st.session_state.username}_{current_chat_id}")
            history = chat_db.get_history()
            
            # Формируем сообщения для API с историей
            messages = []
            # Добавляем системное сообщение
            messages.append({
                "role": "system",
                "content": "Ты - полезный ассистент. Используй контекст предыдущих сообщений для предоставления связных и контекстно-зависимых ответов."
            })
            
            # Добавляем историю сообщений
            for msg in history[-10:]:  # Берем последние 10 сообщений
                messages.append({
                    "role": msg["role"],
                    "content": msg["content"]
                })
            
            # Добавляем текущий вопрос пользователя
            messages.append({
                "role": "user",
                "content": user_input
            })
            
            payload = {
                "model": "google/gemini-flash-1.5",
                "messages": messages,
                "max_tokens": 2048,
                "temperature": 0.7,
                "top_p": 0.9
            }
            
            headers = {
                "Authorization": f"Bearer {st.secrets['openrouter']['api_key']}",
                "HTTP-Referer": "https://github.com/cursor-ai",
                "X-Title": "Cursor AI Assistant",
                "Content-Type": "application/json"
            }

            try:
                # Сохраняем сообщение пользователя
                user_hash = get_message_hash("user", user_input)
                if "message_hashes" not in st.session_state:
                    st.session_state.message_hashes = set()
                
                if user_hash not in st.session_state.message_hashes:
                    st.session_state.message_hashes.add(user_hash)
                    current_chat_db.add_message("user", user_input)

                # Отправляем запрос
                response = requests.post(api_url, headers=headers, json=payload)
                elapsed_time = int(time.time() - start_time)
                
                if response.status_code == 200:
                    progress_container.info(f"⏱️ Время обработки: {elapsed_time} сек.")
                    
                    try:
                        response_data = response.json()
                        assistant_response = response_data['choices'][0]['message']['content']
                        
                        if assistant_response:
                            translated_response = translate_text(assistant_response)
                            assistant_hash = get_message_hash("assistant", translated_response)
                            
                            if assistant_hash not in st.session_state.message_hashes:
                                st.session_state.message_hashes.add(assistant_hash)
                                current_chat_db.add_message("assistant", translated_response)
                                update_remaining_generations(st.session_state.username, -1)
                                st.rerun()
                        else:
                            st.error("Получен пустой ответ от API")
                    except Exception as e:
                        st.error(f"Ошибка при обработке ответа: {str(e)}")
                else:
                    st.error(f"Неожиданный ответ API (код {response.status_code})")
                
            except requests.exceptions.RequestException as e:
                progress_container.empty()
                st.error(f"Ошибка сети при отправке запроса: {str(e)}")
                
    except Exception as e:
        st.error(f"Общая ошибка: {str(e)}")

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

def normalize_text(text):
    """Нормализует текст, исправляя проблемы с кодировкой"""
    if isinstance(text, bytes):
        try:
            text = text.decode('utf-8')
        except UnicodeDecodeError:
            try:
                text = text.decode('cp1251')
            except UnicodeDecodeError:
                return None
    elif not isinstance(text, str):
        text = str(text)
    
    # Нормализуем Unicode и удаляем проблемные символы
    text = unicodedata.normalize('NFKD', text)
    # Конвертируем обратно в UTF-8 и декодируем
    return text.encode('utf-8', errors='ignore').decode('utf-8')