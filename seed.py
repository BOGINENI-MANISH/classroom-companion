import sqlite3

MY_ID =5849123744 # Replace with your numeric Telegram ID

conn = sqlite3.connect("classroom.db")
cursor = conn.cursor()
cursor.execute("INSERT OR IGNORE INTO users (telegram_id, role, name) VALUES (?, 'teacher', 'My Name')", (MY_ID,))

# Add a dummy student linked to you for testing
cursor.execute("INSERT OR IGNORE INTO users (telegram_id, role, name, teacher_id) VALUES (999, 'student', 'Riya', ?)", (MY_ID,))

conn.commit()
conn.close()
print("Test data seeded!")