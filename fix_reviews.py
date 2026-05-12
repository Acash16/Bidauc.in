import sqlite3

def create_table():
    conn = sqlite3.connect('auction.db')
    cursor = conn.cursor()
    
    print("Creating reviews table...")
    cursor.execute('''
    CREATE TABLE IF NOT EXISTS reviews (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id INTEGER,
        stars INTEGER,
        comment TEXT,
        timestamp DATETIME DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY (user_id) REFERENCES users(id)
    )
    ''')
    
    conn.commit()
    conn.close()
    print("✅ Success! Reviews table created.")

if __name__ == "__main__":
    create_table()