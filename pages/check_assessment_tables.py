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
        SELECT table_schema, table_name
        FROM information_schema.tables
        WHERE table_schema NOT IN ('pg_catalog', 'information_schema')
        ORDER BY table_schema, table_name;
    """)

    rows = cursor.fetchall()

    print("DATABASE TABLES")
    print("=" * 70)

    for schema, table in rows:
        print(f"{schema}.{table}")

except Exception as error:
    print("Database connection failed:")
    print(error)

finally:
    if cursor:
        cursor.close()

    if conn:
        conn.close()