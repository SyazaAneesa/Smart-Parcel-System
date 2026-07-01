import os
import sqlite3
from flask import Flask, jsonify, render_template, request, redirect, url_for, session, flash
from werkzeug.utils import secure_filename
from werkzeug.security import generate_password_hash, check_password_hash
import qrcode
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from email.mime.image import MIMEImage
import random
from datetime import date, datetime, timedelta
import threading

app = Flask(__name__)
app.secret_key = os.getenv("SECRET_KEY", "secretkey")

UPLOAD_FOLDER = 'static/profile_pics'
QR_FOLDER = 'static/qr_codes'

for folder in [UPLOAD_FOLDER, QR_FOLDER]:
    os.makedirs(folder, exist_ok=True)

ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg', 'gif'}
DATABASE = 'database.db'

SENDER_EMAIL = os.getenv("SENDER_EMAIL")
SENDER_PASSWORD = os.getenv("SENDER_PASSWORD")


def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS


def get_db_connection():
    conn = sqlite3.connect(DATABASE, timeout=30)
    conn.row_factory = sqlite3.Row
    return conn


def send_qr_email(student_email, student_username, tracking_number, qr_path):
    if not SENDER_EMAIL or not SENDER_PASSWORD:
        print("Email not sent: SENDER_EMAIL or SENDER_PASSWORD missing")
        return

    subject = "Parcel Collection QR Code"

    body = f"""
Hello {student_username},

Your parcel payment is successful.

Tracking Number: {tracking_number}

Please show this QR code to staff when collecting your parcel.

Thank you.
"""

    msg = MIMEMultipart()
    msg["From"] = SENDER_EMAIL
    msg["To"] = student_email
    msg["Subject"] = subject
    msg.attach(MIMEText(body, "plain"))

    if qr_path and os.path.exists(qr_path):
        with open(qr_path, "rb") as file:
            qr_image = MIMEImage(file.read())
            qr_image.add_header("Content-Disposition", "attachment", filename="parcel_qr.png")
            msg.attach(qr_image)

    try:
        with smtplib.SMTP("smtp.gmail.com", 587, timeout=20) as server:
            server.starttls()
            server.login(SENDER_EMAIL, SENDER_PASSWORD)
            server.send_message(msg)
    except Exception as e:
        print("Failed to send QR email:", e)


def send_reset_code_email(student_email, student_username, reset_code):
    if not SENDER_EMAIL or not SENDER_PASSWORD:
        print("Email not sent: SENDER_EMAIL or SENDER_PASSWORD missing")
        return

    subject = "Password Reset Verification Code"

    body = f"""
Hello {student_username},

Your password reset verification code is: {reset_code}

This code will expire in 10 minutes.

Thank you.
"""

    msg = MIMEMultipart()
    msg["From"] = SENDER_EMAIL
    msg["To"] = student_email
    msg["Subject"] = subject
    msg.attach(MIMEText(body, "plain"))

    try:
        with smtplib.SMTP("smtp.gmail.com", 587, timeout=20) as server:
            server.starttls()
            server.login(SENDER_EMAIL, SENDER_PASSWORD)
            server.send_message(msg)
    except Exception as e:
        print("Failed to send reset email:", e)


def send_parcel_email(student_email, student_username, tracking_number):
    def job():
        if not SENDER_EMAIL or not SENDER_PASSWORD:
            print("Email not sent: SENDER_EMAIL or SENDER_PASSWORD missing")
            return

        subject = "Parcel Arrival Notification"

        body = f"""
Hello {student_username},

Your parcel has arrived.

Tracking Number: {tracking_number}

Please login to the Smart Parcel Collection System and make payment to generate your QR code.

Thank you.
"""

        msg = MIMEMultipart()
        msg["From"] = SENDER_EMAIL
        msg["To"] = student_email
        msg["Subject"] = subject
        msg.attach(MIMEText(body, "plain"))

        try:
            with smtplib.SMTP("smtp.gmail.com", 587, timeout=20) as server:
                server.starttls()
                server.login(SENDER_EMAIL, SENDER_PASSWORD)
                server.send_message(msg)
        except Exception as e:
            print("Failed to send parcel email:", e)

    threading.Thread(target=job, daemon=True).start()


