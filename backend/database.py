
import psycopg2


# ============================================================
# DATABASE CONFIGURATION
# ============================================================

DB_HOST = "100.96.84.42"
DB_PORT = 5432
DB_NAME = "skill_engine_tho"
DB_USER = "admin"
DB_PASSWORD = "admin"


# ============================================================
# DATABASE CONNECTION
# ============================================================

def get_db_connection():
    connection = psycopg2.connect(
        host=DB_HOST,
        port=DB_PORT,
        dbname=DB_NAME,
        user=DB_USER,
        password=DB_PASSWORD,
        connect_timeout=5
    )

    return connection


# ============================================================
# CONNECTION TEST
# ============================================================

if __name__ == "__main__":

    print("=" * 60)
    print("DATABASE CONFIGURATION")
    print("=" * 60)

    print("DB_HOST:", DB_HOST)
    print("DB_PORT:", DB_PORT)
    print("DB_NAME:", DB_NAME)
    print("DB_USER:", DB_USER)
    print("DB_PASSWORD:", "********")
    print("=" * 60)

    connection = None
    cursor = None

    try:
        connection = get_db_connection()
        cursor = connection.cursor()

        print("PostgreSQL Connected Successfully")

        cursor.execute(
            "SELECT current_database(), current_schema();"
        )

        database_name, schema_name = cursor.fetchone()

        print("CONNECTED DATABASE:", database_name)
        print("CURRENT SCHEMA:", schema_name)

        cursor.execute(
            "SELECT to_regclass('public.attempt_questions');"
        )

        table_name = cursor.fetchone()[0]

        print("attempt_questions:", table_name)

    except psycopg2.Error as error:
        print("Database connection failed:", error)

    finally:
        if cursor is not None:
            cursor.close()

        if connection is not None:
            connection.close()

        print("Database connection closed.")
