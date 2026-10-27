import os
import sqlite3


DATA_DIR = os.path.join(os.path.dirname(__file__), "data")
os.makedirs(DATA_DIR, exist_ok=True)

# Point the database connection to data/library.db
DB_PATH = os.path.join(DATA_DIR, "library.db")

def get_connection():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def init_db():
    """Creates the database schema if tables do not exist."""
    conn = get_connection()
    cursor = conn.cursor()

    # 1. Articles Catalog Table
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS articles (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            title TEXT NOT NULL,
            gerateart TEXT,
            hersteller TEXT
        )
    """)

    # 2. Physical Item Units Table
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS items (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            article_id INTEGER NOT NULL,
            serial_number TEXT UNIQUE NOT NULL,
            ort TEXT,
            status TEXT DEFAULT 'available',
            FOREIGN KEY (article_id) REFERENCES articles (id)
        )
    """)

    # 3. Bookings Table
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS bookings (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            item_id INTEGER NOT NULL,
            user_name TEXT NOT NULL,
            user_email TEXT NOT NULL,
            start_time TEXT NOT NULL,
            end_time TEXT NOT NULL,
            status TEXT DEFAULT 'checked_out',
            reminder_sent INTEGER DEFAULT 0,
            last_overdue_email TEXT,
            FOREIGN KEY (item_id) REFERENCES items (id)
        )
    """)

    conn.commit()
    conn.close()

def get_available_items_for_article(article_id: int, start_time: str, end_time: str):
    """
    Returns ALL physical items for an article that are available 
    for the selected time window.
    """
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("""
        SELECT i.id, i.serial_number, i.ort 
        FROM items i
        WHERE i.article_id = ?
          AND i.id NOT IN (
              SELECT item_id FROM bookings
              WHERE status = 'checked_out'
                AND datetime(start_time) < datetime(?)
                AND datetime(end_time) > datetime(?)
          )
    """, (article_id, end_time, start_time))
    items = cursor.fetchall()
    conn.close()
    return items


def create_multi_booking(item_ids: list, user_name: str, user_email: str, start_time: str, end_time: str):
    """Creates individual booking records for a list of item IDs in one transaction."""
    conn = get_connection()
    cursor = conn.cursor()
    for item_id in item_ids:
        cursor.execute("""
            INSERT INTO bookings (item_id, user_name, user_email, start_time, end_time, status)
            VALUES (?, ?, ?, ?, ?, 'checked_out')
        """, (item_id, user_name, user_email, start_time, end_time))
    conn.commit()
    conn.close()

def get_all_articles():
    """Fetch all articles along with their unit counts and manufacturer details."""
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("""
        SELECT 
            a.id, 
            a.title, 
            a.gerateart, 
            a.hersteller, 
            COUNT(i.id) AS total_units
        FROM articles a
        LEFT JOIN items i ON a.id = i.article_id
        GROUP BY a.id
        ORDER BY a.title ASC
    """)
    articles = cursor.fetchall()
    conn.close()
    return articles

def get_available_item_for_article(article_id: int, start_time: str, end_time: str):
    """Find a physical unit (item) that is not booked during the requested time slot."""
    conn = get_connection()
    cursor = conn.cursor()
    
    query = """
        SELECT i.id, i.serial_number, i.ort
        FROM items i
        WHERE i.article_id = ?
          AND i.status = 'available'
          AND i.id NOT IN (
              SELECT item_id 
              FROM bookings 
              WHERE status = 'checked_out'
                AND (
                    (start_time < ? AND end_time > ?) OR
                    (start_time < ? AND end_time > ?) OR
                    (start_time >= ? AND end_time <= ?)
                )
          )
        LIMIT 1
    """
    cursor.execute(query, (article_id, end_time, start_time, start_time, start_time, start_time, end_time))
    item = cursor.fetchone()
    conn.close()
    return item

def check_available_items(article_id: int, start_time: str, end_time: str):
    """Finds physical items for an article that have no overlapping active bookings."""
    conn = get_connection()
    cursor = conn.cursor()

    query = """
        SELECT * FROM items 
        WHERE article_id = ? 
          AND status = 'available'
          AND id NOT IN (
              SELECT item_id FROM bookings 
              WHERE status = 'checked_out'
                AND start_time < ? 
                AND end_time > ?
          )
    """
    cursor.execute(query, (article_id, end_time, start_time))
    available_items = cursor.fetchall()
    conn.close()
    return available_items

def get_active_bookings():
    """Fetch all currently checked-out bookings for active rentals management."""
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("""
        SELECT 
            b.id AS booking_id,
            a.title AS item_title,
            a.gerateart,
            i.serial_number,
            i.ort,
            b.user_name,
            b.user_email,
            b.start_time,
            b.end_time,
            b.reminder_sent,
            b.last_overdue_email
        FROM bookings b
        JOIN items i ON b.item_id = i.id
        JOIN articles a ON i.article_id = a.id
        WHERE b.status = 'checked_out'
        ORDER BY b.end_time ASC
    """)
    active_bookings = cursor.fetchall()
    conn.close()
    return active_bookings

def create_booking(item_id: int, user_name: str, user_email: str, start_time: str, end_time: str):
    """Record a new checkout booking."""
    conn = get_connection()
    cursor = conn.cursor()
    
    cursor.execute("""
        INSERT INTO bookings (item_id, user_name, user_email, start_time, end_time, status, reminder_sent)
        VALUES (?, ?, ?, ?, ?, 'checked_out', 0)
    """, (item_id, user_name, user_email, start_time, end_time))
    
    conn.commit()
    conn.close()

def get_due_bookings():
    """
    Finds active bookings where end_time is due within the next 3 hours 
    (or overdue) and a reminder hasn't been sent yet.
    """
    conn = get_connection()
    cursor = conn.cursor()
    
    # Matches bookings where end_time is <= 3 hours from local time
    query = """
        SELECT 
            b.id AS booking_id,
            a.title AS item_title,
            i.serial_number,
            b.user_name,
            b.user_email,
            b.end_time
        FROM bookings b
        JOIN items i ON b.item_id = i.id
        JOIN articles a ON i.article_id = a.id
        WHERE b.status = 'checked_out'
          AND b.reminder_sent = 0
          AND datetime(b.end_time) <= datetime('now', 'localtime', '+3 hours')
    """
    cursor.execute(query)
    due_bookings = cursor.fetchall()
    conn.close()
    return due_bookings

def get_overdue_bookings():
    """
    Finds active bookings where end_time is past due AND
    no overdue email was sent in the last 12 hours.
    """
    conn = get_connection()
    cursor = conn.cursor()
    
    query = """
        SELECT 
            b.id AS booking_id,
            a.title AS item_title,
            i.serial_number,
            b.user_name,
            b.user_email,
            b.end_time
        FROM bookings b
        JOIN items i ON b.item_id = i.id
        JOIN articles a ON i.article_id = a.id
        WHERE b.status = 'checked_out'
          AND datetime(b.end_time) < datetime('now', 'localtime')
          AND (
              b.last_overdue_email IS NULL 
              OR datetime(b.last_overdue_email) <= datetime('now', 'localtime', '-12 hours')
          )
        ORDER BY b.end_time ASC
    """
    cursor.execute(query)
    overdue_bookings = cursor.fetchall()
    conn.close()
    return overdue_bookings

def mark_overdue_email_sent(booking_id: int):
    """Updates last_overdue_email to current timestamp."""
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("""
        UPDATE bookings 
        SET last_overdue_email = datetime('now', 'localtime') 
        WHERE id = ?
    """, (booking_id,))
    conn.commit()
    conn.close()

def mark_reminder_sent(booking_id: int):
    """Mark booking as reminded so duplicate emails aren't sent."""
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("UPDATE bookings SET reminder_sent = 1 WHERE id = ?", (booking_id,))
    conn.commit()
    conn.close()

def return_booking(booking_id: int):
    """Mark a booking status as 'returned' so the item becomes available again."""
    conn = get_connection()
    cursor = conn.cursor()
    
    cursor.execute("""
        UPDATE bookings 
        SET status = 'returned' 
        WHERE id = ?
    """, (booking_id,))
    
    conn.commit()
    conn.close()

def get_returned_bookings():
    """Fetch all completed/returned bookings for the history log."""
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("""
        SELECT 
            b.id AS booking_id,
            a.title AS item_title,
            i.serial_number,
            b.user_name,
            b.user_email,
            b.start_time,
            b.end_time,
            b.status
        FROM bookings b
        JOIN items i ON b.item_id = i.id
        JOIN articles a ON i.article_id = a.id
        WHERE b.status = 'returned'
        ORDER BY b.end_time DESC
    """)
    returned_bookings = cursor.fetchall()
    conn.close()
    return returned_bookings

if __name__ == "__main__":
    init_db()
    print("Database library.db initialized successfully!")