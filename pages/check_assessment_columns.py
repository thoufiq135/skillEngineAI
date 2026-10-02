import psycopg2

DB_CONFIG = {
    "host": "100.117.158.50",
    "port": 5432,
    "user": "admin",
    "password": "admin",
    "dbname": "skill_engine_tho",
}

TABLES = [
    "assessments",
    "assessment_sections",
    "assessment_section_questions",
    "assessment_attempts",
    "attempt_questions",
    "interview_questions",
    "interview_answers",
    "interview_evaluations",
]

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

    for table in TABLES:

        print("\n" + "=" * 70)
        print("TABLE:", table)
        print("=" * 70)

        cursor.execute("""
            SELECT
                column_name,
                data_type,
                is_nullable,
                column_default
            FROM information_schema.columns
            WHERE table_schema = 'public'
              AND table_name = %s
            ORDER BY ordinal_position;
        """, (table,))

        columns = cursor.fetchall()

        if not columns:
            print("No columns found.")
            continue

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