import sqlite3
import os

print("Files in root:", [f for f in os.listdir('.') if f.endswith('.db')])

db_path = "asteria.db" if os.path.exists("asteria.db") else "backend/asteria.db"
conn = sqlite3.connect(db_path)
cursor = conn.cursor()

cursor.execute("SELECT COUNT(*) FROM telemetry_history;")
count = cursor.fetchone()[0]
print(f"COUNT in {db_path}: {count}")

cursor.execute("SELECT * FROM telemetry_history LIMIT 10;")
rows = cursor.fetchall()
for row in rows:
    print(row)

conn.close()
