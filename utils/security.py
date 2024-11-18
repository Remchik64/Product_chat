from passlib.hash import pbkdf2_sha256
import re
from datetime import datetime, timedelta
import streamlit as st

# Константы безопасности
MAX_LOGIN_ATTEMPTS = 3
LOCKOUT_DURATION = 15  # минут
PASSWORD_MIN_LENGTH = 8

def hash_password(password):
    """Хеширование пароля с использованием PBKDF2"""
    return pbkdf2_sha256.hash(password)

def verify_password(password, hashed):
    """Проверка пароля"""
    return pbkdf2_sha256.verify(password, hashed)

def is_strong_password(password):
    """Проверка надежности пароля"""
    if len(password) < PASSWORD_MIN_LENGTH:
        return False, "Пароль должен содержать минимум 8 символов"
    
    if not re.search(r"[A-Z]", password):
        return False, "Пароль должен содержать хотя бы одну заглавную букву"
    
    if not re.search(r"[a-z]", password):
        return False, "Пароль должен содержать хотя бы одну строчную букву"
    
    if not re.search(r"\d", password):
        return False, "Пароль должен содержать хотя бы одну цифру"
    
    if not re.search(r"[!@#$%^&*(),.?\":{}|<>]", password):
        return False, "Пароль должен содержать хотя бы один специальный символ"
    
    return True, "Пароль соответствует требованиям"

def check_login_attempts(username):
    """Проверка попыток входа"""
    if 'login_attempts' not in st.session_state:
        st.session_state.login_attempts = {}
    
    if username not in st.session_state.login_attempts:
        st.session_state.login_attempts[username] = {
            'attempts': 0,
            'lockout_until': None
        }
    
    user_attempts = st.session_state.login_attempts[username]
    
    # Проверка блокировки
    if user_attempts['lockout_until']:
        if datetime.now() < user_attempts['lockout_until']:
            remaining_time = (user_attempts['lockout_until'] - datetime.now()).seconds // 60
            return False, f"Аккаунт заблокирован. Попробуйте через {remaining_time} минут"
        else:
            user_attempts['lockout_until'] = None
            user_attempts['attempts'] = 0
    
    return True, ""

def increment_login_attempts(username):
    """Увеличение счетчика неудачных попыток входа"""
    user_attempts = st.session_state.login_attempts[username]
    user_attempts['attempts'] += 1
    
    if user_attempts['attempts'] >= MAX_LOGIN_ATTEMPTS:
        user_attempts['lockout_until'] = datetime.now() + timedelta(minutes=LOCKOUT_DURATION)
        return False, f"Превышено количество попыток. Аккаунт заблокирован на {LOCKOUT_DURATION} минут"
    
    remaining_attempts = MAX_LOGIN_ATTEMPTS - user_attempts['attempts']
    return True, f"Осталось попыток: {remaining_attempts}"

def reset_login_attempts(username):
    """Сброс счетчика попыток входа"""
    if username in st.session_state.login_attempts:
        st.session_state.login_attempts[username] = {
            'attempts': 0,
            'lockout_until': None
        }
