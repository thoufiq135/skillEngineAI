from backend.api import get_db_connection


connection = get_db_connection()
cursor = connection.cursor()

print("\nDATABASE INFO:\n")

cursor.execute("""
    SELECT
        current_database(),
        current_schema(),
        inet_server_addr(),
        inet_server_port()
""")

print(cursor.fetchone())


print("\nASSESSMENT_SECTIONS TABLES:\n")

cursor.execute("""
    SELECT
        table_schema,
        table_name
    FROM information_schema.tables
    WHERE table_name = 'assessment_sections'
""")

for row in cursor.fetchall():
    print(row)


print("\nALL CONSTRAINTS ON assessment_sections:\n")

cursor.execute("""
    SELECT
        n.nspname AS schema_name,
        c.relname AS table_name,
        con.conname AS constraint_name,
        pg_get_constraintdef(con.oid) AS constraint_definition
    FROM pg_constraint con
    JOIN pg_class c
        ON c.oid = con.conrelid
    JOIN pg_namespace n
        ON n.oid = c.relnamespace
    WHERE c.relname = 'assessment_sections'
    ORDER BY con.conname
""")

rows = cursor.fetchall()

if not rows:
    print("NO CONSTRAINTS FOUND")

for row in rows:
    print(row)


cursor.close()
connection.close()