import streamlit as st
from streamlit_extras.switch_page_button import switch_page
from tinydb import TinyDB, Query
import os
from PIL import Image
from utils.utils import check_token_status, format_database
from utils.page_config import setup_pages, PAGE_CONFIG
import magic  # Добавьте в начало файла
import hashlib
from PIL import Image
import io

# Настраиваем страницы
setup_pages()

# Конфигурация страницы должна быть в начале
st.set_page_config(page_title="Личный кабинет", layout="wide")

# Проверка аутентификации
if "authenticated" not in st.session_state or not st.session_state.authenticated:
    st.error("Пожалуйста, войдите в систему")
    switch_page(PAGE_CONFIG["registr"]["name"])
    st.stop()

# Инициализация базы данных пользователей
user_db = TinyDB('user_database.json')

# Папка с изображениями профиля
PROFILE_IMAGES_DIR = 'profile_images'  # Используем относительный путь
if not os.path.exists(PROFILE_IMAGES_DIR):
    os.makedirs(PROFILE_IMAGES_DIR)

# Получение данных пользователя
User = Query()
user_data = user_db.search(User.username == st.session_state.username)
if not user_data:
    st.error("Пользователь не найден.")
    st.session_state.authenticated = False
    st.session_state.username = None
    switch_page(PAGE_CONFIG["registr"]["name"])
    st.stop()

user_data = user_data[0]
# Синхронизируем session state с данными из базы
if user_data.get('active_token'):
    st.session_state.active_token = user_data['active_token']
    st.session_state.remaining_generations = user_data.get('remaining_generations', 0)

st.title(f"Личный кабинет {user_data['username']}")

# Отображение информации о пользователе
st.header("Личная информация")
st.write(f"Email: {user_data['email']}")

# Отображение текущей фотографии профиля
st.subheader("Фотография профиля")
if user_data.get('profile_image') and os.path.exists(user_data['profile_image']):
    st.image(user_data['profile_image'], width=150)
    # Добавляем кнопку для уаления аватара
    if st.button("Удалить фотографию профиля"):
        old_image_path = user_data.get('profile_image')
        if old_image_path and old_image_path != os.path.join(PROFILE_IMAGES_DIR, "default_user_icon.png"):
            if os.path.exists(old_image_path):
                try:
                    os.remove(old_image_path)
                    st.success("Старое изображение успешно удалено.")
                except Exception as e:
                    st.error(f"Ошибка при удалении файла: {e}")
        # Обновляем данные пользователя в базе
        user_db.update({'profile_image': None}, User.username == st.session_state.username)
        st.success("Фотография профиля удалена")
        st.rerun()  # Перезагружаем страницу для обновления изменений
else:
    st.write("Фотография профиля не установлена.")

# Отображение токена и количества генераций
if user_data.get('active_token'):
    st.subheader("Доступные генерации")
    remaining_generations = user_data.get('remaining_generations', 0)
    
    if remaining_generations > 0:
        st.success(f"Осталось генераций: {remaining_generations}")
    else:
        st.warning("Генерации закончились. Пожалуйста, активируйте новый токен.")
else:
    st.warning("У вас нет активного токена. Для использования сервиса необходимо активировать токен.")
    if st.button("Активировать токен"):
        switch_page(PAGE_CONFIG["key_input"]["name"])

# Зона для оновления данных
st.header("Обновление данных")
new_email = st.text_input("Новый email", value=user_data['email'])
new_password = st.text_input("Новый пароль", type="password")
confirm_password = st.text_input("Подтвердите новый пароль", type="password")

# Загрузка новой фотографии профиля
new_profile_image = st.file_uploader("Обновите фотографию профиля", type=["png", "jpg", "jpeg"])

# Инициализируем словарь для обновлений
updates = {}
needs_reload = False

