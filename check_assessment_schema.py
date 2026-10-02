from pages.assessment_interview_db import get_connection

conn = get_connection()
cur = conn.cursor()

tables = [
    "assessments",
    "assessment_sections",
    "assessment_section_questions",
    "assessment_attempts",
    "attempt_sections",
    "attempt_questions"
]

for table in tables:
    print("\nTABLE:", table)
    cur.execute("""
        SELECT column_name, data_type, is_nullable, column_default
        FROM information_schema.columns
        WHERE table_name = %s
        ORDER BY ordinal_position
    """, (table,))

    for row in cur.fetchall():
        print(row)

cur.close()
conn.close()
