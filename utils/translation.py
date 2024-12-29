from googletrans import Translator
import streamlit as st

# Создаем глобальный экземпляр переводчика
translator = Translator()

def translate_text(text):
    """Переводит текст между русским и английским языками"""
    if not text or not isinstance(text, str):
        return text

    try:
        # Определяем язык текста
        detected = translator.detect(text)
        
        # Если текст на русском - переводим на английский, иначе на русский
        target_lang = 'en' if detected.lang == 'ru' else 'ru'
        
        translation = translator.translate(text, dest=target_lang)
        if translation and hasattr(translation, 'text'):
            return translation.text
        return text
    except Exception as e:
        print(f"Ошибка перевода: {str(e)}")
        return text

def display_message_with_translation(message, message_hash, avatar, role, button_key=None):
    """Отображает сообщение с кнопкой перевода"""
    if button_key is None:
        button_key = f"translate_{message_hash}_{role}"
    
    translation_key = f"translation_{message_hash}"
    content = message.get("content", "")
    
    with st.chat_message(role, avatar=avatar):
        cols = st.columns([0.9, 0.05, 0.05])
        
        with cols[0]:
            message_placeholder = st.empty()
            
            # Инициализируем или обновляем состояние перевода
            if translation_key not in st.session_state:
                st.session_state[translation_key] = {
                    "is_translated": False,
                    "translated_text": None,
                    "original_text": content
                }
            elif "original_text" not in st.session_state[translation_key]:
                # Обновляем существующее состояние
                st.session_state[translation_key].update({
                    "original_text": content
                })
            
            current_state = st.session_state[translation_key]
            
            # Отображаем текст
            if current_state["is_translated"]:
                if current_state["translated_text"] is None:
                    current_state["translated_text"] = translate_text(content)
                message_placeholder.markdown(current_state["translated_text"])
            else:
                message_placeholder.markdown(content)
        
        with cols[1]:
            # Кнопка перевода с динамической подсказкой
            try:
                detected_lang = translator.detect(content).lang
                tooltip = "Перевести на английский" if detected_lang == 'ru' else "Перевести на русский"
            except:
                tooltip = "Перевести"
                
            if st.button("🔄", key=button_key, help=tooltip):
                current_state = st.session_state[translation_key]
                current_state["is_translated"] = not current_state["is_translated"]
                
                # Если переключаемся на перевод и перевод еще не сделан
                if current_state["is_translated"] and current_state["translated_text"] is None:
                    current_state["translated_text"] = translate_text(content)
                
                message_placeholder.markdown(
                    current_state["translated_text"] if current_state["is_translated"] 
                    else content
                )
        
        with cols[2]:
            # Кнопка удаления
            if st.button("🗑", key=f"delete_{message_hash}", help="Удалить сообщение"):
                return True
    
    return False 