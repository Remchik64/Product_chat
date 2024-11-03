import streamlit as st
from utils import generate_and_save_token

st.title("Генерация уникальных токенов")

password = st.text_input("Введите пароль для доступа", type="password")

if password == "01122011":  # Замените на реальный пароль
    if st.button("Сгенерировать уникальный токен"):
        new_token = generate_and_save_token()
        st.success(f"Ваш уникальный токен: {new_token}")
        st.write(f"Ссылка для доступа: http://yourapp.com/chat/new_chat?token={new_token}")
else:
    st.error("Неверный пароль. Доступ запрещён.")

