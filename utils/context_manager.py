import os
import streamlit as st
import together
import json
from utils.chat_database import ChatDatabase
from tinydb import TinyDB, Query
import time

class ContextManager:
    def __init__(self):
        # Инициализируем Together API для анализа контекста
        os.environ["TOGETHER_API_KEY"] = st.secrets["together"]["api_key"]
        together.api_key = st.secrets["together"]["api_key"]
        
    def get_context(self, username, message, flow_id=None, last_n_messages=10):
        """Получает контекст для сообщения на основе истории чата"""
        chat_db = ChatDatabase(f"{username}_{flow_id}" if flow_id else f"{username}_main_chat")
        history = chat_db.get_history()
        
        if not history:
            return message
            
        try:
            # Форматируем историю в структурированный диалог
            formatted_history = []
            for msg in history:
                role = "Assistant" if msg['role'] == "assistant" else "User"
                formatted_history.append(f"{role}: {msg['content']}")
            
            history_text = "\n".join(formatted_history)
            
            # Создаем промпт для анализа контекста
            context_prompt = f"""[INST] Ты - ассистент с отличной памятью. Твоя задача - проанализировать всю историю диалога и создать подробный контекст для нового вопроса.

История диалога:
{history_text}

Новый вопрос пользователя:
{message}

Пожалуйста:
1. Проанализируй всю историю диалога
2. Определи основные темы и ключевые моменты обсуждения
3. Найди связи между предыдущими вопросами и текущим вопросом
4. Выдели информацию, которая важна для ответа на текущий вопрос
5. Создай краткое, но информативное резюме контекста

Формат ответа:
1. Основные темы диалога: [перечисли темы]
2. Ключевые моменты: [важные детали]
3. Связь с текущим вопросом: [как текущий вопрос связан с предыдущим контекстом]
4. Релевантная информация: [что важно для ответа]

[/INST]"""

            # Добавляем повторные попытки при сетевых ошибках
            max_retries = 3
            retry_delay = 2
            
            for attempt in range(max_retries):
                try:
                    # Запрос к Together.ai для анализа контекста
                    response = together.Complete.create(
                        model="meta-llama/Meta-Llama-3.1-8B-Instruct-Turbo",
                        prompt=context_prompt,
                        max_tokens=2048,
                        temperature=0.2,
                        top_p=0.9,
                        top_k=50,
                        repetition_penalty=1.1
                    )
                    
                    # Проверяем структуру ответа
                    if isinstance(response, dict) and 'output' in response:
                        context_analysis = response['output']['choices'][0]['text'].strip()
                    else:
                        print(f"Неожиданный формат ответа: {response}")
                        return message
                    
                    if not context_analysis:
                        return message
                    
                    # Формируем финальное сообщение с контекстом
                    enhanced_message = f"""Контекст предыдущего диалога:
{context_analysis}

Текущий вопрос пользователя:
{message}

Используя предоставленный контекст, дай подробный и связный ответ, учитывая всю историю обсуждения. Убедись, что ответ логически связан с предыдущими темами разговора."""
                    
                    return enhanced_message
                    
                except (ConnectionError, TimeoutError) as e:
                    if attempt < max_retries - 1:
                        print(f"Попытка {attempt + 1} не удалась: {str(e)}")
                        time.sleep(retry_delay)
                        continue
                    else:
                        print(f"Все попытки подключения исчерпаны: {str(e)}")
                        return message
                        
                except Exception as e:
                    print(f"Неожиданная ошибка при анализе контекста: {str(e)}")
                    return message
                    
        except Exception as e:
            print(f"Ошибка при обработке истории чата: {str(e)}")
            return message