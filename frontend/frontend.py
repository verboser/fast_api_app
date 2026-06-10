import streamlit as st
import requests
from streamlit_cookies_manager import EncryptedCookieManager
import os


API_URL = "http://web:8000"

st.set_page_config(page_title="Task Manager", page_icon="📝", layout="centered")

st.markdown(
    """
    <style>
    button[title="Удалить заметку"] {
        transition: all 0.2s ease-in-out;
    }
    button[title="Удалить заметку"]:hover {
        background-color: #ff4b4b !important;
        color: white !important;
        transform: scale(1.15); /* Слегка увеличиваем кнопку */
        border-color: #ff4b4b !important;
    }
    </style>
    """,
    unsafe_allow_html=True
)

cookies = EncryptedCookieManager(
    prefix="task_manager",
    password="super_secret_password_for_cookies"
)

if not cookies.ready():
    st.stop()

if 'token' not in st.session_state:
    st.session_state['token'] = cookies.get('jwt_token')
if 'page' not in st.session_state:
    st.session_state['page'] = 'login'


def get_auth_headers():
    return {"Authorization": f"Bearer {st.session_state['token']}"}


def fetch_tasks():
    try:
        res = requests.get(f"{API_URL}/tasks/", headers=get_auth_headers())
        if res.status_code == 200:
            return res.json()
    except requests.exceptions.ConnectionError:
        st.error("Не удалось подключиться к серверу бэкенда.")
    return []


def create_task(title, descr, status, priority):
    payload = {"title": title, "descr": descr, "status": status, "priority": priority}
    requests.post(f"{API_URL}/tasks/", json=payload, headers=get_auth_headers())


def delete_task(task_id):
    requests.delete(f"{API_URL}/tasks/{task_id}", headers=get_auth_headers())


def perform_logout():
    st.session_state['token'] = None
    st.session_state['page'] = 'login'
    cookies['jwt_token'] = ""  # Затираем куки
    cookies.save()


if st.session_state['page'] == 'login' and not st.session_state['token']:
    st.subheader("🔑 Вход в аккаунт")

    with st.form("login_form"):
        username = st.text_input("Логин")
        password = st.text_input("Пароль", type="password")
        submit_login = st.form_submit_button("Войти", use_container_width=True)

        if submit_login:
            if username and password:
                res = requests.post(f"{API_URL}/login/", data={"username": username, "password": password})
                if res.status_code == 200:
                    token = res.json().get("access_token")
                    st.session_state['token'] = token
                    cookies['jwt_token'] = token
                    cookies.save()

                    st.success("Успешный вход!")
                    st.rerun()
                else:
                    st.error("Неверный логин или пароль")
            else:
                st.warning("Пожалуйста, заполните все поля")

    st.write("")
    col1, col2 = st.columns([3, 1])
    with col1:
        st.write("Нет аккаунта?")
    with col2:
        if st.button("Зарегистрироваться", type="tertiary"):
            st.session_state['page'] = 'register'
            st.rerun()

elif st.session_state['page'] == 'register' and not st.session_state['token']:
    st.subheader("📝 Регистрация нового аккаунта")

    with st.form("register_form"):
        new_username = st.text_input("Придумайте логин")
        new_password = st.text_input("Придумайте пароль", type="password")
        submit_register = st.form_submit_button("Создать аккаунт", use_container_width=True)

        if submit_register:
            if new_username and new_password:
                res = requests.post(f"{API_URL}/register/", json={"login": new_username, "password": new_password})
                if res.status_code == 200:
                    login_res = requests.post(f"{API_URL}/login/",
                                              data={"username": new_username, "password": new_password})
                    if login_res.status_code == 200:
                        token = login_res.json().get("access_token")
                        st.session_state['token'] = token
                        cookies['jwt_token'] = token
                        cookies.save()

                        st.success("Аккаунт создан! Входим в систему...")
                        st.rerun()
                    else:
                        st.session_state['page'] = 'login'
                        st.rerun()
                else:
                    st.error("Ошибка при регистрации. Возможно, этот логин уже занят.")
            else:
                st.warning("Пожалуйста, заполните все поля")

    st.write("")
    col1, col2 = st.columns([3, 1])
    with col1:
        st.write("Уже есть аккаунт?")
    with col2:
        if st.button("Войти", type="tertiary"):
            st.session_state['page'] = 'login'
            st.rerun()

else:
    st.title("Менеджер задач")
    col_space, col_logout = st.columns([5, 1])
    with col_logout:
        st.button("Выйти 🚪", type="secondary", use_container_width=True, on_click=perform_logout)

    st.divider()

    with st.expander("  Создать новую задачу / заметку"):
        with st.form("task_creation_form", clear_on_submit=True):
            title = st.text_input("Название задачи*")
            descr = st.text_area("Описание задачи")
            c1, c2 = st.columns(2)
            status = c1.selectbox("Статус", ["New", "In Progress", "Done"])
            priority = c2.number_input("Приоритет (1-5)", min_value=1, max_value=5, value=1)

            save_button = st.form_submit_button("Сохранить", use_container_width=True)
            if save_button and title:
                create_task(title, descr, status, priority)
                st.success("Задача успешно добавлена!")
                st.rerun()

    st.subheader("  Ваши текущие задачи")
    tasks = fetch_tasks()

    if not tasks:
        st.info("Создайте свою первую заметку")
    else:
        for task in tasks:
            with st.container(border=True):
                col_text, col_action = st.columns([9, 1])
                with col_text:
                    st.markdown(f"### {task['title']}")
                    st.caption(f" Статус: **{task['status']}** |  Приоритет: **{task['priority']}**")
                    if task.get('descr'):
                        st.write(task['descr'])
                with col_action:
                    st.write("")
                    if st.button("🗑️", key=f"del_{task['id']}", type="tertiary", help="Удалить заметку"):
                        delete_task(task['id'])
                        st.rerun()

    if st.button("Сымитировать падение сервера"):
        os._exit(1)