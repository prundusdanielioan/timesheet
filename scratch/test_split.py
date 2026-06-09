import sqlite3
import re

conn = sqlite3.connect('timesheet.db')
conn.row_factory = sqlite3.Row
logs = conn.execute('SELECT date, tasks_summary FROM logs WHERE tasks_summary IS NOT NULL AND tasks_summary != ""').fetchall()
conn.close()

pattern = re.compile(r';|\r?\n|,(?=\s*(?:Epic|Bug|Issue|Pull Request|PR|Task)\b)', re.IGNORECASE)

for log in logs:
    tasks_text = log['tasks_summary']
    raw_tasks = pattern.split(tasks_text)
    tasks_lines = [t.strip() for t in raw_tasks if t.strip()]
    print(f"Date: {log['date']}")
    print(f"  Original: {tasks_text!r}")
    print("  Split:")
    for line in tasks_lines:
        print(f"    - {line}")
    print("-" * 50)
