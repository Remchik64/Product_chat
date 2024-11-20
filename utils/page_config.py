from st_pages import Page, show_pages, add_page_title
import streamlit as st
import os

# Словарь с настройками страниц
PAGE_CONFIG = {
    "registr": {
        "name": "Вход/Регистрация",
        "icon": "🔐",
        "order": 1,
        "show_when_authenticated": False,
        "show_in_menu": False
    },
    "key_input": {
        "name": "Ввод/Покупка токена",
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
        "show_when_authenticated": True,
        "show_in_menu": False
    },
    "profile": {
        "name": "Профиль",
        "icon": "👤",
        "order": 5,
        "show_when_authenticated": True
    },
    "admin/generate_tokens": {
        "name": "Генерация токенов",
        "icon": "🔑",
        "order": 6,
        "show_when_authenticated": True,
        "admin_only": True
    }
}

def setup_pages():
    pages_to_show = []
    
    # Добавляем все страницы в список
    for page_id, config in sorted(PAGE_CONFIG.items(), key=lambda x: x[1]["order"]):
        is_authenticated = st.session_state.get("authenticated", False)
        is_admin = st.session_state.get("is_admin", False)
        
        should_show = (
            (not is_authenticated and page_id == "registr") or
            (is_authenticated and config["show_when_authenticated"] and
             (not config.get("admin_only") or (config.get("admin_only") and is_admin)))
        )
        
        if should_show:
            page_path = f"pages/{page_id}.py"
            if os.path.exists(page_path) and config.get("show_in_menu", True):
                pages_to_show.append(
                    Page(page_path, name=config["name"], icon=config["icon"])
                )
    
    if not pages_to_show:
        # Если список пуст, добавляем хотя бы страницу регистрации
        pages_to_show.append(
            Page("pages/registr.py", name=PAGE_CONFIG["registr"]["name"], icon=PAGE_CONFIG["registr"]["icon"])
        )
    
    show_pages(pages_to_show)