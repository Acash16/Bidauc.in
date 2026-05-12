from flask import Flask, render_template, request, redirect, session, jsonify
from config import Config
from flask_bcrypt import Bcrypt
from auction_scheduler import auctions_bp
import os
import sqlite3
import requests

# ── ALGORITHMS ─────────────────────────────
from algorithms import (
    get_cheapest_biddable,
    get_leading_bid,
    is_duplicate_bid,
    clear_bid_cache,
    validate_bid_amount,
    start_scheduler,
    get_sorted_bid_history,
    push_bid_to_feed,
    get_live_feed,
)

app = Flask(__name__)
app.secret_key = Config.SECRET_KEY
app.register_blueprint(auctions_bp, url_prefix="/api/auctions")
bcrypt = Bcrypt(app)

# ── START SCHEDULER ───────────────────────
start_scheduler(interval_seconds=60)


# ── DATABASE FUNCTION ─────────────────────
def get_db():
    conn = sqlite3.connect('auction.db', timeout=10)
    conn.execute("PRAGMA journal_mode=WAL")
    return conn


# ── CREATE TABLES ─────────────────────────
def init_db():
    conn = get_db()
    cursor = conn.cursor()

    cursor.execute('''
    CREATE TABLE IF NOT EXISTS users (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        name TEXT,
        mobile TEXT,
        email TEXT UNIQUE,
        password TEXT
    )
    ''')

    # NOTE: category column added between image and start_price
    # Column order: id, title, description, image, category,
    #               start_price, current_bid, end_time, seller_id, status
    cursor.execute('''
    CREATE TABLE IF NOT EXISTS auctions (
        id          INTEGER PRIMARY KEY AUTOINCREMENT,
        title       TEXT,
        description TEXT,
        image       TEXT,
        category    TEXT,
        start_price REAL,
        current_bid REAL,
        end_time    TEXT,
        seller_id   INTEGER,
        status      TEXT DEFAULT 'active'
    )
    ''')

    cursor.execute('''
    CREATE TABLE IF NOT EXISTS bids (
        id         INTEGER PRIMARY KEY AUTOINCREMENT,
        auction_id INTEGER,
        user_id    INTEGER,
        bid_amount REAL
    )
    ''')

    cursor.execute('''
    CREATE TABLE IF NOT EXISTS wishlist (
        id         INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id    INTEGER,
        auction_id INTEGER,
        FOREIGN KEY (user_id)    REFERENCES users(id),
        FOREIGN KEY (auction_id) REFERENCES auctions(id)
    )
    ''')

    cursor.execute('''
    CREATE TABLE IF NOT EXISTS reviews (
        id        INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id   INTEGER,
        stars     INTEGER,
        comment   TEXT,
        timestamp DATETIME DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY (user_id) REFERENCES users(id)
    )
    ''')

    cursor.execute('''
    CREATE TABLE IF NOT EXISTS newsletter (
        id    INTEGER PRIMARY KEY AUTOINCREMENT,
        email TEXT UNIQUE
    )
    ''')

    conn.commit()
    conn.close()

init_db()


# ── COLUMN HELPER ─────────────────────────
def row_to_auction(row):
   
    return {
        "id":          row[0],
        "title":       row[1],
        "description": row[2],
        "image":       row[3],
        "start_price": float(row[4]) if row[4] else 0.0,
        "current_bid": float(row[5]) if row[5] else (float(row[4]) if row[4] else 0.0),
        "end_time":    row[6],
        "seller_id":   row[7],
        "status":      row[8] or "active",
        "category":    row[9] if len(row) > 9 and row[9] else "General",
        "buy_now_price": float(row[10]) if len(row) > 10 and row[10] else None,
        "sold_mode":     row[11] if len(row) > 11 and row[11] else "manual",
        "sold_to":       row[12] if len(row) > 12 else None,
    }
# ── EXPIRE AUCTIONS ───────────────────────
def expire_auctions():
    conn = None
    try:
        conn = get_db()
        conn.execute("""
            UPDATE auctions
            SET status = 'ended'
            WHERE status = 'active'
            AND end_time <= datetime('now')
        """)
        conn.commit()
    except Exception as e:
        print(f"expire_auctions error: {e}")
    finally:
        if conn:
            conn.close()


