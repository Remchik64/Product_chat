from googletrans import Translator
import streamlit as st

def translate_text(text):
    """Переводит текст между русским и английским языками"""
    if not text or not isinstance(text, str):
        return text

    try:
        translator = Translator()
        
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

def display_message_with_translation(message, message_hash, avatar, role):
    """Отображает сообщение с возможностью перевода"""
    translation_key = f"translation_{message_hash}"
    
    with st.chat_message(role, avatar=avatar):
        cols = st.columns([0.9, 0.05, 0.05])
        
        with cols[0]:
            message_placeholder = st.empty()
            
            # Проверяем состояние перевода
            if translation_key not in st.session_state:
                st.session_state[translation_key] = {
                    "is_translated": False,
                    "translated_text": None
                }
            
            # Отображаем текст
            if st.session_state[translation_key]["is_translated"]:
                if st.session_state[translation_key]["translated_text"] is None:
                    translated_text = translate_text(message["content"])
                    st.session_state[translation_key]["translated_text"] = translated_text
                message_placeholder.markdown(st.session_state[translation_key]["translated_text"])
            else:
                message_placeholder.markdown(message["content"])
        
        with cols[1]:
            # Кнопка перевода с динамической подсказкой
            detected_lang = Translator().detect(message["content"]).lang
            tooltip = "Перевести на английский" if detected_lang == 'ru' else "Перевести на русский"
            if st.button("🔄", key=f"translate_{message_hash}", help=tooltip):
                st.session_state[translation_key]["is_translated"] = not st.session_state[translation_key]["is_translated"]
                st.rerun()
        
        with cols[2]:
            # Кнопка удаления
            if st.button("🗑", key=f"delete_{message_hash}", help="Удалить сообщение"):
                return True
    
    return False 