def init_db():
    conn = get_db_connection()
    c = conn.cursor()

    c.execute('''
        CREATE TABLE IF NOT EXISTS students (
            username TEXT PRIMARY KEY,
            student_id TEXT UNIQUE,
            full_name TEXT,
            email TEXT,
            phone TEXT,
            password TEXT,
            profile_pic_path TEXT
        )
    ''')

    c.execute('''
        CREATE TABLE IF NOT EXISTS parcels (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            student_username TEXT,
            tracking_number TEXT,
            courier TEXT,
            arrival_date TEXT,
            quantity INTEGER,
            payment_status TEXT DEFAULT 'Unpaid',
            collection_status TEXT DEFAULT 'Not Collected',
            qr_code TEXT,
            collection_date TEXT
        )
    ''')

    c.execute('''
        CREATE TABLE IF NOT EXISTS staff (
            staff_id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT UNIQUE,
            password TEXT
        )
    ''')

    # Reset admin account
    c.execute("DELETE FROM staff WHERE username = ?", ("admin",))

    c.execute("""
              INSERT INTO STAFF (username, password)
              VALUES (?, ?)
    """, ("admin", generate_password_hash("admin123")))

    c.execute('''
        CREATE TABLE IF NOT EXISTS notices (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            title TEXT NOT NULL,
            message TEXT NOT NULL,
            type TEXT NOT NULL,
            recipient TEXT DEFAULT 'all',
            is_read INTEGER DEFAULT 0,
            created_at TEXT DEFAULT CURRENT_TIMESTAMP
        )
    ''')

    c.execute('''
        CREATE TABLE IF NOT EXISTS chat_messages (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            sender_username TEXT,
            receiver_username TEXT,
            message TEXT,
            answer TEXT,
            status TEXT DEFAULT 'Pending',
            is_read INTEGER DEFAULT 0,
            created_at TEXT DEFAULT CURRENT_TIMESTAMP,
            answered_at TEXT
        )
    ''')

    try:
        c.execute("ALTER TABLE parcels ADD COLUMN collection_date TEXT")
    except sqlite3.OperationalError:
        pass

    try:
        c.execute("ALTER TABLE parcels ADD COLUMN qr_code TEXT")
    except sqlite3.OperationalError:
        pass

    try:
        c.execute("ALTER TABLE chat_messages ADD COLUMN answer TEXT")
    except sqlite3.OperationalError:
        pass

    try:
        c.execute("ALTER TABLE chat_messages ADD COLUMN status TEXT DEFAULT 'Pending'")
    except sqlite3.OperationalError:
        pass

    try:
        c.execute("ALTER TABLE chat_messages ADD COLUMN answered_at TEXT")
    except sqlite3.OperationalError:
        pass

    c.execute("""
        INSERT OR IGNORE INTO staff (username, password)
        VALUES (?, ?)
    """, ("admin", generate_password_hash("admin123")))

    conn.commit()
    conn.close()


@app.route('/')
def home():
    return redirect(url_for('register'))


@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        username = request.form['username']
        student_id = request.form['student_id']
        full_name = request.form['fullname']
        email = request.form['email']
        phone = request.form['phone']
        password = request.form['password']

        conn = get_db_connection()

        try:
            conn.execute("""
                INSERT INTO students
                (username, student_id, full_name, email, phone, password)
                VALUES (?, ?, ?, ?, ?, ?)
            """, (username, student_id, full_name, email, phone, password))

            conn.commit()
            flash("Student registered! Please login.")
            return redirect(url_for('login'))

        except sqlite3.IntegrityError:
            flash("Username or ID already exists!")

        finally:
            conn.close()

    return render_template('register.html')


