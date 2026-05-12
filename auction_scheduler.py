import os
import logging
import datetime
from flask import Blueprint, request, jsonify

import sqlite3

# DB connection
def get_conn():
    conn = sqlite3.connect("auction.db")
    conn.row_factory = sqlite3.Row
    return conn

log = logging.getLogger(__name__)
auctions_bp = Blueprint("auctions", __name__)

BUYER_PREMIUM_DEFAULTS = {
    "general": 0.0,
    "real_estate": 0.0,
    "art": float(os.getenv("BUYER_PREMIUM_PERCENT", 15)),
}

# ---------------- CREATE AUCTION ----------------
@auctions_bp.route("/", methods=["POST"])
def create_auction():

    user_id = 1  # temporary user
    data = request.get_json(silent=True) or {}

    required = ["title", "category", "auction_type", "start_time", "end_time"]
    for field in required:
        if not data.get(field):
            return jsonify(error=f"{field} is required"), 400

    category = data["category"]
    auction_type = data["auction_type"]

    if category not in ("general", "real_estate", "art"):
        return jsonify(error="Invalid category"), 400

    if auction_type not in ("first_price", "vickrey"):
        return jsonify(error="Invalid auction type"), 400

    try:
        start = datetime.datetime.fromisoformat(data["start_time"])
        end = datetime.datetime.fromisoformat(data["end_time"])
    except:
        return jsonify(error="Invalid date format"), 400

    if end <= start:
        return jsonify(error="End time must be after start time"), 400

    conn = get_conn()
    cursor = conn.cursor()

    try:
        reserve = float(data.get("reserve_price", 0))
        premium = BUYER_PREMIUM_DEFAULTS.get(category, 0.0)
        status = "draft" if start > datetime.datetime.now() else "open"

        cursor.execute("""
            INSERT INTO auctions
            (seller_id, title, description, category, auction_type,
             reserve_price, buyer_premium_pct, start_time, end_time,
             status, image_url, doc_url)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            user_id,
            data["title"],
            data.get("description", ""),
            category,
            auction_type,
            reserve,
            premium,
            start,
            end,
            status,
            data.get("image_url"),
            data.get("doc_url"),
        ))

        conn.commit()

        return jsonify(message="Auction created"), 201

    except Exception as e:
        conn.rollback()
        return jsonify(error=str(e)), 500

    finally:
        conn.close()


# ---------------- LIST AUCTIONS ----------------
@auctions_bp.route("/", methods=["GET"])
def list_auctions():

    conn = get_conn()
    cursor = conn.cursor()

    cursor.execute("""
        SELECT id, title, category, auction_type,
               reserve_price, start_time, end_time,
               status, image_url
        FROM auctions
        WHERE status IN ('open','draft')
        ORDER BY end_time ASC
    """)

    rows = cursor.fetchall()

    auctions = []
    for r in rows:
        auctions.append(dict(r))

    conn.close()
    return jsonify(auctions=auctions)


# ---------------- AUCTION DETAIL ----------------
@auctions_bp.route("/<int:auction_id>", methods=["GET"])
def auction_detail(auction_id):

    conn = get_conn()
    cursor = conn.cursor()

    cursor.execute("SELECT * FROM auctions WHERE id=?", (auction_id,))
    row = cursor.fetchone()

    if not row:
        return jsonify(error="Not found"), 404

    data = dict(row)

    cursor.execute("SELECT COUNT(*) FROM bids WHERE auction_id=?", (auction_id,))
    data["bid_count"] = cursor.fetchone()[0]

    conn.close()
    return jsonify(auction=data)


# ---------------- CANCEL AUCTION ----------------
@auctions_bp.route("/<int:auction_id>/cancel", methods=["POST"])
def cancel_auction(auction_id):

    user_id = 1  # temporary

    conn = get_conn()
    cursor = conn.cursor()

    cursor.execute("SELECT seller_id, status FROM auctions WHERE id=?", (auction_id,))
    auction = cursor.fetchone()

    if not auction:
        return jsonify(error="Not found"), 404

    if auction["seller_id"] != user_id:
        return jsonify(error="Forbidden"), 403

    if auction["status"] in ("settled", "cancelled"):
        return jsonify(error="Already closed"), 400

    cursor.execute(
        "UPDATE auctions SET status='cancelled' WHERE id=?",
        (auction_id,)
    )

    conn.commit()
    conn.close()

    return jsonify(message="Auction cancelled")