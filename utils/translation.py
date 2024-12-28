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

def display_message_with_translation(message, message_hash, avatar, role):
    """Отображает сообщение с кнопкой перевода"""
    translation_key = f"translation_{message_hash}"
    
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
            
        # Кнопка перевода во второй колонке с уникальным ключом
        with cols[1]:
            unique_key = f"translate_{message_hash}_{role}"  # Добавляем role к ключу
            if st.button("🔄", key=unique_key, help="Перевести сообщение"):
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
                    
    # Добавляем кнопку удаления с уникальным ключом
    delete_key = f"delete_{message_hash}_{role}"  # Уникальный ключ для кнопки удаления
    if st.button("🗑️", key=delete_key, help="Удалить сообщение"):
        return True
    return False 