# ── HOME ─────────────────────────────────
@app.route('/')
def home():
    expire_auctions()

    selected_cat = request.args.get('cat', 'All')

    conn = get_db()
    cursor = conn.cursor()

    # Stats
    cursor.execute("SELECT COUNT(*) FROM auctions WHERE status = 'active'")
    active_raw = cursor.fetchone()[0]

    cursor.execute("SELECT COUNT(*) FROM users")
    users_raw = cursor.fetchone()[0]

    cursor.execute("SELECT SUM(bid_amount) FROM bids")
    bids_sum_raw = cursor.fetchone()[0] or 0

    stats = {
        "active_val":    f"{active_raw/1000:.1f}" if active_raw >= 1000 else active_raw,
        "active_suffix": "K" if active_raw >= 1000 else "",
        "user_val":      f"{users_raw/100000:.1f}" if users_raw >= 100000 else (f"{users_raw/1000:.1f}" if users_raw >= 1000 else users_raw),
        "user_suffix":   "L" if users_raw >= 100000 else ("K" if users_raw >= 1000 else ""),
        "bids_val":      f"{bids_sum_raw/10000000:.1f}" if bids_sum_raw >= 10000000 else (f"{bids_sum_raw/100000:.1f}" if bids_sum_raw >= 100000 else f"{bids_sum_raw:,.0f}"),
        "bids_suffix":   "Cr" if bids_sum_raw >= 10000000 else ("L" if bids_sum_raw >= 100000 else "")
    }

    # Reviews
    cursor.execute("""
        SELECT users.name, reviews.stars, reviews.comment
        FROM reviews
        JOIN users ON reviews.user_id = users.id
        ORDER BY reviews.id DESC LIMIT 6
    """)
    reviews_list = [
        {
            "name":     r[0],
            "stars":    "★" * r[1] + "☆" * (5 - r[1]),
            "comment":  r[2],
            "initials": r[0][0].upper() if r[0] else "?"
        }
        for r in cursor.fetchall()
    ]

    # Auctions
    if selected_cat and selected_cat != "All":
        cursor.execute("""
            SELECT * FROM auctions
            WHERE status = 'active'
            AND end_time > datetime('now')
            AND LOWER(category) LIKE ?
            ORDER BY end_time ASC
        """, (selected_cat.lower() + '%',))
    else:
        cursor.execute("""
            SELECT * FROM auctions
            WHERE status = 'active'
            AND end_time > datetime('now')
            ORDER BY end_time ASC
        """)

    auctions = [row_to_auction(row) for row in cursor.fetchall()]
    conn.close()

    return render_template(
        "index.html",
        auctions=auctions,
        current_category=selected_cat,
        stats=stats,
        reviews_list=reviews_list,
        user=session.get('user_id'),
        user_name=session.get('user_name')
    )


# ── SIGNUP ───────────────────────────────
@app.route('/signup', methods=['GET', 'POST'])
def signup():
    if request.method == 'POST':
        conn = get_db()
        cursor = conn.cursor()

        name     = request.form['name']
        mobile   = request.form['mobile']
        email    = request.form['email']
        password = request.form['password']

        hashed = bcrypt.generate_password_hash(password).decode('utf-8')

        cursor.execute("SELECT * FROM users WHERE email=?", (email,))
        if cursor.fetchone():
            conn.close()
            return "User already exists"

        cursor.execute(
            "INSERT INTO users (name, mobile, email, password) VALUES (?, ?, ?, ?)",
            (name, mobile, email, hashed)
        )
        conn.commit()
        conn.close()
        return redirect('/login')

    return render_template("signup.html")


# ── LOGIN ───────────────────────────────
@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        conn = get_db()
        cursor = conn.cursor()

        email    = request.form['email']
        password = request.form['password']

        cursor.execute("SELECT * FROM users WHERE email=?", (email,))
        user = cursor.fetchone()
        conn.close()

        if user and bcrypt.check_password_hash(user[4], password):
            session['user_id']   = user[0]
            session['user_name'] = user[1]
            return redirect('/dashboard')

        return render_template("login.html", error="Invalid email or password")

    return render_template("login.html")


# ── DASHBOARD ─────────────────────────────
@app.route('/dashboard')
def dashboard():
    if 'user_id' not in session:
        return redirect('/login')

    conn = get_db()
    cursor = conn.cursor()

    cursor.execute("""
        SELECT * FROM auctions
        WHERE seller_id = ?
        ORDER BY id DESC
    """, (session['user_id'],))
    auctions = cursor.fetchall()

    cursor.execute("""
        SELECT bids.id, bids.auction_id, bids.user_id, bids.bid_amount, auctions.title
        FROM bids
        JOIN auctions ON bids.auction_id = auctions.id
        WHERE bids.user_id = ?
        ORDER BY bids.id DESC
    """, (session['user_id'],))
    bids = cursor.fetchall()

    conn.close()

    return render_template(
        "dashboard.html",
        auctions=auctions,
        bids=bids,
        cheapest_biddable=get_cheapest_biddable(session['user_id'])
    )


