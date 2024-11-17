import streamlit as st
import json
import os
from utils.utils import load_access_keys
from utils.page_config import PAGE_CONFIG, setup_pages
from flowise import Flowise
from typing import List
import requests
from tinydb import TinyDB, Query

# Настраиваем страницы
setup_pages()

# Проверка доступа
if "access_granted" not in st.session_state or not st.session_state.access_granted:
    st.error("Доступ запрещён. Пожалуйста, введите правильный токен на странице ввода ключа.")
    st.stop()

st.title("Новый чат-поток в разработке")

def upload_documents_to_flowise(files: List[str], chatflow_id: str) -> bool:
    """
    Загружает документы в Flowise используя SDK
    """
    try:
        client = Flowise(
            base_url=st.secrets["flowise"]["base_url"],
            api_key=st.secrets["flowise"]["api_key"]
        )
        
        # Подготавливаем файлы для загрузки
        files_data = []
        for file_path in files:
            with open(file_path, 'rb') as f:
                file_content = f.read()
                files_data.append({
                    'name': os.path.basename(file_path),
                    'content': file_content
                })
        
        # Отправляем запрос на загрузку через Vector Upsert API
        response = client.upsert_document(
            chatflow_id=chatflow_id,
            files=files_data
        )
        
        if response:
            st.success(f"""
                Документы успешно загружены:
                - Добавлено: {response.get('numAdded', 0)}
                - Обновлено: {response.get('numUpdated', 0)}
                - Пропущено: {response.get('numSkipped', 0)}
            """)
            return True
            
        return False
            
    except Exception as e:
        st.error(f"Ошибка при загрузке документов: {str(e)}")
        return False

def render_file_uploader():
    """
    Рендерит интерфейс загрузки файлов
    """
    st.subheader("Загрузка документов")
    
    uploaded_files = st.file_uploader(
        "Выберите документы для загрузки",
        accept_multiple_files=True,
        type=['pdf', 'txt', 'doc', 'docx']
    )
    
    if uploaded_files and st.button("Загрузить документы"):
        # Временно сохраняем загруженные файлы
        temp_paths = []
        try:
            for uploaded_file in uploaded_files:
                temp_path = f"temp_{uploaded_file.name}"
                with open(temp_path, "wb") as f:
                    f.write(uploaded_file.getbuffer())
                temp_paths.append(temp_path)
            
            # Загружаем в Flowise
            success = upload_documents_to_flowise(
                temp_paths,
                "fc24280f-f41c-4121-b1fb-c41176a726e9"  # Ваш chatflow ID
            )
            
            if success:
                # После успешной загрузки можно задать вопрос
                st.session_state.user_input = "Расскажи о содержании загруженных документов"
                
        finally:
            # Удаляем временные файлы
            for temp_path in temp_paths:
                if os.path.exists(temp_path):
                    os.remove(temp_path)

# Добавляем загрузчик файлов
render_file_uploader()

# Логика для чата
user_input = st.text_input("Введите ваше сообщение")
if st.button("Отправить"):
    st.write(f"Вы: {user_input}")
    # Здесь можно добавить логику для обработки сообщений
