from pages.assessment_interview_db import get_connection

conn = get_connection()
cursor = conn.cursor()

cursor.execute("""
SELECT column_name, data_type
FROM information_schema.columns
WHERE table_name = 'users'
ORDER BY ordinal_position
""")

for row in cursor.fetchall():
    print(row)

cursor.close()
conn.close()