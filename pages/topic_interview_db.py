"""
import os
import time
import psycopg2
from dotenv import load_dotenv

load_dotenv()

DB_CONFIG = {
    "host": "100.117.158.50",
    "port": 5432,
    "user": "admin",
    "password": "admin",
    "dbname": "skill_engine_tho",
}


def connect_db():
    while True:
        try:
            conn = psycopg2.connect(**DB_CONFIG)

            print("✅ PostgreSQL Connected")

            return conn

        except Exception as err:
            print(f"❌ Database connection failed: {err}")
            print("Retrying in 10 seconds...")
            time.sleep(10)


conn = connect_db()
"""

import psycopg2

DB_CONFIG = {
    "host": "100.117.158.50",
    "port": 5432,
    "user": "admin",
    "password": "admin",
    "dbname": "skill_engine_tho",
}

try:
    print("🔄 Trying to connect to PostgreSQL...")

    conn = psycopg2.connect(
        host=DB_CONFIG["host"],
        port=DB_CONFIG["port"],
        user=DB_CONFIG["user"],
        password=DB_CONFIG["password"],
        dbname=DB_CONFIG["dbname"],
        connect_timeout=10
    )

    print("✅ PostgreSQL Connected")

except Exception as err:
    print("❌ Database connection failed")
    print("ERROR:", err)