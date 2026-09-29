import hashlib
import os

import mysql.connector
from flask import Blueprint, request, abort, g, jsonify

from .db import get_connection
from .tokens import create_token, login_required, set_token_cookie

import requests

bp = Blueprint('api', __name__, url_prefix='/api')
OPEN_ROUTER_API = os.getenv("OPEN_ROUTER_API")

def hash_password(password, salt=None):
    if salt is None:
        salt = os.urandom(16)
    digest = hashlib.scrypt(password.encode(), salt=salt, n=2 ** 14, r=8, p=1)
    return digest.hex() + "." + salt.hex()


def error(message, status):
    return {"result": False, "message": message}, status


def success(user_id, message):
    # токен отдаётся и в cookie (для страниц), и в ответе (для других клиентов)
    token = create_token(user_id)
    response = jsonify(result=True, id=user_id, token=token, message=message)
    return set_token_cookie(response, user_id)


@bp.route('/register', methods=['POST'])
def user_register():
    req = request.get_json(silent=True) or {}
    # форма шлёт fullname, старые клиенты — name
    name = req.get('fullname') or req.get('name')
    login = req.get('email')
    password = req.get('password')
    if not name or not login or not password:
        return error('Заполните все поля', 400)
    password = str(password)
    if "." in password:
        return error('Пароль не должен содержать точку', 400)

    password_hash = hash_password(password)

    try:
        cnx = get_connection()
        try:
            cur = cnx.cursor()
            cur.execute(
                'INSERT INTO `users`(`username`, `email`, `password_hash`) VALUES (%s, %s, %s)',
                (name, login, password_hash))
            cnx.commit()
            new_id = cur.lastrowid
        finally:
            cnx.close()
    except mysql.connector.IntegrityError:
        return error('Пользователь с таким email уже существует', 409)
    except mysql.connector.Error:
        return error('Ошибка базы данных', 500)

    return success(new_id, 'Регистрация прошла успешно')


@bp.route('/login', methods=['POST'])
def user_login():
    req = request.get_json(silent=True) or {}
    # форма входа шлёт username, в нём email
    login = req.get('email') or req.get('username')
    password = req.get('password')
    if not login or not password:
        return error('Введите логин и пароль', 400)
    password = str(password)

    try:
        cnx = get_connection()
        try:
            cur = cnx.cursor(dictionary=True)
            cur.execute('SELECT * FROM `users` WHERE email=%s', (login,))
            user = cur.fetchone()
        finally:
            cnx.close()
    except mysql.connector.Error:
        return error('Ошибка базы данных', 500)

    if user is None:
        return error('Неверный логин или пароль', 401)

    stored_hash, salt_hex = user['password_hash'].rsplit(".", 1)
    salt = bytes.fromhex(salt_hex)
    password_hash = hashlib.scrypt(password.encode(), salt=salt, n=2 ** 14, r=8, p=1).hex()

    if password_hash == stored_hash:
        return success(user['id'], 'Вы успешно вошли')
    else:
        return error('Неверный логин или пароль', 401)


@bp.route('/me')
@login_required
def me():
    try:
        cnx = get_connection()
        try:
            cur = cnx.cursor(dictionary=True)
            cur.execute('SELECT `id`, `username`, `email` FROM `users` WHERE id=%s', (g.user_id,))
            user = cur.fetchone()
        finally:
            cnx.close()
    except mysql.connector.Error:
        return error('Ошибка базы данных', 500)

    if user is None:
        abort(401)

    return {"result": True, "user": user}


OPENROUTER_URL = "https://openrouter.ai/api/v1/chat/completions"
# конкретные чат-модели: openrouter/free иногда попадает на модель-модератор,
# которая вместо ответа пишет "User Safety: safe". Если первая недоступна — берётся следующая
CHAT_MODELS = [
    "google/gemma-4-31b-it:free",
    "qwen/qwen3.8-27b:free",
    "nvidia/nemotron-3-super-120b-a12b:free",
]
MAX_HISTORY = 20  # сколько последних сообщений отправлять модели


@bp.route('/chat', methods=['POST'])
@login_required
def chat():
    if not OPEN_ROUTER_API:
        return error('OPEN_ROUTER_API не задан в .env', 500)

    req = request.get_json(silent=True) or {}

    # страница шлёт всю историю в messages: [{role, content}, ...], последнее — от пользователя
    history = req.get('messages')
    if not isinstance(history, list):
        history = [{"role": "user", "content": req.get('message')}]

    messages = [
        {"role": m["role"], "content": m["content"]}
        for m in history
        if isinstance(m, dict)
        and m.get("role") in ("user", "assistant")
        and isinstance(m.get("content"), str)
        and m["content"].strip()
    ][-MAX_HISTORY:]
    if not messages or messages[-1]["role"] != "user":
        return error('Пустое сообщение', 400)

    try:
        response = requests.post(
            OPENROUTER_URL,
            headers={"Authorization": f"Bearer {OPEN_ROUTER_API}"},
            json={"models": CHAT_MODELS, "messages": messages},
            timeout=60,
        )
        data = response.json()
    except requests.Timeout:
        return error('ИИ не ответил вовремя, попробуйте ещё раз', 504)
    except (requests.RequestException, ValueError):
        return error('Не удалось связаться с ИИ', 502)

    if not response.ok or "error" in data:
        err = data.get("error")
        message = (err.get("message") if isinstance(err, dict) else err) or f"код {response.status_code}"
        return error(f'Ошибка ИИ: {message}', 502)

    try:
        reply = data["choices"][0]["message"]["content"]
    except (KeyError, IndexError, TypeError):
        return error('ИИ вернул пустой ответ', 502)

    return {"result": True, "reply": reply}
