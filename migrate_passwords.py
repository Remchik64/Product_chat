from tinydb import TinyDB, Query
from utils.security import hash_password

user_db = TinyDB('user_database.json')
User = Query()

users = user_db.all()

for user in users:
    if not user['password'].startswith('$pbkdf2-sha256$'):
        hashed_password = hash_password(user['password'])
        user_db.update({'password': hashed_password}, User.username == user['username'])

print("Миграция паролей завершена.")
