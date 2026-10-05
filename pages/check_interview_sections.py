from pages.assessment_interview_db import get_connection


conn = get_connection()

try:
    cursor = conn.cursor()

    cursor.execute("""
        SELECT
            a.id,
            a.title,
            a.status,
            s.id,
            s.name,
            s.section_type,
            s.interview_mode,
            s.question_count
        FROM assessments a
        JOIN assessment_sections s
            ON s.assessment_id = a.id
        WHERE s.section_type = 'interview'
           OR s.interview_mode IS NOT NULL
        ORDER BY a.created_at DESC;
    """)

    rows = cursor.fetchall()

    print("INTERVIEW ASSESSMENT SECTIONS:")

    if not rows:
        print("No interview sections found.")

    for row in rows:
        print(row)

finally:
    conn.close()