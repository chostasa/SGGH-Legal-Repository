import os
import uuid
import streamlit as st

def get_session_id() -> str:
    if "secure_session_id" not in st.session_state:
        st.session_state["secure_session_id"] = str(uuid.uuid4())
    return st.session_state["secure_session_id"]

def get_secure_temp_dir(base_dir="temp") -> str:
    session_id = get_session_id()
    path = os.path.join(base_dir, session_id)
    os.makedirs(path, exist_ok=True)
    return path

def get_session_temp_dir(base_dir="temp") -> str:
    """
    Alias for backwards compatibility.
    """
    return get_secure_temp_dir(base_dir)
