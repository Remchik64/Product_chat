import os
import streamlit as st
from typing import Optional, List, Dict
import requests
import json
from functools import lru_cache
from utils.chat_database import ChatDatabase
from tinydb import TinyDB, Query
import time

@lru_cache()
def initialize_openrouter_api() -> Optional[str]:
    """Инициализация OpenRouter API с обработкой ошибок"""
    try:
        if "openrouter" in st.secrets and "api_key" in st.secrets["openrouter"]:
            api_key = st.secrets["openrouter"]["api_key"]
            return api_key
        return None
    except Exception as e:
        print(f"Ошибка при инициализации OpenRouter API: {e}")
        return None

class ContextManager:
    def __init__(self):
        """Инициализация менеджера контекста с обработкой ошибок"""
        self.openrouter_api_key = initialize_openrouter_api()
        self.default_context = "Вы - профессиональный бизнес-консультант."

    def get_context(self, username, message, flow_id=None, context_range=(1, 10)):
        """
        Получает контекст для сообщения на основе истории конкретного чата
        с учетом указанного диапазона сообщений
        """
        chat_db_name = f"{username}_{flow_id}" if flow_id else f"{username}_main_chat"
        chat_db = ChatDatabase(chat_db_name)
        history = chat_db.get_history()
        
        if not history:
            return message
        
        try:
            # Получаем сообщения из указанного диапазона
            start_idx = max(0, context_range[0] - 1)
            end_idx = min(len(history), context_range[1])
            
            # Форматируем только сообщения из выбранного диапазона
            formatted_history = []
            for msg in history[start_idx:end_idx]:
                role = "Assistant" if msg['role'] == "assistant" else "User"
                formatted_history.append(f"{role}: {msg['content']}")
            
            history_text = "\n".join(formatted_history)
            
            print(f"Анализ истории для чата {chat_db_name}")
            
            # Обновленный промпт для анализа контекста
            context_prompt = f"""[INST] Ты - профессиональный ассистент с отличной памятью. 
            Твоя задача - проанализировать историю диалога и создать релевантный контекст для нового вопроса.

История текущего чата:
{history_text}

Новый вопрос пользователя:
{message}

Проанализируй и создай контекст, учитывая:
1. Ключевые темы и концепции из предыдущих сообщений
2. Важные детали и факты, упомянутые ранее
3. Связи между текущим вопросом и предыдущим контекстом
4. Релевантную информацию для формирования ответа
5. Последовательность развития диалога

Сформируй структурированный ответ, который поможет дать наиболее точный и контекстно-зависимый ответ на новый вопрос.
[/INST]"""

            # Добавляем повторные попытки при сетевых ошибках
            max_retries = 3
            retry_delay = 2
            
            for attempt in range(max_retries):
                try:
                    # Используем существующие настройки
                    flowise_url = f"{st.secrets['flowise']['api_base_url']}{flow_id if flow_id else st.secrets['flowise']['main_chat_id']}"
                    
                    response = requests.post(
                        url=flowise_url,
                        headers={
                            "Content-Type": "application/json"
                        },
                        data=json.dumps({
                            "question": context_prompt,
                            "history": formatted_history
                        })
                    )
                    
                    if response.status_code == 200:
                        response_data = response.json()
                        context_analysis = response_data.get('text', '') # или response_data напрямую
                        print(f"Получен анализ контекста для чата {chat_db_name}")
                    else:
                        print(f"Неожиданный формат ответа для чата {chat_db_name}")
                        return message
                    
                    if not context_analysis:
                        return message
                    
                    # Формируем финальное сообщение с контекстом
                    enhanced_message = f"""Контекст текущего чата:
{context_analysis}

Текущий вопрос:
{message}

Используя контекст ТОЛЬКО ЭТОГО чата, дай подробный и связный ответ. Убедись, что ответ логически связан с предыдущими темами разговора В ЭТОМ ЧАТЕ."""
                    
                    return enhanced_message
                    
                except (ConnectionError, TimeoutError) as e:
                    if attempt < max_retries - 1:
                        print(f"Попытка {attempt + 1} не удалась для чата {chat_db_name}: {str(e)}")
                        time.sleep(retry_delay)
                        continue
                    else:
                        print(f"Все попытки исчерпаны для чата {chat_db_name}")
                        return message
                        
                except Exception as e:
                    print(f"Ошибка при анализе контекста для чата {chat_db_name}: {str(e)}")
                    return message
                    
        except Exception as e:
            print(f"Ошибка при обработке истории чата {chat_db_name}: {str(e)}")
            return message