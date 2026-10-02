import psycopg2

c = psycopg2.connect(
    host="100.117.158.50",
    port=5432,
    database="skill_engin_test",
    user="admin",
    password="admin"
)

cur = c.cursor()

cur.execute(
    "SELECT id, email, role, is_active FROM users WHERE email = %s",
    ("test@example.com",)
)

print(cur.fetchall())

cur.close()
c.close()