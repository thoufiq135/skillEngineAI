import psycopg2

DB_CONFIG = {
    "host": "100.117.158.50",
    "port": 5432,
    "user": "admin",
    "password": "admin",
    "dbname": "skill_engine_tho",
}

conn = None
cursor = None

try:
    print("Connecting to PostgreSQL...")

    conn = psycopg2.connect(
        **DB_CONFIG,
        connect_timeout=10
    )

    cursor = conn.cursor()

    print("Connected successfully.\n")

    cursor.execute("""
        SELECT
            column_name,
            data_type,
            is_nullable,
            column_default
        FROM information_schema.columns
        WHERE table_schema = 'public'
          AND table_name = 'attempt_sections'
        ORDER BY ordinal_position;
    """)

    columns = cursor.fetchall()

    print("=" * 70)
    print("TABLE: attempt_sections")
    print("=" * 70)

    for column_name, data_type, is_nullable, column_default in columns:
        print(
            f"{column_name} | "
            f"{data_type} | "
            f"nullable={is_nullable} | "
            f"default={column_default}"
        )

except Exception as error:
    print("Database connection failed:")
    print(error)

finally:
    if cursor:
        cursor.close()

    if conn:
        conn.close()