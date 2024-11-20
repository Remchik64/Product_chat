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
    # Проверяем и инициализируем базовые значения в session_state
    if "page_config_initialized" not in st.session_state:
        st.session_state.page_config_initialized = False
        
    is_authenticated = st.session_state.get("authenticated", False)
    is_admin = st.session_state.get("is_admin", False)
    
    pages = []
    
    try:
        # Добавляем все страницы в список
        for page_id, config in sorted(
            PAGE_CONFIG.items(),
            key=lambda x: x[1]["order"]
        ):
            # Проверяем условия отображения страницы
            should_show = (
                (not is_authenticated and page_id == "registr") or
                (is_authenticated and config["show_when_authenticated"] and
                 (not config.get("admin_only") or (config.get("admin_only") and is_admin)))
            )
            
            if should_show and config.get("show_in_menu", True):
                page_path = f"pages/{page_id}.py"
                if os.path.exists(page_path):
                    pages.append(
                        Page(
                            page_path,
                            name=config["name"],
                            icon=config["icon"]
                        )
                    )
        
        if not pages:
            # Если список страниц пуст, добавляем страницу регистрации
            pages.append(
                Page(
                    "pages/registr.py",
                    name=PAGE_CONFIG["registr"]["name"],
                    icon=PAGE_CONFIG["registr"]["icon"]
                )
            )
        
        # Показываем страницы только если они изменились или еще не были инициализированы
        current_pages = str([(p.name, p.icon) for p in pages])
        if not st.session_state.page_config_initialized or st.session_state.get("last_pages") != current_pages:
            show_pages(pages)
            st.session_state.last_pages = current_pages
            st.session_state.page_config_initialized = True
            
    except Exception as e:
        st.error(f"Ошибка при настройке страниц: {str(e)}")
        # Логируем ошибку для отладки
        print(f"Error in setup_pages: {str(e)}") 