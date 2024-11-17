import json
import os
import uuid
from tinydb import TinyDB, Query
from streamlit.runtime.scriptrunner import add_script_run_ctx
from streamlit import switch_page
import streamlit as st

def ensure_directories():
    """Проверка и создание необходимых директорий"""
    directories = [
        'chat',
        'profile_images',
        '.streamlit'
    ]
    base_dir = os.path.dirname(os.path.dirname(__file__))
    for directory in directories:
        dir_path = os.path.join(base_dir, directory)
        if not os.path.exists(dir_path):
            os.makedirs(dir_path)

ensure_directories()

user_db = TinyDB('user_database.json')
User = Query()

# Функция для генерации уникального токена
def generate_unique_token():
    return str(uuid.uuid4())

# Функция для сохранения токена в файл
def save_token(token, generations=500):
    chat_dir = os.path.join(os.path.dirname(__file__), '..', 'chat')
    os.makedirs(chat_dir, exist_ok=True)
    
    keys_file = os.path.join(chat_dir, 'access_keys.json')
    
    try:
        # Создаем новую структуру данных, если файл не существует
        if not os.path.exists(keys_file):
            data = {"keys": [], "generations": {}}
        else:
            try:
                with open(keys_file, 'r') as f:
                    data = json.load(f)
                    if not isinstance(data, dict):
                        data = {"keys": [], "generations": {}}
            except json.JSONDecodeError:
                data = {"keys": [], "generations": {}}
        
        # Убедимся, что все необходимые ключи существуют
        if "keys" not in data:
            data["keys"] = []
        if "generations" not in data:
            data["generations"] = {}
        
        # Добавляем токен без кавычек
        token = token.strip('"')
        if token not in data["keys"]:
            data["keys"].append(token)
        data["generations"][token] = generations
        
        # Сохраняем с отступами для читаемости
        with open(keys_file, 'w') as f:
            json.dump(data, f, indent=4)
            
    except Exception as e:
        print(f"Error saving token: {str(e)}")
        raise e  # Выбрасываем ошибку для отладки

# Функция для генерации и сохранения нового токена
def generate_and_save_token(generations=500):
    new_token = generate_unique_token()
    save_token(new_token, generations)
    return new_token

def load_access_keys():
    chat_dir = os.path.join(os.path.dirname(__file__), '..', 'chat')
    os.makedirs(chat_dir, exist_ok=True)
    
    keys_file = os.path.join(chat_dir, 'access_keys.json')
    
    try:
        if os.path.exists(keys_file):
            with open(keys_file, 'r') as f:
                data = json.load(f)
                if isinstance(data, dict) and "keys" in data:
                    return data["keys"]
        return []
    except Exception as e:
        print(f"Error loading keys: {str(e)}")
        return []

def check_token_status(username):
    user_db = TinyDB('user_database.json')
    User = Query()
    user = user_db.get(User.username == username)
    
    if user and user.get('active_token'):
        # Если количество генераций равно 0, деактивируем токен
        if user.get('remaining_generations', 0) <= 0:
            user_db.update({
                'active_token': None,
                'remaining_generations': 0
            }, User.username == username)
            return False, "Токен деактивирован: закончились генерации"
        return True, "Токен активен"
    return False, "Токен не найден"

def update_remaining_generations(username, remaining):
    user_db = TinyDB('user_database.json')
    User = Query()
    
    if remaining <= 0:
        # Деактивируем токен и удаляем его из базы
        user = user_db.get(User.username == username)
        if user and user.get('active_token'):
            # Обновляем данные пользователя
            user_db.update({
                'active_token': None,
                'remaining_generations': 0,
                'token_generations': 0
            }, User.username == username)
            
            # Очищаем session state
            if 'access_granted' in st.session_state:
                st.session_state.access_granted = False
            if 'active_token' in st.session_state:
                st.session_state.active_token = None
            
            return True
    else:
        # Обновляем количество оставшихся генераций
        user_db.update({
            'remaining_generations': remaining,
            'token_generations': remaining
        }, User.username == username)
        return True
    return False

def remove_used_key(used_key):
    json_file = os.path.join(os.path.dirname(__file__), '..', 'chat', 'access_keys.json')
    txt_file = os.path.join(os.path.dirname(__file__), '..', 'chat', 'access_keys.txt')
    
    # Удаление из JSON файла
    with open(json_file, 'r') as file:
        data = json.load(file)
    
    if f'"{used_key}"' in data['keys']:
        data['keys'].remove(f'"{used_key}"')
        with open(json_file, 'w') as file:
            json.dump(data, file)
    
    # Удаление из TXT файла
    with open(txt_file, 'r') as file:
        lines = file.readlines()
    with open(txt_file, 'w') as file:
        for line in lines:
            if line.strip() != used_key:
                file.write(line)
    
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
        # Читаем текущую базу данных
        with open('user_database.json', 'r', encoding='utf-8') as f:
            data = json.load(f)
        
        # Записываем с отступами для читаемости
        with open('user_database.json', 'w', encoding='utf-8') as f:
            json.dump(data, f, indent=4, ensure_ascii=False)
            
    except Exception as e:
        print(f"Ошибка форматирования базы данных: {str(e)}")
