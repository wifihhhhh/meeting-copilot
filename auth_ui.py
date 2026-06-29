import streamlit as st

from services.auth_service import AuthError, AuthService


def current_user_id() -> int | None:
    return st.session_state.get("user_id")


def current_username() -> str:
    return st.session_state.get("username", "")


def require_login() -> int:
    user_id = current_user_id()
    if user_id is None:
        st.warning("请先登录后再使用该功能。")
        render_auth_forms()
        st.stop()
    return int(user_id)


def render_user_box() -> None:
    if current_user_id() is None:
        return
    with st.sidebar:
        st.divider()
        st.caption("当前账号")
        st.write(f"**{st.session_state.get('display_name') or current_username()}**")
        st.caption(f"用户名：{current_username()}")
        if st.button("退出登录", use_container_width=True):
            logout()
            st.toast("已退出登录")
            st.rerun()


def render_auth_forms() -> None:
    auth = AuthService()
    st.markdown("### 进入工作台")
    login_tab, register_tab = st.tabs(["登录", "注册"])

    with login_tab:
        with st.form("login_form"):
            username = st.text_input("用户名", key="login_username")
            password = st.text_input("密码", type="password", key="login_password")
            submitted = st.form_submit_button("登录", type="primary", use_container_width=True)
        if submitted:
            try:
                user = auth.authenticate(username, password)
                set_current_user(user.id, user.username, user.display_name)
                st.toast("登录成功")
                st.rerun()
            except AuthError as exc:
                st.error(str(exc))

    with register_tab:
        with st.form("register_form"):
            username = st.text_input("用户名", key="register_username", help="至少 3 个字符，登录时使用")
            display_name = st.text_input("显示名称", key="register_display_name", help="页面上展示的名字，可与用户名不同")
            password = st.text_input("密码", type="password", key="register_password", help="至少 6 个字符")
            password2 = st.text_input("确认密码", type="password", key="register_password2")
            submitted = st.form_submit_button("创建账号", type="primary", use_container_width=True)
        if submitted:
            if password != password2:
                st.error("两次输入的密码不一致。")
            else:
                try:
                    user = auth.register(username, password, display_name)
                    set_current_user(user.id, user.username, user.display_name)
                    st.toast("注册成功，已自动登录")
                    st.rerun()
                except AuthError as exc:
                    st.error(str(exc))


def set_current_user(user_id: int, username: str, display_name: str) -> None:
    st.session_state.user_id = user_id
    st.session_state.username = username
    st.session_state.display_name = display_name


def logout() -> None:
    for key in ("user_id", "username", "display_name", "current_meeting_id", "current_minutes", "current_markdown"):
        st.session_state.pop(key, None)
