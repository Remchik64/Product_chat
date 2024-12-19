from tinydb import TinyDB, Query
import os
from datetime import datetime
from utils.utils import get_data_file_path
import hashlib

def get_message_hash(role, content):
    """Создает уникальный хэш для сообщения"""
    return hashlib.md5(f"{role}:{content}".encode()).hexdigest()

class ChatDatabase:
    def __init__(self, chat_id):
        self.db = TinyDB(get_data_file_path(f'chat_history_{chat_id}.json'))
        
    def add_message(self, role, content):
        self.db.insert({
            'role': role,
            'content': content,
            'timestamp': datetime.now().isoformat()
        })
        
    def get_history(self):
        return self.db.all()
        
    def clear_history(self):
        self.db.truncate()
        
    def delete_message(self, message_hash):
        """Удаляет конкретное сообщение из истории чата по его хэшу"""
        history = self.get_history()
        updated_history = [msg for msg in history if get_message_hash(msg["role"], msg["content"]) != message_hash]
        # Очищаем базу
        self.db.truncate()
        # Вставляем обновленную историю
        for msg in updated_history:
            self.db.insert(msg)