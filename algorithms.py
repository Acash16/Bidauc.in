"""
algorithms.py
─────────────────────────────────────────────────────────────
All 7 auction algorithms. Import and call from app.py.
Your existing code stays unchanged — these just plug in.
─────────────────────────────────────────────────────────────
"""

import heapq
import threading
import sqlite3
from collections import deque
from datetime import datetime


# ─────────────────────────────────────────────────────────────
# DB HELPER  (same pattern as your auction_scheduler.py)
# ─────────────────────────────────────────────────────────────
def get_conn():
    conn = sqlite3.connect("auction.db", check_same_thread=False)
    conn.row_factory = sqlite3.Row
    return conn


# ══════════════════════════════════════════════════════════════
# ALGORITHM 1 — MIN-HEAP
# Use: Dashboard → show the cheapest active auctions where
#      the current user has placed bids (so they know where
#      they can still win without spending the most).
# ══════════════════════════════════════════════════════════════
def get_cheapest_biddable(user_id: int, top_n: int = 5) -> list[dict]:
    """
    Returns up to `top_n` active auctions where the user has bid,
    sorted cheapest-first using a Min-Heap.

    Returns list of dicts: {id, title, current_bid, end_time}
    """
    conn = get_conn()
    cursor = conn.cursor()

    # Get all active auctions this user has bid on
    cursor.execute("""
        SELECT a.id, a.title, a.current_bid, a.end_time
        FROM auctions a
        JOIN bids b ON b.auction_id = a.id
        WHERE b.user_id = ?
          AND (a.end_time IS NULL OR a.end_time > ?)
        GROUP BY a.id
    """, (user_id, datetime.now().isoformat()))

    rows = cursor.fetchall()
    conn.close()

    # Build Min-Heap: (current_bid, id, title, end_time)
    heap = []
    for row in rows:
        heapq.heappush(heap, (row["current_bid"], row["id"], row["title"], row["end_time"]))

    # Pop cheapest top_n
    result = []
    for _ in range(min(top_n, len(heap))):
        bid, aid, title, end_time = heapq.heappop(heap)
        result.append({"id": aid, "title": title, "current_bid": bid, "end_time": end_time})

    return result


# ══════════════════════════════════════════════════════════════
# ALGORITHM 2 — MAX-HEAP
# Use: Auction detail page → find the leading (highest) bidder
#      instantly from all bids on that auction.
# ══════════════════════════════════════════════════════════════
def get_leading_bid(auction_id: int) -> dict | None:
    """
    Returns the leading bid dict: {user_id, bid_amount, bidder_name}
    Uses a Max-Heap (negated amounts in heapq).
    Returns None if no bids exist.
    """
    conn = get_conn()
    cursor = conn.cursor()

    cursor.execute("""
        SELECT b.user_id, b.bid_amount, u.name AS bidder_name
        FROM bids b
        LEFT JOIN users u ON u.id = b.user_id
        WHERE b.auction_id = ?
    """, (auction_id,))

    rows = cursor.fetchall()
    conn.close()

    if not rows:
        return None

    # Max-Heap: negate bid_amount so heapq (min-heap) gives us max
    heap = [(-row["bid_amount"], row["user_id"], row["bidder_name"]) for row in rows]
    heapq.heapify(heap)

    neg_amount, uid, name = heapq.heappop(heap)
    return {
        "user_id":     uid,
        "bid_amount":  -neg_amount,
        "bidder_name": name or "Anonymous",
    }


# ══════════════════════════════════════════════════════════════
# ALGORITHM 3 — HASHMAP  (bid deduplication)
# Use: bid() route → prevent a user from placing the exact same
#      bid amount twice on the same auction (double-click guard).
# ══════════════════════════════════════════════════════════════

# In-memory HashMap: key = (user_id, auction_id, amount) → True
_bid_seen: dict[tuple, bool] = {}
_bid_seen_lock = threading.Lock()

def is_duplicate_bid(user_id: int, auction_id: int, amount: float) -> bool:
    """
    Returns True if this exact (user, auction, amount) combo was
    already submitted (duplicate). Registers it otherwise.
    """
    key = (user_id, auction_id, round(amount, 2))
    with _bid_seen_lock:
        if key in _bid_seen:
            return True
        _bid_seen[key] = True
        return False


def clear_bid_cache(user_id: int, auction_id: int):
    """
    Call this after a successful bid so the user CAN bid again
    (with a different/higher amount). Clears only their entry.
    """
    with _bid_seen_lock:
        keys_to_del = [k for k in _bid_seen if k[0] == user_id and k[1] == auction_id]
        for k in keys_to_del:
            del _bid_seen[k]


