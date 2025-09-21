from frontend import *

if "first_run" not in st.session_state:
    st.session_state.first_run = True
    setting_defaults()

    
st.set_page_config(
    page_title="AI Study Assistant",
    page_icon="📘",
    layout=st.session_state.app_layout,
    initial_sidebar_state="expanded",
)
st.title("📘 AI Study Assistant")

login_or_signup_alert = st.empty()

if not st.session_state.logged_in:
    login_or_signup_alert.info("Enter your username and password to proceed!")
    if not st.session_state.reset_password:
        login_or_signup()           # Login or signup function
    else:
        reset_password()            # Reset password functionality
else:
    if st.session_state.shown_login_alert:
        login_or_signup_alert.success(f"Logged in as {st.session_state.username}")
        time.sleep(1)
        login_or_signup_alert.empty()
        st.session_state.shown_login_alert = True

    menu = ["🏠 Home","📤 Temporary Chat", "🧠 Chat with AI", "📖 Open a chapter"]

    for i, item in enumerate(menu):
        if st.sidebar.button(item, key=f"nav_{i}"):
            st.session_state.page = item
            st.rerun()

    # ===== Pages =====
    if st.session_state.page == "📤 Temporary Chat":
        temporary_chat()
    elif st.session_state.page == "🏠 Home":
        home_page()
    elif st.session_state.page == "📖 Open a chapter":
        open_a_chapter()
    if st.session_state.page == "🧠 Chat with AI":
        chat_with_AI()
    else:
        st.session_state.opened_chat_with_AI = False

    with st.sidebar:
        st.markdown("---")
        logout(setting_defaults)