@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']

        conn = get_db_connection()
        student = conn.execute("""
            SELECT * FROM students
            WHERE username=? AND password=?
        """, (username, password)).fetchone()
        conn.close()

        if student:
            session['username'] = username
            return redirect(url_for('dashboard', username=username))

        flash("Invalid credentials!")

    return render_template('login.html')


@app.route('/dashboard/<username>')
def dashboard(username):
    conn = get_db_connection()
    cursor = conn.cursor()

    cursor.execute("""
        UPDATE parcels
        SET collection_status = 'Collected'
        WHERE collection_status = 'Pending Confirmation'
        AND DATETIME(collection_date, '+3 days') <= DATETIME('now')
    """)
    conn.commit()

    cursor.execute("SELECT * FROM students WHERE username = ?", (username,))
    user = cursor.fetchone()

    cursor.execute("""
        SELECT * FROM parcels
        WHERE student_username = ?
        ORDER BY id DESC
    """, (username,))
    parcels = cursor.fetchall()

    conn.close()

    return render_template(
        'dashboard.html',
        username=username,
        parcels=parcels,
        student_id=user['student_id'] if user and 'student_id' in user.keys() else 'Not set',
        student_email=user['email'] if user and 'email' in user.keys() else 'Not set',
        profile_pic=user['profile_pic_path'] if user and 'profile_pic_path' in user.keys() else None
    )


@app.route('/upload_profile/<username>', methods=['POST'])
def upload_profile(username):
    if 'profile_pic' not in request.files:
        return redirect(url_for('dashboard', username=username))

    file = request.files['profile_pic']

    if file.filename == '':
        return redirect(url_for('dashboard', username=username))

    if file and allowed_file(file.filename):
        filename = secure_filename(f"{username}_{file.filename}")
        file.save(os.path.join(UPLOAD_FOLDER, filename))
        saved_path = "profile_pics/" + filename

        conn = get_db_connection()
        conn.execute("""
            UPDATE students
            SET profile_pic_path=?
            WHERE username=?
        """, (saved_path, username))
        conn.commit()
        conn.close()

    return redirect(url_for('dashboard', username=username))


@app.route('/pay_selected/<username>', methods=['POST'])
def pay_selected(username):
    selected_ids = request.form.getlist('parcel_ids')

    if not selected_ids:
        flash("No parcels selected!")
        return redirect(url_for('dashboard', username=username))

    conn = get_db_connection()
    c = conn.cursor()
    qr_files = []

    for parcel_id in selected_ids:
        parcel = c.execute("SELECT * FROM parcels WHERE id=?", (parcel_id,)).fetchone()

        if not parcel:
            continue

        if parcel['payment_status'] == 'Paid':
            continue

        data = f"Username:{username}, Parcel:{parcel['tracking_number']} | ID:{parcel['id']}"
        qr_filename = f"qr_{parcel['tracking_number']}.png"
        qr_path = os.path.join(QR_FOLDER, qr_filename)

        qr_img = qrcode.make(data)
        qr_img.save(qr_path)

        c.execute("""
            UPDATE parcels
            SET payment_status='Paid',
                qr_code=?,
                collection_status='Not Collected'
            WHERE id=?
        """, (qr_filename, parcel_id))

        student = conn.execute(
            "SELECT email FROM students WHERE username=?",
            (username,)
        ).fetchone()

        if student and student['email']:
            send_qr_email(
                student['email'],
                username,
                parcel['tracking_number'],
                qr_path
            )

        qr_files.append(qr_filename)

    conn.commit()
    conn.close()

    flash("Payment successful! QR code has been sent to your email.")
    return render_template('payment_success.html', qr_codes=qr_files, username=username)


@app.route('/staff/login', methods=['GET', 'POST'])
def staff_login():
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']

        conn = get_db_connection()
        staff = conn.execute(
            "SELECT * FROM staff WHERE username=?",
            (username,)
        ).fetchone()
        conn.close()

        if staff and check_password_hash(staff['password'], password):
            session['staff_username'] = username
            return redirect(url_for('staff_dashboard', username=username))

        flash("Invalid credentials!")

    return render_template('staff_login.html')


