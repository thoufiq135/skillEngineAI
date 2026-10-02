import os
import psycopg2
from dotenv import load_dotenv


# ============================================================
# LOAD BACKEND .ENV
# ============================================================

BASE_DIR = os.path.dirname(
    os.path.abspath(__file__)
)

ENV_PATH = os.path.join(
    BASE_DIR,
    ".env"
)

load_dotenv(
    dotenv_path=ENV_PATH,
    override=True
)


# ============================================================
# DATABASE CONNECTION
# ============================================================

def get_db_connection():

    connection = psycopg2.connect(
        host=os.getenv("DB_HOST"),
        port=os.getenv("DB_PORT"),
        database=os.getenv("DB_NAME"),
        user=os.getenv("DB_USER"),
        password=os.getenv("DB_PASSWORD")
    )

    return connection


# ============================================================
# CONNECTION TEST
# ============================================================

if __name__ == "__main__":

    print()
    print("============================================================")
    print("DATABASE CONFIGURATION")
    print("============================================================")

    print(
        "ENV PATH:",
        ENV_PATH
    )

    print(
        "ENV EXISTS:",
        os.path.exists(ENV_PATH)
    )

    print(
        "DB_HOST:",
        os.getenv("DB_HOST")
    )

    print(
        "DB_PORT:",
        os.getenv("DB_PORT")
    )

    print(
        "DB_NAME:",
        os.getenv("DB_NAME")
    )

    print(
        "DB_USER:",
        os.getenv("DB_USER")
    )

    print(
        "DB_PASSWORD:",
        "********" if os.getenv("DB_PASSWORD") else None
    )

    print("============================================================")
    print()


    # ========================================================
    # TEST CONNECTION
    # ========================================================

    try:

        connection = get_db_connection()

        print(
            "✅ PostgreSQL Connected Successfully"
        )

        # ----------------------------------------------------
        # Verify actual database
        # ----------------------------------------------------

        cursor = connection.cursor()

        cursor.execute(
            "SELECT current_database(), current_schema();"
        )

        database_name, schema_name = cursor.fetchone()

        print(
            "CONNECTED DATABASE:",
            database_name
        )

        print(
            "CURRENT SCHEMA:",
            schema_name
        )

        # ----------------------------------------------------
        # Verify attempt_questions table
        # ----------------------------------------------------

        cursor.execute(
            """
            SELECT to_regclass('public.attempt_questions');
            """
        )

        table_name = cursor.fetchone()[0]

        print(
            "attempt_questions:",
            table_name
        )

        cursor.close()
        connection.close()

        print()
        print(
            "✅ Connection Closed"
        )

        print(
            "============================================================"
        )

    except Exception as e:

        print()
        print(
            "❌ Database connection failed:"
        )

        print(
            e
        )

        print(
            "============================================================"
        )