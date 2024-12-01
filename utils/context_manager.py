import os
import streamlit as st
from together import Together
import json
from utils.chat_database import ChatDatabase
from tinydb import TinyDB, Query

class ContextManager:
    def __init__(self):
        # Инициализируем Together API для анализа контекста
        os.environ["TOGETHER_API_KEY"] = st.secrets["together"]["api_key"]
        self.together_client = Together()
        
    def get_context(self, username, message, flow_id=None, last_n_messages=10):
        """Получает контекст для сообщения на основе истории чата"""
        # Если flow_id не указан, получаем историю из всех чатов пользователя
        if not flow_id:
            user_db = TinyDB('user_database.json')
            User = Query()
            user = user_db.get(User.username == username)
            if user and 'chat_flows' in user:
                all_history = []
                for flow in user['chat_flows']:
                    chat_db = ChatDatabase(f"{username}_{flow['id']}")
                    history = chat_db.get_history()
                    if history:
                        all_history.extend(history)
                # Сортируем по времени и берем последние сообщения
                all_history.sort(key=lambda x: x.get('timestamp', ''))
                recent_history = all_history[-last_n_messages:] if all_history else []
            else:
                return message
        else:
            # Получаем историю конкретного чата
            chat_db = ChatDatabase(f"{username}_{flow_id}")
            history = chat_db.get_history()
            if not history:
                return message
            recent_history = history[-last_n_messages:]
        
        # Проверяем, есть ли история сообщений
        if not recent_history:
            print("История сообщений пуста, возвращаем исходное сообщение")
            return message
            
        try:
            # Преобразуем историю в читаемый формат
            formatted_history = []
            for msg in recent_history:
                if isinstance(msg, dict):
                    role = msg.get('role', 'unknown')
                    content = msg.get('content', '')
                    formatted_history.append(f"{role}: {content}")
                else:
                    formatted_history.append(str(msg))
            
            history_text = "\n".join(formatted_history)
            
            # Используем Together.ai для анализа контекста
            context_prompt = f"""[INST] Ты - помощник по анализу контекста диалога. Твоя задача - проанализировать историю чата и выделить ключевую информацию, которая важна для понимания нового вопроса.

История чата:
{history_text}

Новый вопрос:
{message}

Проанализируй историю чата и выдели только ту информацию, которая напрямую связана с новым вопросом. Верни только релевантные части диалога, которые помогут лучше понять контекст вопроса. [/INST]"""

            # Запрос к Together.ai
            response = self.together_client.chat.completions.create(
                model="meta-llama/Meta-Llama-3.1-70B-Instruct-Turbo",
                messages=[{
                    "role": "user",
                    "content": context_prompt
                }],
                max_tokens=1024,
                temperature=0.7,
                top_p=0.8,
                top_k=50,
                repetition_penalty=1.1
            )
            
            # Получаем анализ контекста от Together.ai
            context_analysis = response.choices[0].message.content.strip()
            
            if not context_analysis or len(context_analysis.strip()) < 10:
                print("Получен пустой контекст от Together.ai, возвращаем исходное сообщение")
                return message
            
            # Формируем финальное сообщение для Flowise с контекстом
            enhanced_message = f"""Контекст предыдущего разговора:
{context_analysis}

Текущий вопрос:
{message}

Пожалуйста, используй предоставленный контекст для формирования полного и связного ответа."""
            
            print(f"Отправляем в Flowise сообщение с контекстом: {enhanced_message[:200]}...")
            return enhanced_message
            
        except Exception as e:
            print(f"Ошибка при анализе контекста через Together.ai: {str(e)}")
            return message