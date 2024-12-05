from tinydb import TinyDB, Query
import os
from datetime import datetime
from utils.utils import get_data_file_path

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