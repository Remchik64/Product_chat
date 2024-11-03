from st_pages import Page, show_pages, add_page_title
import streamlit as st

# Словарь с настройками страниц
PAGE_CONFIG = {
    "registr": {
        "name": "Вход/Регистрация",
        "icon": "🔐",
        "order": 1,
        "show_when_authenticated": False
    },
    "key_input": {
        "name": "Ввод токена",
        "icon": "🔑",
        "order": 2,
        "show_when_authenticated": True
    },
    "app": {
        "name": "Главная",
        "icon": "🏠",
        "order": 3,
        "show_when_authenticated": True
    },
    "new_chat": {
        "name": "Новый чат",
        "icon": "💭",
        "order": 4,
        "show_when_authenticated": True
    },
    "profile": {
        "name": "Профиль",
        "icon": "👤",
        "order": 5,
        "show_when_authenticated": True
    }
}

def setup_pages():
    # Создаем список страниц на основе конфигурации и состояния аутентификации
    is_authenticated = st.session_state.get("authenticated", False)
    
    pages = [
        Page(
            f"pages/{page_id}.py",
            name=config["name"],
            icon=config["icon"]
        )
        for page_id, config in sorted(
            PAGE_CONFIG.items(),
            key=lambda x: x[1]["order"]
        )
        if not is_authenticated or config["show_when_authenticated"]
    ]
    
    # Отображаем страницы
    show_pages(pages) 