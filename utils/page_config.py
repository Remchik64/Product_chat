from st_pages import Page, show_pages, add_page_title
import streamlit as st

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
    is_authenticated = st.session_state.get("authenticated", False)
    is_admin = st.session_state.get("is_admin", False)
    
    pages = []
    
    # Добавляем страницу регистрации только если пользователь НЕ аутентифицирован
    if not is_authenticated:
        pages.append(
            Page(
                "pages/registr.py",
                name=PAGE_CONFIG["registr"]["name"],
                icon=PAGE_CONFIG["registr"]["icon"]
            )
        )
    
    # Если пользователь аутентифицирован, добавляем остальные страницы
    if is_authenticated:
        for page_id, config in sorted(
            PAGE_CONFIG.items(),
            key=lambda x: x[1]["order"]
        ):
            if (config["show_when_authenticated"] and 
                config.get("show_in_menu", True) and
                (not config.get("admin_only") or (config.get("admin_only") and is_admin))):
                pages.append(
                    Page(
                        f"pages/{page_id}.py",
                        name=config["name"],
                        icon=config["icon"]
                    )
                )
    
    show_pages(pages) 