@app.route('/staff/dashboard/<username>')
def staff_dashboard(username):
    conn = get_db_connection()

    parcels = conn.execute("""
        SELECT * FROM parcels
        ORDER BY id DESC
    """).fetchall()

    chat_messages = conn.execute("""
        SELECT * FROM chat_messages
        ORDER BY status='Pending' DESC, created_at DESC
    """).fetchall()

    conn.close()

    today = date.today()
    parcel_list = []

    for parcel in parcels:
        parcel = dict(parcel)

        try:
            arrival_date = datetime.strptime(parcel['arrival_date'], "%Y-%m-%d").date()
            days_waiting = (today - arrival_date).days
        except:
            days_waiting = 0

        parcel['days_waiting'] = days_waiting
        parcel['overdue'] = days_waiting > 7 and parcel['collection_status'] != 'Collected'

        parcel_list.append(parcel)

    return render_template(
        'staff_dashboard.html',
        parcels=parcel_list,
        username=username,
        staff_username=username,
        chat_messages=chat_messages
    )


@app.route('/staff/checkin', methods=['GET', 'POST'])
def staff_checkin():
    if request.method == 'POST':
        student_username = request.form.get('student_username') or request.form.get('username')
        tracking_number = request.form.get('tracking_number')
        courier = request.form.get('courier')
        quantity = request.form.get('quantity', 1)

        conn = get_db_connection()

        student = conn.execute(
            "SELECT email FROM students WHERE username=?",
            (student_username,)
        ).fetchone()

        conn.execute("""
            INSERT INTO parcels
            (student_username, tracking_number, courier, arrival_date, quantity, payment_status, collection_status)
            VALUES (?, ?, ?, DATE('now'), ?, 'Unpaid', 'Not Collected')
        """, (student_username, tracking_number, courier, quantity))

        conn.execute("""
            INSERT INTO notices (title, message, type, recipient)
            VALUES (?, ?, ?, ?)
        """, (
            "Parcel Arrived",
            f"Your parcel with tracking number {tracking_number} has arrived. Please make payment to generate QR code.",
            "notification",
            student_username
        ))

        conn.commit()
        conn.close()

        if student and student['email']:
            send_parcel_email(student['email'], student_username, tracking_number)

        flash("Parcel checked in and notification sent!")
        return redirect(url_for('staff_dashboard', username=session['staff_username']))

    return render_template('parcel_checkin.html')


@app.route('/staff/qr_scan', methods=['GET', 'POST'])
def staff_qr_scan():
    parcel_info = None

    if request.method == 'POST':
        qr_code = request.form.get('qr_code')

        if qr_code:
            try:
                parcel_id = qr_code.split("ID:")[1].strip()
            except:
                flash("Invalid QR.")
                return render_template('staff_qr_scan.html', parcel_info=None)

            conn = get_db_connection()

            parcel_info = conn.execute("""
                SELECT * FROM parcels
                WHERE id=?
            """, (parcel_id,)).fetchone()

            if not parcel_info:
                conn.close()
                flash("Parcel not found.")
                return render_template('staff_qr_scan.html', parcel_info=None)

            conn.close()

            flash("QR scanned successfully. Please check parcel information.")

            return render_template('scan_result.html', tracking_number=parcel_info['tracking_number'], parcel_info=parcel_info)

    return render_template('staff_qr_scan.html', parcel_info=parcel_info)


@app.route("/release_parcel/<int:parcel_id>", methods=["POST"])
def release_parcel(parcel_id):
    conn = get_db_connection()

    conn.execute("""
        UPDATE parcels
        SET collection_status='Pending Confirmation',
            collection_date = DATETIME('now')
        WHERE id = ?
    """, (parcel_id,))

    conn.commit()
    conn.close()

    flash("Parcel released. Waiting for student to confirm collection.")
    return redirect(url_for('staff_qr_scan'))


