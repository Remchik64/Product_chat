import streamlit as st
from utils.page_config import setup_pages
import requests
import json
import os
from tinydb import TinyDB, Query
from utils.chat_database import ChatDatabase
from utils.utils import get_data_file_path

# Настраиваем страницы
setup_pages()

# Проверка прав администратора
if not st.session_state.get("is_admin", False):
    st.error("Доступ запрещен. Страница доступна только администраторам.")
    st.stop()

st.title("Управление памятью чата")

# Настройки модели в боковой панели
st.sidebar.title("Настройки модели")

# Выбор модели
if "model_settings" not in st.session_state:
    st.session_state.model_settings = {
        "model": "google/gemini-flash-1.5-exp",
        "max_tokens": 512,
        "temperature": 0.5,
        "top_p": 0.9,
        "top_k": 50,
        "repetition_penalty": 1.1
    }

model = st.sidebar.selectbox(
    "Выберите модель:",
    [
        "mistralai/ministral-8b",
        "google/gemini-flash-1.5-exp",
        "google/gemini-2.0-flash-exp:free",
    ],
    index=0,
    key="model_select"
)

# Настройки генерации
with st.sidebar.expander("Настройки генерации", expanded=True):
    max_tokens = st.slider(
        "Max Tokens:",
        min_value=64,
        max_value=2048,
        value=st.session_state.model_settings["max_tokens"],
        step=64,
        help="Максимальное количество токенов в ответе"
    )
    
    temperature = st.slider(
        "Temperature:",
        min_value=0.0,
        max_value=2.0,
        value=st.session_state.model_settings["temperature"],
        step=0.1,
        help="Контролирует случайность генерации (0 = более предсказуемо, 1 = более креативно)"
    )
    
    top_p = st.slider(
        "Top P:",
        min_value=0.0,
        max_value=1.0,
        value=st.session_state.model_settings["top_p"],
        step=0.1,
        help="Nucleus sampling - вероятностный порог для выбора токенов"
    )
    
    top_k = st.slider(
        "Top K:",
        min_value=1,
        max_value=100,
        value=st.session_state.model_settings["top_k"],
        step=1,
        help="Количество наиболее вероятных токенов для выбора"
    )
    
    repetition_penalty = st.slider(
        "Repetition Penalty:",
        min_value=1.0,
        max_value=2.0,
        value=st.session_state.model_settings["repetition_penalty"],
        step=0.1,
        help="Штраф за повторение токенов (1 = нет штрафа)"
    )
    
    # Кнопка сохранения настроек
    if st.button("Сохранить настройки генерации", key="save_generation_settings"):
        st.session_state.model_settings.update({
            "model": model,
            "max_tokens": max_tokens,
            "temperature": temperature,
            "top_p": top_p,
            "top_k": top_k,
            "repetition_penalty": repetition_penalty
        })
        st.success("Настройки генерации сохранены!")

def get_chat_flows(username):
    """Получает список чат-потоков пользователя"""
    user_db = TinyDB(get_data_file_path('user_database.json'))
    User = Query()
    user = user_db.get(User.username == username)
    if user and 'chat_flows' in user:
        return user['chat_flows']
    return []

def analyze_chat_history(username, chat_id=None, last_n_messages=10):
    """Анализирует историю конкретного чата пользователя и возвращает релевантный контекст"""
    # Определяем ID чата
    chat_db_name = f"{username}_{chat_id}" if chat_id else f"{username}_main_chat"
    chat_db = ChatDatabase(chat_db_name)
    history = chat_db.get_history()
    
    if not history:
        return None
        
    # Форматируем историю в структурированный диалог
    formatted_history = []
    for msg in history[-last_n_messages:]:
        role = "Assistant" if msg['role'] == "assistant" else "User"
        formatted_history.append(f"{role}: {msg['content']}")
    
    history_text = "\n".join(formatted_history)
    
    # Формируем промпт для анализа
    analysis_prompt = f"""[INST] Ты - ассистент с отличной памятью, анализирующий историю диалога. 
    Проанализируй последние {last_n_messages} сообщений из истории чата и создай подробный отчет.
    
    История диалога:
    {history_text}

Пожалуйста, предоставь структурированный анализ по следующим пунктам:

1. Основные темы диалога:
   - Перечисли все обсуждаемые темы
   - Укажи их взаимосвязи

2. Ключевые моменты обсуждения:
   - Важные детали и факты
   - Принятые решения
   - Заданные вопросы

3. Развитие диалога:
   - Как менялись темы
   - Какие вопросы остались открытыми
   - Какие темы требуют продолжения

4. Контекстные связи:
   - Как темы связаны между собой
   - Какая информация может быть важна для будущих ответов

5. Рекомендации:
   - Какие темы стоит развить
   - На что обратить внимание в будущих ответах

Формат ответа должен быть четко структуррован по этим пунктам.
[/INST]"""

    try:
        # Используем настройки из session_state
        settings = st.session_state.model_settings
        
        # Запрос к OpenRouter API для анализа
        response = requests.post(
            url="https://openrouter.ai/api/v1/chat/completions",
            headers={
                "Authorization": f"Bearer {st.secrets['openrouter']['api_key']}",
                "Content-Type": "application/json"
            },
            data=json.dumps({
                "model": settings["model"],
                "messages": [
                    {
                        "role": "user",
                        "content": analysis_prompt
                    }
                ],
                "max_tokens": 2048,
                "temperature": settings["temperature"],
                "top_p": settings["top_p"],
                "n": 1
            })
        )
        
        if response.status_code == 200:
            response_data = response.json()
            analysis = response_data['choices'][0]['message']['content'].strip()
        else:
            raise Exception(f"Ошибка при анализе контекста. Код ответа: {response.status_code}")
        
        # Добавляем метаданные о чате
        chat_info = ""
        if chat_id:
            chat_flows = get_chat_flows(username)
            current_chat = next((flow for flow in chat_flows if flow['id'] == chat_id), None)
            if current_chat:
                chat_info = f"\nАнализ чата: {current_chat['name']}\n"
        
        return f"{chat_info}\n{analysis}"
        
    except Exception as e:
        st.error(f"Ошибка при анализе истории: {str(e)}")
        return None

