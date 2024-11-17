from tinydb import TinyDB, Query
import hashlib
import os

def setup_first_admin():
    db = TinyDB('user_database.json')
    User = Query()
    
    # Проверяем существование админа
    admin = db.search(User.is_admin == True)
    if admin:
        print("Администратор уже существует")
        return
    
    # Данные администратора
    admin_username = input("Введите имя администратора: ")
    admin_password = input("Введите пароль администратора: ")
    admin_email = input("Введите email администратора: ")
    
    # Создаем запись администратора
    admin_data = {
        'username': admin_username,
        'email': admin_email,
        'password': admin_password,
        'is_admin': True,
        'profile_image': "profile_images/default_user_icon.png",
        'remaining_generations': 0
    }
    
    # Проверяем существование пользователя
    existing_user = db.get(User.username == admin_username)
    if existing_user:
        # Обновляем существующего пользователя до админа
        db.update({'is_admin': True}, User.username == admin_username)
        print(f"Пользователь {admin_username} повышен до администратора")
    else:
        # Создаем нового администратора
        db.insert(admin_data)
        print(f"Администратор {admin_username} успешно создан")

if __name__ == "__main__":
    setup_first_admin()