@app.route("/confirm_collection/<int:parcel_id>", methods=["POST"])
def confirm_collection(parcel_id):
    username = session.get('username')

    if not username:
        flash("Please login first.")
        return redirect(url_for('login'))

    conn = get_db_connection()

    conn.execute("""
        UPDATE parcels
        SET collection_status='Collected',
            collection_date = DATETIME('now')
        WHERE id=?
        AND student_username=?
    """, (parcel_id, username))

    conn.commit()
    conn.close()

    flash("Parcel collection confirmed!")
    return redirect(url_for('dashboard', username=username))


@app.route('/chatbot/ask', methods=['POST'])
def chatbot_ask():
    data = request.get_json(silent=True) or {}
    message = (data.get('message') or '').strip()
    username = session.get('username')

    if not message:
        return jsonify({"reply": "Please type your question first."})

    lower_message = message.lower()
    tracking_number = data.get('tracking_number') or ''

    words = [word.strip('.,?!#') for word in message.split()]
    possible_tracking_numbers = [
        word for word in words
        if any(ch.isdigit() for ch in word) and len(word) >= 4
    ]

    if possible_tracking_numbers:
        tracking_number = possible_tracking_numbers[0]

    conn = get_db_connection()

    if tracking_number:
        parcel = conn.execute("""
            SELECT * FROM parcels
            WHERE tracking_number = ?
            AND (? IS NULL OR student_username = ?)
        """, (tracking_number, username, username)).fetchone()
        conn.close()

        if parcel:
            reply = (
                f"Tracking number {parcel['tracking_number']} was found. "
                f"Courier: {parcel['courier']}. Arrival date: {parcel['arrival_date']}. "
                f"Payment status: {parcel['payment_status']}. "
                f"Collection status: {parcel['collection_status']}."
            )

            if parcel['payment_status'] != 'Paid':
                reply += " Please select this parcel in your dashboard and proceed with payment before collection."
            elif parcel['collection_status'] != 'Collected':
                reply += " Your parcel is ready for collection. Please show your QR code to staff."
            else:
                reply += " This parcel has already been collected."

            return jsonify({"reply": reply})

        return jsonify({"reply": "I could not find that tracking number. Please check the number or choose Ask staff below."})

    if any(word in lower_message for word in ['track', 'tracking', 'where', 'status', 'parcel']):
        conn.close()
        return jsonify({"reply": "Please send your tracking number, for example: Track ABC123."})

    if 'payment' in lower_message or 'pay' in lower_message:
        conn.close()
        return jsonify({"reply": "To pay, tick your unpaid parcel in your dashboard, then click Proceed to Payment."})

    if 'qr' in lower_message or 'collect' in lower_message or 'collection' in lower_message:
        conn.close()
        return jsonify({"reply": "After payment, your QR code appears in the dashboard. Show that QR code to staff during collection."})

    conn.close()
    return jsonify({"reply": "I can help you track parcels, check payment status, and explain collection steps."})


@app.route('/chatbot/ask_staff', methods=['POST'])
def chatbot_ask_staff():
    data = request.get_json(silent=True) or {}
    question = (data.get('question') or '').strip()
    username = session.get('username') or 'Guest'

    if not question:
        return jsonify({"reply": "Please type your question before sending it to staff."}), 400

    conn = get_db_connection()

    conn.execute("""
        INSERT INTO chat_messages
        (sender_username, receiver_username, message, status)
        VALUES (?, ?, ?, 'Pending')
    """, (username, 'staff', question))

    conn.commit()
    conn.close()

    return jsonify({"reply": "Your question has been sent to staff."})


@app.route('/chatbot/my_questions')
def chatbot_my_questions():
    username = session.get('username')

    if not username:
        return jsonify({"messages": []})

    conn = get_db_connection()

    messages = conn.execute("""
        SELECT message, answer, status, created_at, answered_at
        FROM chat_messages
        WHERE sender_username=?
        ORDER BY created_at DESC
        LIMIT 10
    """, (username,)).fetchall()

    conn.close()

    return jsonify({"messages": [dict(message) for message in messages]})