# ── CREATE AUCTION ───────────────────────
@app.route('/create_auction', methods=['GET', 'POST'])
def create_auction():
    if 'user_id' not in session:
        return redirect('/login')

    if request.method == 'POST':
        title       = request.form.get('title')
        description = request.form.get('description')
        price       = float(request.form.get('price', 0))
        end_time    = request.form.get('end_time')
        category    = request.form.get('category', 'Other')
        buy_now_raw   = request.form.get('buy_now_price', '').strip()
        buy_now_price = float(buy_now_raw) if buy_now_raw else None
        sold_mode     = request.form.get('sold_mode', 'manual')  # 'auto' or 'manual'

        image_file     = request.files.get('image')
        image_filename = ""
        if image_file and image_file.filename != '':
            image_filename = image_file.filename
            os.makedirs("static/images", exist_ok=True)
            image_file.save(os.path.join('static/images', image_filename))

        conn = get_db()
        cursor = conn.cursor()
        cursor.execute("""
             INSERT INTO auctions
            (title, description, image, category, start_price, current_bid,
             end_time, seller_id, status, buy_now_price, sold_mode)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, 'active', ?, ?)
        """, (title, description, image_filename, category, price, price,
              end_time, session['user_id'], buy_now_price, sold_mode))
        conn.commit()
        auction_id = cursor.lastrowid
        conn.close()

        return redirect('/auction/' + str(auction_id))

    return render_template('create_auction.html')


# ── VIEW AUCTION ─────────────────────────
@app.route('/auction/<int:id>')
def auction(id):
    expire_auctions()

    conn = get_db()
    cursor = conn.cursor()

    cursor.execute("SELECT * FROM auctions WHERE id=?", (id,))
    row = cursor.fetchone()
    conn.close()

    if not row:
        return "Auction not found", 404

    auction_data = row_to_auction(row)
    leading      = get_leading_bid(id)
    bid_history  = get_sorted_bid_history(id)

    return render_template(
        "auction.html",
        auction=auction_data,
        leading=leading,
        bid_history=bid_history
    )


# ── BID ──────────────────────────────────
@app.route('/bid', methods=['POST'])
def bid():
    if 'user_id' not in session:
        return redirect('/login')

    conn = get_db()
    cursor = conn.cursor()

    auction_id = int(request.form['auction_id'])
    bid_amount = float(request.form['bid'])
    user_id    = session['user_id']

    if is_duplicate_bid(user_id, auction_id, bid_amount):
        conn.close()
        return render_template("error.html", message="Duplicate bid")

    valid, error_msg, _ = validate_bid_amount(auction_id, bid_amount)
    if not valid:
        conn.close()
        return render_template("error.html", message=error_msg)

    cursor.execute(
        "INSERT INTO bids (auction_id, user_id, bid_amount) VALUES (?, ?, ?)",
        (auction_id, user_id, bid_amount)
    )
    cursor.execute(
        "UPDATE auctions SET current_bid=? WHERE id=?",
        (bid_amount, auction_id)
    ) 
     # ── BUY NOW AUTO-SOLD CHECK ──────────────────────────
    cursor.execute(
        "SELECT buy_now_price, sold_mode FROM auctions WHERE id=?",
        (auction_id,)
    )
    row = cursor.fetchone()
    if row:
        buy_now_price = row[0]
        sold_mode     = row[1]
        if buy_now_price and sold_mode == 'auto' and bid_amount >= buy_now_price:
            cursor.execute(
                "UPDATE auctions SET status='sold', sold_to=? WHERE id=?",
                (user_id, auction_id)
            )
    conn.commit()
    conn.close()

    clear_bid_cache(user_id, auction_id)

    push_bid_to_feed(auction_id, {
        "user_id":     user_id,
        "bidder_name": session.get('user_name'),
        "bid_amount":  bid_amount,
    })

    return redirect('/auction/' + str(auction_id))


# ── BUY PAGE ─────────────────────────────
@app.route('/buy')
def buy_page():
    selected_cat = request.args.get('cat', 'All')

    conn = get_db()
    cursor = conn.cursor()

    if selected_cat and selected_cat != "All":
        cursor.execute("""
            SELECT * FROM auctions
            WHERE status = 'active'
            AND LOWER(category) LIKE ?
            ORDER BY id DESC
        """, (selected_cat.lower() + '%',))
    else:
        cursor.execute("SELECT * FROM auctions WHERE status = 'active' ORDER BY id DESC")

    auctions = [row_to_auction(row) for row in cursor.fetchall()]
    conn.close()

    return render_template('buy.html', auctions=auctions, current_category=selected_cat)
