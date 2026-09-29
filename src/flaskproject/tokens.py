import os
from datetime import datetime, timedelta, timezone
from functools import wraps

import dotenv
from flask import request, abort, g, redirect, url_for
from jwt import JWT
from jwt.exceptions import JWTDecodeError
from jwt.jwk import OctetJWK
from jwt.utils import get_int_from_datetime

dotenv.load_dotenv()
JWT_SECRET = os.getenv("JWT_SECRET")
if not JWT_SECRET:
    raise RuntimeError("JWT_SECRET не задан в .env")

TOKEN_LIFETIME = timedelta(days=7)
COOKIE_NAME = "token"

_jwt = JWT()
_key = OctetJWK(JWT_SECRET.encode())


def create_token(user_id):
    now = datetime.now(timezone.utc)
    payload = {
        "sub": str(user_id),
        "iat": get_int_from_datetime(now),
        "exp": get_int_from_datetime(now + TOKEN_LIFETIME),
    }
    return _jwt.encode(payload, _key, alg="HS256")


def decode_token(token):
    """Возвращает id пользователя или None, если токен неверный или истёк."""
    try:
        payload = _jwt.decode(token, _key, algorithms={"HS256"})
        return int(payload["sub"])
    # на битом токене библиотека кидает не только JWTDecodeError
    except (JWTDecodeError, ValueError, KeyError, TypeError):
        return None


def set_token_cookie(response, user_id):
    response.set_cookie(COOKIE_NAME, create_token(user_id),
                        max_age=int(TOKEN_LIFETIME.total_seconds()),
                        httponly=True, samesite="Lax")
    return response


def clear_token_cookie(response):
    response.delete_cookie(COOKIE_NAME)
    return response


def current_user_id():
    """Токен берётся из cookie, либо из заголовка `Authorization: Bearer <token>`."""
    token = request.cookies.get(COOKIE_NAME)
    header = request.headers.get("Authorization", "")
    if header.startswith("Bearer "):
        token = header[len("Bearer "):]
    if not token:
        return None
    return decode_token(token)


def login_required(view):
    """Для API: без токена — 401. id пользователя кладётся в g.user_id."""
    @wraps(view)
    def wrapper(*args, **kwargs):
        user_id = current_user_id()
        if user_id is None:
            abort(401)
        g.user_id = user_id
        return view(*args, **kwargs)
    return wrapper


def page_login_required(view):
    """Для страниц: без токена — редирект на /login."""
    @wraps(view)
    def wrapper(*args, **kwargs):
        user_id = current_user_id()
        if user_id is None:
            return redirect(url_for("views.login"))
        g.user_id = user_id
        return view(*args, **kwargs)
    return wrapper
