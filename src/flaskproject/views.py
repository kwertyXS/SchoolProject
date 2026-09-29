from flask import Blueprint, render_template, redirect, url_for

from .tokens import page_login_required, clear_token_cookie

bp = Blueprint('views', __name__)


@bp.route("/")
def registration():
    return render_template('registration.html')


@bp.route("/login")
def login():
    return render_template('login.html')


@bp.route("/logout")
def logout():
    return clear_token_cookie(redirect(url_for('views.login')))


@bp.route("/chat")
@page_login_required
def chat():
    return render_template('chat.html')


@bp.route("/buy")
@page_login_required
def buy():
    return render_template('buy.html')
