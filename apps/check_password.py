import hmac
import streamlit as st

from apps.documents import Summary
summary = Summary()

def check_password():
    """Returns `True` if the user had the correct password."""
    def password_entered():
        """Checks whether a password entered by the user is correct."""
        if hmac.compare_digest(st.session_state["password"], st.secrets["password"]):
            st.session_state["password_correct"] = True
            del st.session_state["password"]  # Don't store the password.
        else:
            st.session_state["password_correct"] = False

    # Return True if the password is validated.
    if st.session_state.get("password_correct", False):
        return True
    
    summary.show_sign_in_summary

    # Show input for password.
    st.text_input(
        label='パスワードを入力して下さい。',
        type='password',
        on_change=password_entered, 
        key="password"
    )
    if "password_correct" in st.session_state:
        st.error("😫 パスワードが違います。")
    return False



