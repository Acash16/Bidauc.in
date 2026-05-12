import sqlite3
conn = sqlite3.connect('auction.db')
cursor = conn.cursor()
cursor.execute('''
CREATE TABLE IF NOT EXISTS newsletter (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    email TEXT UNIQUE,
    subscribed_at DATETIME DEFAULT CURRENT_TIMESTAMP
)
''')
conn.commit()
conn.close()
print("✅ Newsletter table created!")