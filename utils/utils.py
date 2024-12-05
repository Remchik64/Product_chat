import json
import os
import uuid
import codecs
from tinydb import TinyDB, Query
from datetime import datetime
from streamlit.runtime.scriptrunner import add_script_run_ctx
from streamlit import switch_page
import streamlit as st

# Определяем базовый путь для файлов данных
DATA_DIR = "/data" if os.path.exists("/data") else "."

# Функция для получения правильного пути к файлу
def get_data_file_path(filename):
    """
    Возвращает полный путь к файлу данных с учетом окружения
    """
    return os.path.join(DATA_DIR, filename)

def ensure_directories():
    """Проверка и создание необходимых директорий"""
    directories = ['chat', 'profile_images', '.streamlit']
    base_dir = os.path.dirname(os.path.dirname(__file__))
    for directory in directories:
        dir_path = os.path.join(base_dir, directory)
        if not os.path.exists(dir_path):
            os.makedirs(dir_path)

ensure_directories()

# Инициализация базы данных
user_db = TinyDB(get_data_file_path('user_database.json'))
User = Query()

def check_token_status(username):
    """Проверяет статус токена пользователя"""
    user = user_db.get(User.username == username)
    
    if not user:
        return False, "Пользователь не найден"
        
    if not user.get('active_token'):
        return False, "Токен не активирован"
        
    remaining_generations = user.get('remaining_generations', 0)
    if remaining_generations <= 0:
        # Деактивируем токен если генерации закончились
        user_db.update({
            'active_token': None,
            'remaining_generations': 0,
            'token_generations': 0
        }, User.username == username)
        return False, "Токен деактивирован: закончились генерации"
        
    return True, f"Токен активен. Осталось генераций: {remaining_generations}"

def save_token(token, generations=500):
    chat_dir = os.path.join(os.path.dirname(__file__), '..', 'chat')
    os.makedirs(chat_dir, exist_ok=True)
    keys_file = os.path.join(chat_dir, 'access_keys.json')
    
    try:
        # Читаем существующие данные или создаем новые
        if os.path.exists(keys_file):
            with open(keys_file, 'r', encoding='utf-8') as f:
                try:
                    data = json.load(f)
                except:
                    data = {"keys": [], "generations": {}}
        else:
            data = {"keys": [], "generations": {}}
        
        # Добавляем токен
        token = token.strip('"')
        if token not in data["keys"]:
            data["keys"].append(token)
        data["generations"][token] = generations
        
        # Сохраняем данные
        with open(keys_file, 'w', encoding='utf-8') as f:
            json.dump(data, f, ensure_ascii=False, indent=4)
        return True
    except Exception as e:
        print(f"Error saving token: {str(e)}")
        return False

def load_access_keys():
    chat_dir = os.path.join(os.path.dirname(__file__), '..', 'chat')
    os.makedirs(chat_dir, exist_ok=True)
    keys_file = os.path.join(chat_dir, 'access_keys.json')
    
    try:
        if os.path.exists(keys_file):
            with open(keys_file, 'r', encoding='utf-8') as f:
                try:
                    data = json.load(f)
                    if isinstance(data, dict) and "keys" in data:
                        return data["keys"]
                except:
                    return []
        return []
    except Exception as e:
        print(f"Error loading keys: {str(e)}")
        return []

def remove_used_key(used_key):
    json_file = os.path.join(os.path.dirname(__file__), '..', 'chat', 'access_keys.json')
    
    try:
        if not os.path.exists(json_file):
            return False
        
        with open(json_file, 'r', encoding='utf-8') as f:
            try:
                data = json.load(f)
            except:
                data = {"keys": [], "generations": {}}
        
        if used_key in data.get('keys', []):
            data['keys'].remove(used_key)
        elif f'"{used_key}"' in data.get('keys', []):
            data['keys'].remove(f'"{used_key}"')
        
        if used_key in data.get('generations', {}):
            del data['generations'][used_key]
        
        with open(json_file, 'w', encoding='utf-8') as f:
            json.dump(data, f, ensure_ascii=False, indent=4)
        return True
    except Exception as e:
        print(f"Ошибка при удалении ключа: {str(e)}")
        return False

def update_remaining_generations(username, remaining):
    user = user_db.get(User.username == username)
    
    if not user:
        return False
    
    current_generations = user.get('remaining_generations', 0)
    
    if remaining < 0:
        new_remaining = current_generations + remaining
    else:
        new_remaining = remaining
    
    if new_remaining <= 0:
        if user.get('active_token'):
            used_key = user['active_token']
            remove_used_key(used_key)
            
            user_db.update({
                'active_token': None,
                'remaining_generations': 0,
                'token_generations': 0
            }, User.username == username)
            
            if 'access_granted' in st.session_state:
                st.session_state.access_granted = False
    else:
        user_db.update({
            'remaining_generations': new_remaining,
            'token_generations': new_remaining
        }, User.username == username)
    
    return True

def verify_user_access():
    if "username" not in st.session_state:
        st.warning("Необходима авторизация")
        switch_page("registr")
        return False
    
    user = user_db.get(User.username == st.session_state.username)
    if not user or not user.get('active_token'):
        st.warning("Необходим активный токен")
        switch_page("key_input")
        return False
    
    return True

def format_database():
    try:
        with open(get_data_file_path('user_database.json'), 'r', encoding='utf-8') as f:
            data = json.load(f)
        with open(get_data_file_path('user_database.json'), 'w', encoding='utf-8') as f:
            json.dump(data, f, ensure_ascii=False, indent=4)
        return True
    except Exception as e:
        print(f"Ошибка форматирования базы данных: {str(e)}")
        return False

def generate_unique_token():
    return str(uuid.uuid4())

def generate_and_save_token(generations=500):
    new_token = generate_unique_token()
    if save_token(new_token, generations):
        return new_token
    return None
