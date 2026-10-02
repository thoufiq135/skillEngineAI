from backend.database import get_db_connection

conn = get_db_connection()
cur = conn.cursor()

cur.execute("""
    SELECT
        table_name,
        column_name,
        data_type
    FROM information_schema.columns
    WHERE table_schema = 'public'
    ORDER BY table_name, ordinal_position
""")

rows = cur.fetchall()

current_table = None

for table_name, column_name, data_type in rows:

    if table_name != current_table:
        print("\n" + "=" * 60)
        print(f"TABLE: {table_name}")
        print("=" * 60)
        current_table = table_name

    print(f"  {column_name} -> {data_type}")

cur.close()
conn.close()