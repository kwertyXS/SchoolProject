import hashlib
import os
import dotenv
from flask import Flask, render_template, request, abort
import mysql.connector

dotenv.load_dotenv()
DB_PASSWORD = os.getenv("passwd")

app = Flask(__name__)


def get_connection():
    return mysql.connector.connect(
        host="185.114.247.43",
        port=3306,
        database="sch688_vvedenie",
        user="sch688_vvedenie",
        password=DB_PASSWORD)


def hash_password(password, salt=None):
    if salt is None:
        salt = os.urandom(16)
    digest = hashlib.scrypt(password.encode(), salt=salt, n=2 ** 14, r=8, p=1)
    return digest.hex() + "." + salt.hex()


@app.route('/user_register', methods=['POST'])
def user_register():
    req = request.get_json(silent=True)
    if not req or 'name' not in req or 'email' not in req or 'password' not in req:
        abort(400)

    name = req['name']
    login = req['email']
    password = str(req['password'])
    if "." in password:
        abort(400)

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
    except mysql.connector.Error:
        return {"result": False}

    return {
        "result": True,
        "id": new_id
    }


@app.route('/user_login', methods=['POST'])
def user_login():
    req = request.get_json(silent=True)
    if not req or 'email' not in req or 'password' not in req:
        abort(400)

    login = req['email']
    password = str(req['password'])

    try:
        cnx = get_connection()
        try:
            cur = cnx.cursor(dictionary=True)
            cur.execute('SELECT * FROM `users` WHERE email=%s', (login,))
            user = cur.fetchone()
        finally:
            cnx.close()
    except mysql.connector.Error:
        return {"result": False}

    if user is None:
        return {"result": False}

    stored_hash, salt_hex = user['password_hash'].rsplit(".", 1)
    salt = bytes.fromhex(salt_hex)
    password_hash = hashlib.scrypt(password.encode(), salt=salt, n=2 ** 14, r=8, p=1).hex()

    if password_hash == stored_hash:
        return {
            "result": True,
            "id": user['id']
        }
    else:
        return {"result": False}


@app.route("/")
def registration():
    return render_template('registration.html')


@app.route("/login")
def login():
    return render_template('login.html')


if __name__ == "__main__":
    app.run()