def validate_image(file_content):
    """Проверка безопасности изображения"""
    try:
        # Проверка MIME-типа
        mime = magic.Magic(mime=True)
        file_mime = mime.from_buffer(file_content)
        allowed_mimes = ['image/jpeg', 'image/png', 'image/jpg']
        if file_mime not in allowed_mimes:
            return False, "Недопустимый тип файла"
        
        # Проверка через PIL
        img = Image.open(io.BytesIO(file_content))
        img.verify()
        
        # Проверка размера
        if len(file_content) > 2 * 1024 * 1024:  # 2MB
            return False, "Файл слишком большой"
        
        # Вычисление хеша файла
        file_hash = hashlib.sha256(file_content).hexdigest()
        
        return True, file_hash
    except Exception as e:
        return False, f"Ошибка проверки изображения: {str(e)}"

def sanitize_filename(filename):
    """Очистка имени файла"""
    return "".join(c for c in filename if c.isalnum() or c in ('-', '_', '.'))

if new_profile_image is not None:
    try:
        # Читаем содержимое файла как байты
        file_content = new_profile_image.getvalue()
        
        # Проверяем безопасность изображения
        is_safe, result = validate_image(file_content)
        if not is_safe:
            st.error(result)
            st.stop()
            
        # Генерируем безопасное имя файла
        file_extension = os.path.splitext(new_profile_image.name)[1].lower()
        safe_filename = sanitize_filename(f"{user_data['username']}{file_extension}")
        image_path = os.path.join(PROFILE_IMAGES_DIR, safe_filename)
        
        # Конвертируем и сохраняем изображение через PIL
        img = Image.open(io.BytesIO(file_content))
        img = img.convert('RGB')  # Конвертируем в RGB для удаления метаданных
        
        # Сохраняем с оптимизацией
        img.save(
            image_path,
            format='JPEG' if file_extension.lower() == '.jpg' else 'PNG',
            optimize=True,
            quality=85
        )
        
        updates['profile_image'] = image_path
        needs_reload = True
        
    except Exception as e:
        st.error(f"Ошибка при обработке изображения: {e}")
        st.stop()

if st.button("Обновить данные"):
    # Собираем все обновления
    if new_email and new_email != user_data['email']:
        updates['email'] = new_email
        needs_reload = True

    if new_password:
        if new_password != confirm_password:
            st.error("Пароли не совпадают")
        else:
            updates['password'] = new_password
            needs_reload = True

    if new_profile_image is not None:
        try:
            # Проверяем и создаем директорию, если она не существует
            if not os.path.exists(PROFILE_IMAGES_DIR):
                os.makedirs(PROFILE_IMAGES_DIR)
            
            # Генерируем имя файла с расширением оригинального файла
            file_extension = os.path.splitext(new_profile_image.name)[1].lower()
            image_filename = f"{user_data['username']}{file_extension}"
            image_path = os.path.join(PROFILE_IMAGES_DIR, image_filename)
            
            # Сохраняем новое изображение
            with open(image_path, "wb") as f:
                f.write(new_profile_image.getbuffer())
            
            # Проверяем, что файл успешно сохранен
            if os.path.exists(image_path):
                # Удаляем старое изображение
                old_image_path = user_data.get('profile_image')
                if old_image_path and old_image_path != os.path.join(PROFILE_IMAGES_DIR, "default_user_icon.png"):
                    if os.path.exists(old_image_path):
                        try:
                            os.remove(old_image_path)
                        except Exception as e:
                            st.warning(f"Не удалось удалить старое изображение: {e}")
                
                updates['profile_image'] = image_path
                needs_reload = True
            else:
                st.error("Ошибка при сохранении изображения")
                
        except Exception as e:
            st.error(f"Ошибка при обработке изображения: {e}")
            st.stop()

    # Применяем все обновления разом
    if updates:
        try:
            user_db.update(updates, User.username == st.session_state.username)
            format_database()
            st.success("Данные успешно обновлены")
            if needs_reload:
                st.rerun()
        except Exception as e:
            st.error(f"Ошибка при обновлении данных: {e}")
    else:
        st.info("Нет изменений для обновления.")

# Зона для выхода из аккаунта
if st.button("Выйти"):
    st.session_state.authenticated = False
    st.session_state.username = None
    st.session_state.active_token = None
    st.session_state.remaining_generations = 0
    st.session_state.is_admin = False  # Удаляем статус администратора
    setup_pages()
    switch_page(PAGE_CONFIG["registr"]["name"])