# ══════════════════════════════════════════════════════════════
# ALGORITHM 4 — GREEDY  (minimum bid enforcement)
# Use: bid() route → always enforce that new bid > current bid.
#      Greedy rule: accept bid only if it gives the maximum
#      immediate gain (i.e. strictly beats current price).
# ══════════════════════════════════════════════════════════════
def validate_bid_amount(auction_id: int, new_amount: float) -> tuple[bool, str, float]:
    """
    Greedy check: is `new_amount` strictly greater than current_bid?

    Returns:
        (True,  "",        min_required)  → bid is valid
        (False, error_msg, min_required)  → bid rejected
    """
    conn = get_conn()
    cursor = conn.cursor()

    cursor.execute("SELECT current_bid, end_time, title FROM auctions WHERE id=?", (auction_id,))
    row = cursor.fetchone()
    conn.close()

    if not row:
        return False, "Auction not found.", 0.0

    current  = float(row["current_bid"] or 0)
    end_time = row["end_time"]
    min_bid  = round(current + 1.0, 2)   # Greedy: must beat by at least $1

    # Also check auction hasn't expired
    if end_time:
        try:
            end_dt = datetime.fromisoformat(end_time)
            if datetime.now() > end_dt:
                return False, "This auction has already ended.", min_bid
        except ValueError:
            pass

    if new_amount < min_bid:
        return False, f"Minimum bid is ${min_bid:.2f} (current: ${current:.2f}).", min_bid

    return True, "", min_bid


# ══════════════════════════════════════════════════════════════
# ALGORITHM 5 — EVENT LOOP / SCHEDULER
# Use: Background thread started once at app launch.
#      Every 60 seconds it scans for expired auctions and
#      marks them as 'ended', then finds the winner via Max-Heap.
# ══════════════════════════════════════════════════════════════
def _scheduler_loop(interval_seconds: int = 60):
    """Internal loop — runs in a daemon thread."""
    import time
    while True:
        try:
            _close_expired_auctions()
        except Exception as e:
            print(f"[Scheduler] Error: {e}")
        time.sleep(interval_seconds)


def _close_expired_auctions():
    conn = get_conn()
    cursor = conn.cursor()
    now = datetime.now().isoformat()

    # Find active auctions whose end_time has passed
    cursor.execute("""
        SELECT id, title, current_bid FROM auctions
        WHERE end_time <= ?
          AND (status IS NULL OR status NOT IN ('ended','cancelled'))
    """, (now,))

    expired = cursor.fetchall()

    for auction in expired:
        aid   = auction["id"]
        title = auction["title"]

        # Use Max-Heap to find winner
        winner = get_leading_bid(aid)

        cursor.execute(
            "UPDATE auctions SET status='ended' WHERE id=?",
            (aid,)
        )

        if winner:
            print(f"[Scheduler] Auction #{aid} '{title}' ENDED → "
                  f"Winner: {winner['bidder_name']} @ ${winner['bid_amount']:.2f}")
        else:
            print(f"[Scheduler] Auction #{aid} '{title}' ENDED → No bids.")

    if expired:
        conn.commit()

    conn.close()


def start_scheduler(interval_seconds: int = 60):
    """
    Call once in app.py after app is created.
    Starts a background daemon thread — won't block your server.
    """
    t = threading.Thread(
        target=_scheduler_loop,
        args=(interval_seconds,),
        daemon=True,
        name="AuctionScheduler"
    )
    t.start()
    print(f"[Scheduler] Started — checking every {interval_seconds}s.")
    return t


# ══════════════════════════════════════════════════════════════
# ALGORITHM 6 — SORTING  (bid history, frontend UX)
# Use: auction() route → return bids sorted descending by amount
#      so the highest bid always appears first in the template.
# ══════════════════════════════════════════════════════════════
def get_sorted_bid_history(auction_id: int) -> list[dict]:
    """
    Returns all bids for an auction sorted highest→lowest.
    Each dict: {bid_id, user_id, bidder_name, bid_amount, placed_at}
    """
    conn = get_conn()
    cursor = conn.cursor()

    cursor.execute("""
        SELECT b.id AS bid_id, b.user_id, b.bid_amount,
               u.name AS bidder_name
        FROM bids b
        LEFT JOIN users u ON u.id = b.user_id
        WHERE b.auction_id = ?
    """, (auction_id,))

    rows = cursor.fetchall()
    conn.close()

    bids = [dict(r) for r in rows]

    # Sorting Algorithm: sort descending by bid_amount
    bids.sort(key=lambda b: b["bid_amount"], reverse=True)

    return bids


# ══════════════════════════════════════════════════════════════
# ALGORITHM 7 — QUEUE (FIFO)  — Live Bid Feed
# Use: dashboard() and auction() → push new bids into a per-
#      auction FIFO queue; frontend polls /api/live-feed/<id>
#      to get the latest bids in arrival order.
# ══════════════════════════════════════════════════════════════

# In-memory store: auction_id → deque of bid dicts (max 50)
_live_feed: dict[int, deque] = {}
_live_feed_lock = threading.Lock()

def push_bid_to_feed(auction_id: int, bid_dict: dict):
    """
    Enqueue a new bid into the live feed for this auction.
    Keeps only the last 50 bids (FIFO, oldest dropped).
    Call this immediately after inserting a bid into DB.
    """
    with _live_feed_lock:
        if auction_id not in _live_feed:
            _live_feed[auction_id] = deque(maxlen=50)
        _live_feed[auction_id].append(bid_dict)


def get_live_feed(auction_id: int, since_index: int = 0) -> list[dict]:
    """
    Returns bids from position `since_index` onward (FIFO order).
    Frontend sends the last index it saw; gets only new ones back.
    """
    with _live_feed_lock:
        feed = list(_live_feed.get(auction_id, []))
    return feed[since_index:]