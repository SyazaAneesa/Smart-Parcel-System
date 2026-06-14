import sqlite3
import os

DATABASE = "database.db"

# Remove old database if exists
if os.path.exists(DATABASE):
    os.remove(DATABASE)

conn = sqlite3.connect(DATABASE)
c = conn.cursor()

# Students table (username as PRIMARY KEY)
c.execute('''
CREATE TABLE students (
    username TEXT PRIMARY KEY,
    student_id TEXT UNIQUE,
    full_name TEXT,
    email TEXT,
    phone TEXT,
    password TEXT,
    profile_pic_path TEXT
)
''')

# Parcels table
c.execute('''
CREATE TABLE parcels (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    student_username TEXT,
    tracking_number TEXT,
    courier TEXT,
    arrival_date TEXT,
    quantity INTEGER,
    payment_status TEXT DEFAULT 'Unpaid',
    collection_status TEXT DEFAULT 'Not Collected',
    qr_code TEXT,
    FOREIGN KEY(student_username) REFERENCES students(username)
)
''')

# Staff table
c.execute('''
CREATE TABLE staff (
    staff_id TEXT PRIMARY KEY,
    username TEXT UNIQUE,
    password TEXT
)
''')

# Default staff account
c.execute("INSERT INTO staff (staff_id, username, password) VALUES (?, ?, ?)",
          ("S001", "admin", "admin123"))

#chatbot table
c.execute('''
    CREATE TABLE IF NOT EXISTS chat_messages (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        student_username TEXT,
        question TEXT NOT NULL,
        answer TEXT,
        status TEXT DEFAULT 'Pending',
        created_at TEXT DEFAULT CURRENT_TIMESTAMP,
        answered_at TEXT
    )
''')

conn.commit()
conn.close()
print("Database created successfully with default staff user.")