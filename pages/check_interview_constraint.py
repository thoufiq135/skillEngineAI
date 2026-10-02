import psycopg2

DB_CONFIG = {
    "host": "100.117.158.50",
    "port": 5432,
    "user": "admin",
    "password": "admin",
    "dbname": "skill_engine_tho",
}

conn = psycopg2.connect(**DB_CONFIG)

try:
    cursor = conn.cursor()

    print("\nDATABASE:")
    cursor.execute("SELECT current_database();")
    print(cursor.fetchone())

    print("\nASSESSMENT_SECTIONS COLUMNS:")
    cursor.execute("""
        SELECT
            column_name,
            data_type
        FROM information_schema.columns
        WHERE table_name = 'assessment_sections'
        ORDER BY ordinal_position;
    """)

    for row in cursor.fetchall():
        print(row)

    print("\nINTERVIEW MODE CONSTRAINT:")
    cursor.execute("""
        SELECT
            conname,
            pg_get_constraintdef(oid)
        FROM pg_constraint
        WHERE conrelid = 'assessment_sections'::regclass
          AND conname = 'assessment_sections_interview_mode_check';
    """)

    rows = cursor.fetchall()

    if not rows:
        print("CONSTRAINT NOT FOUND")
    else:
        for row in rows:
            print(row)

finally:
    cursor.close()
    conn.close()