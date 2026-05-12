import sqlite3

conn = sqlite3.connect('auction.db')
cursor = conn.cursor()

migrations = [
    "ALTER TABLE auctions ADD COLUMN buy_now_price REAL DEFAULT NULL",
    "ALTER TABLE auctions ADD COLUMN sold_mode TEXT DEFAULT 'manual'",
    "ALTER TABLE auctions ADD COLUMN sold_to INTEGER DEFAULT NULL",
]

for sql in migrations:
    try:
        cursor.execute(sql)
        print(f"✅ Done: {sql}")
    except sqlite3.OperationalError as e:
        print(f"⚠️  Skipped (already exists?): {e}")

conn.commit()
conn.close()
print("\n✅ Migration complete. Your auction.db is ready.")