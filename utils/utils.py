import json
import os
import uuid
from tinydb import TinyDB, Query
from streamlit.runtime.scriptrunner import add_script_run_ctx
from streamlit import switch_page
import streamlit as st

user_db = TinyDB('user_database.json')
User = Query()

# Функция для генерации уникального токена
def generate_unique_token():
    return str(uuid.uuid4())

# Функция для сохранения токена в файл
def save_token(token):
    keys_file = os.path.join(os.path.dirname(__file__), '..', 'chat', 'access_keys.json')
    txt_file = os.path.join(os.path.dirname(__file__), '..', 'chat', 'access_keys.txt')
    
    # Создаем директорию chat, если она не существует
    os.makedirs(os.path.dirname(keys_file), exist_ok=True)
    
    # Сохранение в JSON файл
    try:
        if os.path.exists(keys_file):
            with open(keys_file, 'r') as f:
                try:
                    data = json.load(f)
                except json.JSONDecodeError:
                    data = {"keys": []}
        else:
            data = {"keys": []}
        
        data["keys"].append(token)  # Убираем дополнительные кавычки
        
        with open(keys_file, 'w') as f:
            json.dump(data, f, indent=4)
        
        # Сохранение в TXT файл
        with open(txt_file, 'a') as f:
            f.write(f"{token}\n")
            
    except Exception as e:
        raise Exception(f"Ошибка при сохранении токена: {str(e)}")

# Функция для генерации и сохранения нового токена
def generate_and_save_token():
    new_token = generate_unique_token()
    save_token(new_token)
    return new_token

def load_access_keys():
    keys_file = os.path.join(os.path.dirname(__file__), '..', 'chat', 'access_keys.json')
    try:
        if os.path.exists(keys_file):
            with open(keys_file, 'r') as f:
                data = json.load(f)
                return [key.strip('"') for key in data.get("keys", [])]
        else:
            # Если файл не существует, создаем его с пустым списком ключей
            with open(keys_file, 'w') as f:
                json.dump({"keys": []}, f)
            return []
    except json.JSONDecodeError:
        # Если файл поврежден, пересоздаем его
        with open(keys_file, 'w') as f:
            json.dump({"keys": []}, f)
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
        switch_page("Вход/Регистрация")
        return False
        
    user = user_db.get(User.username == st.session_state.username)
    if not user or not user.get('active_token'):
        st.warning("Необходим активный токен")
        switch_page("key_input")
        return False
        
    return True
