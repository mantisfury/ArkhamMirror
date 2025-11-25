# Authentication module for ArkhamMirror
# This provides a simple wrapper for streamlit-authenticator

import streamlit as st
import yaml
from yaml.loader import SafeLoader
import streamlit_authenticator as stauth


def check_authentication():
    """
    Check if the user is authenticated. Returns True if logged in, False otherwise.
    Handles the login UI automatically.
    """
    # Load config
    try:
        with open("config.yaml") as file:
            config = yaml.load(file, Loader=SafeLoader)
    except FileNotFoundError:
        st.error("config.yaml not found")
        st.stop()

    # Initialize authenticator
    authenticator = stauth.Authenticate(
        config["auth"]["credentials"],
        config["auth"]["cookie"]["name"],
        config["auth"]["cookie"]["key"],
        config["auth"]["cookie"]["expiry_days"],
    )

    # Render login widget
    try:
        authenticator.login()
    except Exception as e:
        st.error(f"Authentication Error: {e}")
        st.stop()

    # Check status
    if st.session_state.get("authentication_status"):
        # User is logged in
        with st.sidebar:
            st.write(f"Welcome *{st.session_state['name']}*")
            authenticator.logout("Logout", "main")
            st.divider()
        return True
    elif st.session_state.get("authentication_status") is False:
        st.error("Username/password is incorrect")
        st.stop()
    else:
        st.warning("Please enter your username and password")
        st.stop()
