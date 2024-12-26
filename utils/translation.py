from googletrans import Translator
import streamlit as st

def translate_text(text, target_lang='ru'):
    """
    Переводит текст на указанный язык
    target_lang: 'ru' для русского или 'en' для английского
    """
    try:
        translator = Translator()
        
        if text is None or not isinstance(text, str) or text.strip() == '':
            return "Пустой текст для перевода"
            
        # Определяем язык текста
        detected_lang = translator.detect(text).lang
        
        # Если текст уже на целевом языке, меняем язык перевода
        if detected_lang == target_lang:
            target_lang = 'en' if target_lang == 'ru' else 'ru'
            
        translation = translator.translate(text, dest=target_lang)
        if translation and hasattr(translation, 'text') and translation.text:
            return translation.text
            
        return f"Ошибка перевода: некорректный ответ от переводчика"
        
    except Exception as e:
        st.error(f"Ошибка при переводе: {str(e)}")
        return text

def display_message_with_translation(message, message_hash, avatar, role):
    """Отображает сообщение с кнопкой перевода"""
    # Инициализируем состояние перевода для этого сообщения
    translation_key = f"translation_state_{message_hash}"
    if translation_key not in st.session_state:
        st.session_state[translation_key] = {
            "is_translated": False,
            "original_text": message["content"],
            "translated_text": None
        }
    
    with st.chat_message(role, avatar=avatar):
        cols = st.columns([0.95, 0.05])
        
        # Создаем placeholder для сообщения в первой колонке
        with cols[0]:
            message_placeholder = st.empty()
            current_state = st.session_state[translation_key]
            
            # Показываем текущий текст в зависимости от состояния перевода
            if current_state["is_translated"] and current_state["translated_text"]:
                message_placeholder.markdown(current_state["translated_text"])
            else:
                message_placeholder.markdown(current_state["original_text"])
            
        # Кнопка перевода во второй колонке
        with cols[1]:
            if st.button("🔄", key=f"translate_{message_hash}", help="Перевести сообщение"):
                current_state = st.session_state[translation_key]
                
                if current_state["is_translated"]:
                    # Возвращаемся к оригинальному тексту
                    message_placeholder.markdown(current_state["original_text"])
                    st.session_state[translation_key]["is_translated"] = False
                else:
                    # Переводим текст
                    if not current_state["translated_text"]:
                        translated_text = translate_text(current_state["original_text"])
                        st.session_state[translation_key]["translated_text"] = translated_text
                    
                    message_placeholder.markdown(st.session_state[translation_key]["translated_text"])
                    st.session_state[translation_key]["is_translated"] = True 