# ── MARK AS SOLD ─────────────────────────
@app.route('/mark_sold/<int:auction_id>/<int:winner_id>')
def mark_sold(auction_id, winner_id):
    if 'user_id' not in session:
        return redirect('/login')
 
    conn = get_db()
    cursor = conn.cursor()
 
    # Only the seller can mark as sold
    cursor.execute(
        "SELECT seller_id FROM auctions WHERE id=?", (auction_id,)
    )
    row = cursor.fetchone()
    if not row or row[0] != session['user_id']:
        conn.close()
        return "Unauthorized", 403
 
    cursor.execute(
        "UPDATE auctions SET status='sold', sold_to=? WHERE id=?",
        (winner_id, auction_id)
    )
    conn.commit()
    conn.close()
    return redirect('/auction/' + str(auction_id))


# ── WISHLIST — ADD ────────────────────────
@app.route('/wishlist/<int:auction_id>')
def add_to_wishlist(auction_id):
    if 'user_id' not in session:
        return redirect('/login')

    conn = get_db()
    cursor = conn.cursor()

    cursor.execute(
        "SELECT id FROM wishlist WHERE user_id=? AND auction_id=?",
        (session['user_id'], auction_id)
    )
    if not cursor.fetchone():
        cursor.execute(
            "INSERT INTO wishlist (user_id, auction_id) VALUES (?, ?)",
            (session['user_id'], auction_id)
        )
        conn.commit()

    conn.close()
    return redirect(request.referrer or '/')


# ── WISHLIST — REMOVE ─────────────────────
@app.route('/remove_wishlist/<int:auction_id>')
def remove_from_wishlist(auction_id):
    if 'user_id' not in session:
        return redirect('/login')

    conn = get_db()
    cursor = conn.cursor()

    cursor.execute(
        "DELETE FROM wishlist WHERE user_id=? AND auction_id=?",
        (session['user_id'], auction_id)
    )
    conn.commit()
    conn.close()
    return redirect(request.referrer or '/my_wishlist')


# ── WISHLIST — VIEW ───────────────────────
@app.route('/my_wishlist')
def my_wishlist():
    if 'user_id' not in session:
        return redirect('/login')

    conn = get_db()
    cursor = conn.cursor()

    cursor.execute("""
        SELECT auctions.*
        FROM wishlist
        JOIN auctions ON wishlist.auction_id = auctions.id
        WHERE wishlist.user_id = ?
    """, (session['user_id'],))

    wishlist_items = cursor.fetchall()
    conn.close()

    return render_template('wishlist.html', wishlist_items=wishlist_items)


# ── SUBMIT REVIEW ─────────────────────────
@app.route('/submit_review', methods=['POST'])
def submit_review():
    if 'user_id' not in session:
        return redirect('/login')

    stars   = request.form.get('stars')
    message = request.form.get('message')

    conn = get_db()
    cursor = conn.cursor()
    cursor.execute(
        "INSERT INTO reviews (user_id, stars, comment) VALUES (?, ?, ?)",
        (session['user_id'], stars, message)
    )
    conn.commit()
    conn.close()

    return redirect('/')


# ── NEWSLETTER ────────────────────────────
@app.route('/subscribe', methods=['POST'])
def subscribe():
    email = request.form.get('email')
    if not email:
        return redirect('/')

    conn = get_db()
    cursor = conn.cursor()
    try:
        cursor.execute("INSERT OR IGNORE INTO newsletter (email) VALUES (?)", (email,))
        conn.commit()
    except Exception as e:
        print(f"Subscription error: {e}")
    finally:
        conn.close()

    return redirect('/')


# ── DELETE BID ────────────────────────────
@app.route('/delete_bid/<int:bid_id>')
def delete_bid(bid_id):
    if 'user_id' not in session:
        return redirect('/login')

    conn = get_db()
    cursor = conn.cursor()
    cursor.execute(
        "DELETE FROM bids WHERE id=? AND user_id=?",
        (bid_id, session['user_id'])
    )
    conn.commit()
    conn.close()
    return redirect('/dashboard')


# ── DELETE AUCTION ────────────────────────
@app.route('/delete_auction/<int:id>')
def delete_auction(id):
    if 'user_id' not in session:
        return redirect('/login')

    conn = get_db()
    cursor = conn.cursor()
    cursor.execute(
        "DELETE FROM auctions WHERE id=? AND seller_id=?",
        (id, session['user_id'])
    )
    conn.commit()
    conn.close()
    return redirect('/')


# ── LOGOUT ─────────────────────────────
@app.route('/logout')
def logout():
    session.clear()
    return redirect('/')


# ── RUN ───────────────────────────────
if __name__ == "__main__":
    app.run(debug=True)