def inject_context(original_message, context, chat_name=None):
    """Объединяет исходное сообщение пользователя с контекстом"""
    chat_info = f"Чат: {chat_name}\n" if chat_name else ""
    return f"""{chat_info}
Анализ контекста предыдущего диалога:
{context}

Текущий вопрос пользователя:
{original_message}

Используя предоставленный анализ контекста, сформируй подробный и связный ответ.
Убедись, что ответ:
1. Учитывает всю релевантную информацию из истории диалога
2. Логически связан с предыдущими тем��ми
3. Развивает обсуждение в правильном направлении
4. Отвечает на текущий вопрос с учетом полного контекста"""

# Интерфейс для тестирования
st.subheader("Тестирование анализа истории чата")

# Выбор пользователя
user_db = TinyDB(get_data_file_path('user_database.json'))
users = [user['username'] for user in user_db.all()]
selected_user = st.selectbox("Выберите пользователя:", users)

# Выбор чата
chat_flows = get_chat_flows(selected_user)
chat_options = [{"name": "Основной чат", "id": None}] + chat_flows
selected_chat = st.selectbox(
    "Выберите чат:",
    options=chat_options,
    format_func=lambda x: x["name"],
    key="selected_chat"
)

if st.button("Проанализировать историю"):
    with st.spinner("Анализирую историю чата..."):
        context = analyze_chat_history(
            selected_user,
            chat_id=selected_chat["id"] if selected_chat else None
        )
        if context:
            st.success("Анализ выполнен успешно")
            st.text_area("Выделенный контекст:", value=context, height=200)
            # Сохраняем последний контекст и информацию о чате
            st.session_state.last_context = context
            st.session_state.last_chat_name = selected_chat["name"] if selected_chat else "Основной чат"
        else:
            st.warning("История чата пуста или произошла ошибка при анализе")

# Просмотр и редактирование промпта модели
st.subheader("Промпт модели")
st.markdown("""
Здесь вы можете просмотреть и отредактировать текущий промпт модели.
Это поможет улучшить качество ответов и настроить поведение модели.
""")

# Базовый системный промпт
if "system_prompt" not in st.session_state:
    st.session_state.system_prompt = """Ты - помощник по анализу контекста диалога. 
Твоя задача - анализировать историю конкретного чата и выделять релевантный контекст, 
не смешивая его с другими чатами. Старайся выделять самую важную информацию, 
которая может быть полезна для поддержания связного диалога."""

system_prompt = st.text_area(
    "Системный промпт (общие инструкции для модели):",
    value=st.session_state.system_prompt,
    height=150,
    help="Этот промпт определяет базовое поведение модели"
)

# Промпт для анализа контекста
if "analysis_prompt_template" not in st.session_state:
    st.session_state.analysis_prompt_template = """{chat_info}Проанализируй последние сообщения из этого конкретного чата и выдели ключевой контекст для следующего ответа.
Помни, что этот контекст относится только к текущему чату и не должен смешиваться с контекстом других чатов.

История чата:
{history}

Выдели самую важную информацию и контекст из этой истории, которые могут быть полезны для следующего ответа.
Учитывай только информацию из текущего чата."""

analysis_prompt = st.text_area(
    "Промпт для анализа контекста:",
    value=st.session_state.analysis_prompt_template,
    height=200,
    help="Этот шаблон используется для анализа истории чата"
)

# Пример сгенерированного промпта
if 'last_context' in st.session_state:
    st.markdown("#### Пример текущего промпта")
    with st.expander("Показать полный промпт, отправляемый модели"):
        example_prompt = analysis_prompt.format(
            chat_info=f"Чат: {st.session_state.get('last_chat_name', 'Тестовый чат')}\n",
            history=st.session_state.last_context
        )
        st.code(example_prompt, language="markdown")

# Сохранение изменений промптов
if st.button("Сохранить изменения промптов"):
    st.session_state.system_prompt = system_prompt
    st.session_state.analysis_prompt_template = analysis_prompt
    st.success("Промпты успешно обновлены!")

st.markdown("---")
st.markdown("""
#### Как использовать промпты:
1. **Системный промпт** определяет базовое поведение и роль модели
2. **Промпт для анализа** используется для обработки истории чата
3. Используйте переменные в фигурных скобках:
   - `{chat_info}` - информация о текущем чате
   - `{history}` - история сообщений

Хороший промпт помогает модели:
- Лучше понимать контекст разговора
- Давать более релевантные ответы
- Поддерживать последовательность диалога
""")

# Настройки анализа
st.sidebar.markdown("---")
st.sidebar.title("Настройки анализа")
st.sidebar.number_input(
    "Количество сообщений для анализа",
    min_value=1,
    max_value=30,
    value=10,
    key="n_messages",
    help="Количество последних сообщений, которые будут анализироваться"
) 