@app.route('/staff/chat/<int:message_id>/answer', methods=['POST'])
def staff_answer_chat(message_id):
    if 'staff_username' not in session:
        flash("Please login as staff first.")
        return redirect(url_for('staff_login'))

    answer = request.form.get('answer', '').strip()

    if not answer:
        flash("Answer cannot be empty.")
        return redirect(url_for('staff_dashboard', username=session['staff_username']))

    conn = get_db_connection()

    conn.execute("""
        UPDATE chat_messages
        SET answer=?,
            status='Answered',
            answered_at=CURRENT_TIMESTAMP
        WHERE id=?
    """, (answer, message_id))

    conn.commit()
    conn.close()

    flash("Reply sent to student.")
    return redirect(url_for('staff_dashboard', username=session['staff_username']))


@app.route('/forgot_password', methods=['GET', 'POST'])
def forgot_password():
    if request.method == 'POST':
        email = request.form['email'].strip()

        conn = get_db_connection()

        student = conn.execute(
            "SELECT * FROM students WHERE email=?",
            (email,)
        ).fetchone()

        conn.close()

        if not student:
            flash("Email not found.")
            return redirect('/forgot_password')

        reset_code = str(random.randint(1000, 9999))

        session['reset_email'] = email
        session['reset_code'] = reset_code
        session['reset_code_expiry'] = (datetime.now() + timedelta(minutes=10)).isoformat()

        send_reset_code_email(email, student['username'], reset_code)

        flash("A 4-digit code has been sent to your email.")
        return redirect('/verify_reset_code')

    return render_template('forgot_password.html')


@app.route('/verify_reset_code', methods=['GET', 'POST'])
def verify_reset_code():
    if 'reset_email' not in session:
        return redirect('/forgot_password')

    if request.method == 'POST':
        entered_code = request.form['code'].strip()
        expiry = datetime.fromisoformat(session['reset_code_expiry'])

        if datetime.now() > expiry:
            flash("Code expired. Please request again.")
            return redirect('/forgot_password')

        if entered_code == session['reset_code']:
            session['reset_verified'] = True
            return redirect('/reset_password')

        flash("Invalid code.")

    return render_template('verify_reset_code.html')


@app.route('/reset_password', methods=['GET', 'POST'])
def reset_password():
    if not session.get('reset_verified'):
        return redirect(url_for('forgot_password'))

    if request.method == 'POST':
        new_password = request.form['new_password']
        confirm_password = request.form['confirm_password']

        if new_password != confirm_password:
            flash("Passwords do not match.")
            return redirect(url_for('reset_password'))

        conn = get_db_connection()

        conn.execute("""
            UPDATE students
            SET password=?
            WHERE email=?
        """, (new_password, session['reset_email']))

        conn.commit()
        conn.close()

        session.clear()

        flash("Password reset successful. Please login.")
        return redirect(url_for('login'))

    return render_template('reset_password.html')


@app.route('/notices/<username>')
def notices(username):
    conn = get_db_connection()

    all_notices = conn.execute("""
        SELECT * FROM notices
        WHERE recipient = 'all' OR recipient = ?
        ORDER BY created_at DESC
    """, (username,)).fetchall()

    conn.close()

    return render_template(
        'notices.html',
        username=username,
        notices=all_notices
    )


@app.route('/staff/add_notice', methods=['POST'])
def add_notice():
    title = request.form['title']
    message = request.form['message']
    notice_type = request.form.get('type', 'announcement')
    recipient = request.form.get('recipient', 'all')

    conn = get_db_connection()

    conn.execute("""
        INSERT INTO notices (title, message, type, recipient)
        VALUES (?, ?, ?, ?)
    """, (title, message, notice_type, recipient))

    conn.commit()
    conn.close()

    flash("Notice added successfully!")
    return redirect(url_for('staff_dashboard', username=session['staff_username']))


init_db()

if __name__ == "__main__":
    app.run(debug=True)