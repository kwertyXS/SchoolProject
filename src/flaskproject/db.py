import os

import dotenv
import mysql.connector

dotenv.load_dotenv()
DB_PASSWORD = os.getenv("passwd")


def get_connection():
    return mysql.connector.connect(
        host="185.114.247.43",
        port=3306,
        database="sch688_vvedenie",
        user="sch688_vvedenie",
        password=DB_PASSWORD)
