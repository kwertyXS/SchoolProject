import hashlib
import os

import mysql.connector
from flask import Blueprint, request, abort, g, jsonify

from .db import get_connection
from .tokens import create_token, login_required, set_token_cookie

bp = Blueprint('api', __name__, url_prefix='/api')


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
