from tinydb import TinyDB, Query
import os
from datetime import datetime

class ChatDatabase:
    def __init__(self, username):
        self.db_path = f'chat_history_{username}.json'
        self.db = TinyDB(self.db_path)
        
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