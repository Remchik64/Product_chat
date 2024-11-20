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
    if "pages" not in st.session_state:
        st.session_state.pages = {}
    
    is_authenticated = st.session_state.get("authenticated", False)
    is_admin = st.session_state.get("is_admin", False)
    
    current_pages = {}
    pages_to_show = []
    
    try:
        for page_id, config in sorted(PAGE_CONFIG.items(), key=lambda x: x[1]["order"]):
            should_show = (
                (not is_authenticated and page_id == "registr") or
                (is_authenticated and config["show_when_authenticated"] and
                 (not config.get("admin_only") or (config.get("admin_only") and is_admin)))
            )
            
            if should_show:
                page_path = f"pages/{page_id}.py"
                if os.path.exists(page_path):
                    current_pages[config["name"]] = page_path
                    if config.get("show_in_menu", True):
                        pages_to_show.append(
                            Page(page_path, name=config["name"], icon=config["icon"])
                        )
        
        if pages_to_show:  # Добавляем проверку
            show_pages(pages_to_show)
            
        # Обновляем session_state только если страницы изменились
        if current_pages != st.session_state.pages:
            st.session_state.pages = current_pages
            
    except Exception as e:
        st.error(f"Ошибка при настройке страниц: {str(e)}")
        print(f"Error in setup_pages: {str(e)}")