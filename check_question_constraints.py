from pages.assessment_interview_db import get_connection

conn = get_connection()
cur = conn.cursor()

cur.execute("""
SELECT
    conname,
    pg_get_constraintdef(oid)
FROM pg_constraint
WHERE conrelid = 'questions'::regclass
""")

for row in cur.fetchall():
    print(row)

cur.close()
conn.close()
