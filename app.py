import os
import csv
import io
from datetime import datetime, date, timedelta
from functools import wraps

from flask import (
    Flask, render_template, request, redirect, url_for,
    flash, session, g, make_response, jsonify
)
from werkzeug.security import check_password_hash, generate_password_hash
import database

app = Flask(__name__)
app.secret_key = os.environ.get('SECRET_KEY', 'medcare_smart_hospital_secret_key_2026_xyz')

# Database connection management
def get_db():
    if 'db' not in g:
        g.db = database.get_db()
    return g.db

@app.teardown_appcontext
def close_db(exception):
    db = g.pop('db', None)
    if db is not None:
        db.close()

# Context Processor for Global Template Variables
@app.context_processor
def inject_global_data():
    today_str = date.today().strftime('%Y-%m-%d')
    user_id = session.get('user_id')
    user_notifications = []
    unread_notifs_count = 0

    if user_id:
        db = get_db()
        cursor = db.cursor()
        cursor.execute("""
            SELECT * FROM notifications 
            WHERE user_id = ? 
            ORDER BY created_at DESC LIMIT 6
        """, (user_id,))
        user_notifications = cursor.fetchall()

        cursor.execute("SELECT COUNT(*) as count FROM notifications WHERE user_id = ? AND is_read = 0", (user_id,))
        row = cursor.fetchone()
        if row:
            unread_notifs_count = row['count']

    return {
        'today': today_str,
        'user_notifications': user_notifications,
        'unread_notifs_count': unread_notifs_count
    }

# Authentication & Role Decorators
def login_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'user_id' not in session:
            flash("Please log in to access this page.", "warning")
            return redirect(url_for('login'))
        return f(*args, **kwargs)
    return decorated_function

def role_required(*roles):
    def decorator(f):
        @wraps(f)
        def decorated_function(*args, **kwargs):
            if 'user_id' not in session:
                flash("Please log in to access this page.", "warning")
                return redirect(url_for('login'))
            user_role = session.get('role')
            if user_role not in roles and 'admin' not in roles:
                flash("Unauthorized access: Insufficient permissions for this role.", "danger")
                return redirect(url_for('dashboard'))
            return f(*args, **kwargs)
        return decorated_function
    return decorator

# ----------------- HOME / LANDING PAGE -----------------
@app.route('/')
def index():
    db = get_db()
    cursor = db.cursor()

    cursor.execute("SELECT * FROM departments WHERE is_active = 1 ORDER BY name ASC")
    departments = cursor.fetchall()

    cursor.execute("""
        SELECT d.*, dept.name as department_name 
        FROM doctors d 
        LEFT JOIN departments dept ON d.department_id = dept.id 
        ORDER BY d.experience_years DESC
    """)
    doctors = cursor.fetchall()

    return render_template('index.html', departments=departments, doctors=doctors)

# ----------------- AUTHENTICATION -----------------
@app.route('/login', methods=['GET', 'POST'])
def login():
    if 'user_id' in session:
        return redirect(url_for('dashboard'))

    if request.method == 'POST':
        login_id = request.form.get('login_id', '').strip()
        password = request.form.get('password', '')

        db = get_db()
        cursor = db.cursor()
        cursor.execute("SELECT * FROM users WHERE (username = ? OR email = ?)", (login_id, login_id))
        user = cursor.fetchone()

        if user and check_password_hash(user['password_hash'], password):
            if user['status'] != 'active':
                flash("Your account has been deactivated. Please contact administration.", "danger")
                return render_template('login.html')

            session.clear()
            session['user_id'] = user['id']
            session['username'] = user['username']
            session['email'] = user['email']
            session['role'] = user['role']

            flash(f"Welcome back, {user['username']}! Signed in as {user['role'].capitalize()}.", "success")
            return redirect(url_for('dashboard'))
        else:
            flash("Invalid email/username or password. Please try again.", "danger")

    return render_template('login.html')

@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        full_name = request.form.get('full_name', '').strip()
        dob = request.form.get('dob', '')
        age = request.form.get('age', '')
        gender = request.form.get('gender', '')
        phone = request.form.get('phone', '').strip()
        email = request.form.get('email', '').strip().lower()
        address = request.form.get('address', '').strip()
        blood_group = request.form.get('blood_group', '')
        emergency_contact = request.form.get('emergency_contact', '').strip()
        emergency_phone = request.form.get('emergency_phone', '').strip()
        medical_history_summary = request.form.get('medical_history_summary', '').strip()
        username = request.form.get('username', '').strip().lower()
        password = request.form.get('password', '')
        confirm_password = request.form.get('confirm_password', '')

        if password != confirm_password:
            flash("Passwords do not match. Please re-enter.", "danger")
            return render_template('register.html')

        db = get_db()
        cursor = db.cursor()

        # Check existing user
        cursor.execute("SELECT id FROM users WHERE username = ? OR email = ?", (username, email))
        if cursor.fetchone():
            flash("Username or Email is already registered. Please log in.", "warning")
            return redirect(url_for('login'))

        # Create user account
        pw_hash = generate_password_hash(password)
        cursor.execute("INSERT INTO users (username, email, password_hash, role) VALUES (?, ?, ?, 'patient')", (username, email, pw_hash))
        new_user_id = cursor.lastrowid

        # Generate unique patient UID
        cursor.execute("SELECT COUNT(*) as count FROM patients")
        total_pats = cursor.fetchone()['count'] + 1
        patient_uid = f"PAT-{date.today().year}-{total_pats:04d}"

        cursor.execute("""
            INSERT INTO patients (user_id, patient_uid, full_name, dob, age, gender, phone, email, address, blood_group, emergency_contact, emergency_phone, medical_history_summary)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (new_user_id, patient_uid, full_name, dob, age, gender, phone, email, address, blood_group, emergency_contact, emergency_phone, medical_history_summary))

        # Welcome notification
        cursor.execute("""
            INSERT INTO notifications (user_id, title, message, category)
            VALUES (?, 'Welcome to MedCare+ Hospital', 'Your electronic health profile has been created with Patient ID: ' || ?, 'system')
        """, (new_user_id, patient_uid))

        db.commit()

        # Auto-login
        session.clear()
        session['user_id'] = new_user_id
        session['username'] = username
        session['email'] = email
        session['role'] = 'patient'

        flash(f"Registration successful! Your Patient ID is {patient_uid}.", "success")
        return redirect(url_for('patient_dashboard'))

    return render_template('register.html')

@app.route('/logout')
def logout():
    session.clear()
    flash("You have been successfully logged out.", "info")
    return redirect(url_for('login'))

@app.route('/forgot-password', methods=['GET', 'POST'])
def forgot_password():
    if request.method == 'POST':
        email = request.form.get('email', '').strip().lower()
        new_password = request.form.get('new_password', '')
        confirm_password = request.form.get('confirm_password', '')

        if new_password != confirm_password:
            flash("Passwords do not match.", "danger")
            return render_template('forgot_password.html')

        db = get_db()
        cursor = db.cursor()
        cursor.execute("SELECT id FROM users WHERE email = ?", (email,))
        user = cursor.fetchone()

        if user:
            pw_hash = generate_password_hash(new_password)
            cursor.execute("UPDATE users SET password_hash = ? WHERE id = ?", (pw_hash, user['id']))
            db.commit()
            flash("Your password has been successfully reset. Please log in with your new password.", "success")
            return redirect(url_for('login'))
        else:
            flash("No account found with that email address.", "danger")

    return render_template('forgot_password.html')

@app.route('/profile', methods=['GET', 'POST'])
@login_required
def profile():
    db = get_db()
    cursor = db.cursor()
    user_id = session['user_id']
    role = session['role']

    cursor.execute("SELECT * FROM users WHERE id = ?", (user_id,))
    user = cursor.fetchone()

    patient = None
    doctor = None

    if role == 'patient':
        cursor.execute("SELECT * FROM patients WHERE user_id = ?", (user_id,))
        patient = cursor.fetchone()
    elif role == 'doctor':
        cursor.execute("SELECT * FROM doctors WHERE user_id = ?", (user_id,))
        doctor = cursor.fetchone()

    if request.method == 'POST':
        action = request.form.get('action')

        if action == 'update_profile':
            email = request.form.get('email', '').strip().lower()
            cursor.execute("UPDATE users SET email = ? WHERE id = ?", (email, user_id))

            if patient:
                full_name = request.form.get('full_name', '').strip()
                phone = request.form.get('phone', '').strip()
                address = request.form.get('address', '').strip()
                emergency_contact = request.form.get('emergency_contact', '').strip()
                emergency_phone = request.form.get('emergency_phone', '').strip()
                cursor.execute("""
                    UPDATE patients SET full_name = ?, phone = ?, address = ?, emergency_contact = ?, emergency_phone = ?
                    WHERE id = ?
                """, (full_name, phone, address, emergency_contact, emergency_phone, patient['id']))
            elif doctor:
                name = request.form.get('name', '').strip()
                phone = request.form.get('phone', '').strip()
                consultation_fee = float(request.form.get('consultation_fee', 500.0))
                available_timings = request.form.get('available_timings', '').strip()
                cursor.execute("""
                    UPDATE doctors SET name = ?, phone = ?, consultation_fee = ?, available_timings = ?
                    WHERE id = ?
                """, (name, phone, consultation_fee, available_timings, doctor['id']))

            db.commit()
            flash("Profile details updated successfully.", "success")
            return redirect(url_for('profile'))

        elif action == 'change_password':
            current_password = request.form.get('current_password', '')
            new_password = request.form.get('new_password', '')
            confirm_password = request.form.get('confirm_password', '')

            if not check_password_hash(user['password_hash'], current_password):
                flash("Current password is incorrect.", "danger")
            elif new_password != confirm_password:
                flash("New passwords do not match.", "danger")
            else:
                pw_hash = generate_password_hash(new_password)
                cursor.execute("UPDATE users SET password_hash = ? WHERE id = ?", (pw_hash, user_id))
                db.commit()
                flash("Password updated successfully.", "success")

            return redirect(url_for('profile'))

    return render_template('profile.html', user=user, patient=patient, doctor=doctor)

@app.route('/notifications/read-all')
@login_required
def mark_notifications_read():
    db = get_db()
    cursor = db.cursor()
    cursor.execute("UPDATE notifications SET is_read = 1 WHERE user_id = ?", (session['user_id'],))
    db.commit()
    flash("Notifications marked as read.", "info")
    return redirect(request.referrer or url_for('dashboard'))

# ----------------- ROLE-BASED DASHBOARDS -----------------
@app.route('/dashboard')
@login_required
def dashboard():
    role = session.get('role')
    if role == 'admin':
        return redirect(url_for('admin_dashboard'))
    elif role == 'doctor':
        return redirect(url_for('doctor_dashboard'))
    elif role == 'patient':
        return redirect(url_for('patient_dashboard'))
    elif role == 'receptionist':
        return redirect(url_for('receptionist_dashboard'))
    elif role == 'nurse':
        return redirect(url_for('nurse_dashboard'))
    elif role == 'laboratory':
        return redirect(url_for('laboratory_dashboard'))
    elif role == 'pharmacist':
        return redirect(url_for('pharmacist_dashboard'))
    return redirect(url_for('index'))

@app.route('/dashboard/admin')
@role_required('admin')
def admin_dashboard():
    db = get_db()
    cursor = db.cursor()
    today_str = date.today().strftime('%Y-%m-%d')

    stats = {}
    cursor.execute("SELECT COUNT(*) as count FROM patients")
    stats['total_patients'] = cursor.fetchone()['count']

    cursor.execute("SELECT COUNT(*) as count FROM doctors")
    stats['total_doctors'] = cursor.fetchone()['count']

    cursor.execute("SELECT COUNT(*) as count FROM doctors WHERE is_available = 1")
    stats['available_doctors'] = cursor.fetchone()['count']

    cursor.execute("SELECT COUNT(*) as count FROM employees")
    stats['total_employees'] = cursor.fetchone()['count']

    cursor.execute("SELECT COUNT(*) as count FROM appointments")
    stats['total_appointments'] = cursor.fetchone()['count']

    cursor.execute("SELECT COUNT(*) as count FROM appointments WHERE appointment_date = ?", (today_str,))
    stats['today_appointments'] = cursor.fetchone()['count']

    cursor.execute("SELECT COUNT(*) as count FROM appointments WHERE status = 'Pending'")
    stats['pending_appointments'] = cursor.fetchone()['count']

    cursor.execute("SELECT COUNT(*) as count FROM appointments WHERE status = 'Completed'")
    stats['completed_appointments'] = cursor.fetchone()['count']

    cursor.execute("SELECT COUNT(*) as count FROM appointments WHERE status = 'Cancelled'")
    stats['cancelled_appointments'] = cursor.fetchone()['count']

    cursor.execute("SELECT COALESCE(SUM(paid_amount), 0.0) as revenue FROM bills")
    stats['total_revenue'] = cursor.fetchone()['revenue']

    cursor.execute("SELECT COUNT(*) as count FROM medicines WHERE quantity <= reorder_level")
    stats['low_stock_medicines'] = cursor.fetchone()['count']

    # Recent Appointments
    cursor.execute("""
        SELECT a.*, p.full_name as patient_name, d.name as doctor_name, dept.name as department_name
        FROM appointments a
        JOIN patients p ON a.patient_id = p.id
        JOIN doctors d ON a.doctor_id = d.id
        LEFT JOIN departments dept ON a.department_id = dept.id
        ORDER BY a.created_at DESC LIMIT 8
    """)
    recent_appointments = cursor.fetchall()

    # Active Emergency Cases
    cursor.execute("""
        SELECT e.*, d.name as doctor_name
        FROM emergency_cases e
        LEFT JOIN doctors d ON e.assigned_doctor_id = d.id
        WHERE e.status NOT IN ('Discharged')
        ORDER BY CASE priority_level WHEN 'Critical' THEN 1 WHEN 'Urgent' THEN 2 ELSE 3 END, arrival_time DESC LIMIT 5
    """)
    active_emergencies = cursor.fetchall()

    cursor.execute("SELECT COUNT(*) as count FROM emergency_cases WHERE status NOT IN ('Discharged')")
    emergency_count = cursor.fetchone()['count']

    return render_template(
        'admin_dashboard.html',
        stats=stats,
        recent_appointments=recent_appointments,
        active_emergencies=active_emergencies,
        emergency_count=emergency_count
    )

@app.route('/dashboard/doctor')
@role_required('doctor')
def doctor_dashboard():
    db = get_db()
    cursor = db.cursor()
    today_str = date.today().strftime('%Y-%m-%d')

    cursor.execute("SELECT * FROM doctors WHERE user_id = ?", (session['user_id'],))
    doctor = cursor.fetchone()
    if not doctor:
        flash("Doctor profile not found.", "danger")
        return redirect(url_for('index'))

    stats = {}
    cursor.execute("SELECT COUNT(*) as count FROM appointments WHERE doctor_id = ? AND appointment_date = ?", (doctor['id'], today_str))
    stats['today_count'] = cursor.fetchone()['count']

    cursor.execute("SELECT COUNT(*) as count FROM tokens WHERE doctor_id = ? AND queue_date = ? AND status = 'Waiting'", (doctor['id'], today_str))
    stats['waiting_count'] = cursor.fetchone()['count']

    cursor.execute("SELECT COUNT(DISTINCT patient_id) as count FROM appointments WHERE doctor_id = ?", (doctor['id'],))
    stats['total_assigned_patients'] = cursor.fetchone()['count']

    cursor.execute("SELECT COUNT(*) as count FROM appointments WHERE doctor_id = ? AND status = 'Completed'", (doctor['id'],))
    stats['completed_count'] = cursor.fetchone()['count']

    # Active Token in consultation
    cursor.execute("""
        SELECT t.*, p.full_name as patient_name, p.patient_uid, p.blood_group, p.age, p.gender, p.medical_history_summary, a.reason
        FROM tokens t
        JOIN patients p ON t.patient_id = p.id
        JOIN appointments a ON t.appointment_id = a.id
        WHERE t.doctor_id = ? AND t.queue_date = ? AND t.status = 'In Consultation'
        LIMIT 1
    """, (doctor['id'], today_str))
    current_token = cursor.fetchone()

    # Today's Queue list
    cursor.execute("""
        SELECT t.*, p.full_name as patient_name, p.patient_uid, p.age, p.gender, a.time_slot, a.reason
        FROM tokens t
        JOIN patients p ON t.patient_id = p.id
        JOIN appointments a ON t.appointment_id = a.id
        WHERE t.doctor_id = ? AND t.queue_date = ?
        ORDER BY CASE t.status WHEN 'In Consultation' THEN 1 WHEN 'Waiting' THEN 2 ELSE 3 END, t.id ASC
    """, (doctor['id'], today_str))
    today_queue = cursor.fetchall()

    return render_template(
        'doctor_dashboard.html',
        doctor=doctor,
        stats=stats,
        current_token=current_token,
        today_queue=today_queue,
        today_str=today_str
    )

@app.route('/doctor/availability/toggle', methods=['POST'])
@role_required('doctor')
def toggle_doctor_availability():
    db = get_db()
    cursor = db.cursor()
    cursor.execute("SELECT is_available FROM doctors WHERE user_id = ?", (session['user_id'],))
    row = cursor.fetchone()
    if row:
        new_val = 0 if row['is_available'] == 1 else 1
        cursor.execute("UPDATE doctors SET is_available = ? WHERE user_id = ?", (new_val, session['user_id']))
        db.commit()
        status_txt = "Available for OPD" if new_val == 1 else "Off-Duty / Paused"
        flash(f"Availability updated to: {status_txt}.", "info")
    return redirect(url_for('doctor_dashboard'))

@app.route('/dashboard/patient')
@role_required('patient')
def patient_dashboard():
    db = get_db()
    cursor = db.cursor()
    today_str = date.today().strftime('%Y-%m-%d')

    cursor.execute("SELECT * FROM patients WHERE user_id = ?", (session['user_id'],))
    patient = cursor.fetchone()
    if not patient:
        flash("Patient profile not linked.", "danger")
        return redirect(url_for('index'))

    # Active Queue Token for today
    cursor.execute("""
        SELECT t.*, d.name as doctor_name, d.room_no, dept.name as department_name, a.time_slot
        FROM tokens t
        JOIN doctors d ON t.doctor_id = d.id
        LEFT JOIN departments dept ON d.department_id = dept.id
        JOIN appointments a ON t.appointment_id = a.id
        WHERE t.patient_id = ? AND t.queue_date = ? AND t.status IN ('Waiting', 'In Consultation')
        ORDER BY t.id DESC LIMIT 1
    """, (patient['id'], today_str))
    active_token = cursor.fetchone()

    # Appointments list
    cursor.execute("""
        SELECT a.*, d.name as doctor_name, dept.name as department_name
        FROM appointments a
        JOIN doctors d ON a.doctor_id = d.id
        LEFT JOIN departments dept ON a.department_id = dept.id
        WHERE a.patient_id = ?
        ORDER BY a.appointment_date DESC, a.created_at DESC
    """, (patient['id'],))
    appointments = cursor.fetchall()

    # Prescriptions
    cursor.execute("""
        SELECT r.*, d.name as doctor_name
        FROM prescriptions r
        JOIN doctors d ON r.doctor_id = d.id
        WHERE r.patient_id = ?
        ORDER BY r.prescription_date DESC
    """, (patient['id'],))
    prescriptions = cursor.fetchall()

    # Lab Reports
    cursor.execute("""
        SELECT lr.*, lt.test_name, lt.category, lt.normal_range, d.name as doctor_name
        FROM lab_requests lr
        JOIN lab_tests lt ON lr.test_id = lt.id
        LEFT JOIN doctors d ON lr.doctor_id = d.id
        WHERE lr.patient_id = ?
        ORDER BY lr.requested_at DESC
    """, (patient['id'],))
    lab_reports = cursor.fetchall()

    # Bills
    cursor.execute("SELECT * FROM bills WHERE patient_id = ? ORDER BY bill_date DESC", (patient['id'],))
    bills = cursor.fetchall()

    return render_template(
        'patient_dashboard.html',
        patient=patient,
        active_token=active_token,
        appointments=appointments,
        prescriptions=prescriptions,
        lab_reports=lab_reports,
        bills=bills
    )

@app.route('/dashboard/receptionist')
@role_required('receptionist', 'admin')
def receptionist_dashboard():
    db = get_db()
    cursor = db.cursor()
    today_str = date.today().strftime('%Y-%m-%d')

    cursor.execute("SELECT * FROM employees WHERE user_id = ?", (session.get('user_id'),))
    employee = cursor.fetchone()

    stats = {}
    cursor.execute("SELECT COUNT(*) as count FROM appointments WHERE appointment_date = ?", (today_str,))
    stats['today_patients'] = cursor.fetchone()['count']

    cursor.execute("SELECT COUNT(*) as count FROM tokens WHERE queue_date = ? AND status = 'Waiting'", (today_str,))
    stats['waiting_tokens'] = cursor.fetchone()['count']

    cursor.execute("SELECT COUNT(*) as count FROM doctors WHERE is_available = 1")
    stats['active_doctors'] = cursor.fetchone()['count']

    cursor.execute("SELECT COUNT(*) as count FROM emergency_cases WHERE status NOT IN ('Discharged')")
    stats['emergencies'] = cursor.fetchone()['count']

    # Today's tokens list
    cursor.execute("""
        SELECT t.*, p.full_name as patient_name, p.patient_uid, p.phone, d.name as doctor_name, d.room_no, dept.name as department_name, a.time_slot
        FROM tokens t
        JOIN patients p ON t.patient_id = p.id
        JOIN doctors d ON t.doctor_id = d.id
        LEFT JOIN departments dept ON d.department_id = dept.id
        JOIN appointments a ON t.appointment_id = a.id
        WHERE t.queue_date = ?
        ORDER BY CASE t.status WHEN 'In Consultation' THEN 1 WHEN 'Waiting' THEN 2 ELSE 3 END, t.id ASC
    """, (today_str,))
    today_tokens = cursor.fetchall()

    cursor.execute("SELECT d.*, dept.name as department_name FROM doctors d LEFT JOIN departments dept ON d.department_id = dept.id WHERE d.is_available = 1")
    doctors = cursor.fetchall()

    return render_template(
        'receptionist_dashboard.html',
        employee=employee,
        stats=stats,
        today_tokens=today_tokens,
        doctors=doctors,
        today_str=today_str
    )

@app.route('/receptionist/walkin', methods=['POST'])
@role_required('receptionist', 'admin')
def register_walkin():
    full_name = request.form.get('full_name', '').strip()
    age = request.form.get('age', '')
    gender = request.form.get('gender', '')
    phone = request.form.get('phone', '').strip()
    blood_group = request.form.get('blood_group', 'Unknown')
    doctor_id = int(request.form.get('doctor_id'))
    time_slot = request.form.get('time_slot', '09:00 AM')
    reason = request.form.get('reason', 'Walk-in consultation').strip()
    today_str = date.today().strftime('%Y-%m-%d')

    db = get_db()
    cursor = db.cursor()

    # Generate patient UID
    cursor.execute("SELECT COUNT(*) as count FROM patients")
    total_pats = cursor.fetchone()['count'] + 1
    patient_uid = f"PAT-{date.today().year}-{total_pats:04d}"

    cursor.execute("""
        INSERT INTO patients (patient_uid, full_name, age, gender, phone, blood_group, medical_history_summary)
        VALUES (?, ?, ?, ?, ?, ?, 'Walk-in patient')
    """, (patient_uid, full_name, age, gender, phone, blood_group))
    patient_id = cursor.lastrowid

    # Get doctor department
    cursor.execute("SELECT department_id, name, room_no FROM doctors WHERE id = ?", (doctor_id,))
    doc = cursor.fetchone()
    dept_id = doc['department_id'] if doc else None

    # Generate appointment UID
    cursor.execute("SELECT COUNT(*) as count FROM appointments")
    total_apts = cursor.fetchone()['count'] + 1
    appointment_uid = f"APT-{date.today().year}-{total_apts:04d}"

    cursor.execute("""
        INSERT INTO appointments (appointment_uid, patient_id, doctor_id, department_id, appointment_date, time_slot, reason, status)
        VALUES (?, ?, ?, ?, ?, ?, ?, 'Confirmed')
    """, (appointment_uid, patient_id, doctor_id, dept_id, today_str, time_slot, reason))
    appointment_id = cursor.lastrowid

    # Generate Token
    cursor.execute("SELECT COUNT(*) as count FROM tokens WHERE queue_date = ?", (today_str,))
    token_seq = cursor.fetchone()['count'] + 101
    token_num = f"TKN-{token_seq}"
    est_wait = (token_seq - 101) * 15

    cursor.execute("""
        INSERT INTO tokens (token_number, appointment_id, patient_id, doctor_id, queue_date, status, estimated_time_minutes)
        VALUES (?, ?, ?, ?, ?, 'Waiting', ?)
    """, (token_num, appointment_id, patient_id, doctor_id, today_str, est_wait))

    db.commit()
    flash(f"Walk-in patient registered! Token {token_num} issued for {doc['name']} ({doc['room_no']}).", "success")
    return redirect(url_for('receptionist_dashboard'))

@app.route('/dashboard/nurse')
@role_required('nurse', 'admin')
def nurse_dashboard():
    db = get_db()
    cursor = db.cursor()
    today_str = date.today().strftime('%Y-%m-%d')

    cursor.execute("SELECT * FROM employees WHERE user_id = ?", (session.get('user_id'),))
    employee = cursor.fetchone()

    cursor.execute("""
        SELECT t.*, p.full_name as patient_name, p.patient_uid, p.age, p.gender, p.blood_group, d.name as doctor_name, d.room_no, a.time_slot
        FROM tokens t
        JOIN patients p ON t.patient_id = p.id
        JOIN doctors d ON t.doctor_id = d.id
        JOIN appointments a ON t.appointment_id = a.id
        WHERE t.queue_date = ?
        ORDER BY CASE t.status WHEN 'In Consultation' THEN 1 WHEN 'Waiting' THEN 2 ELSE 3 END, t.id ASC
    """, (today_str,))
    queue_tokens = cursor.fetchall()

    waiting_count = sum(1 for t in queue_tokens if t['status'] == 'Waiting')
    consulting_count = sum(1 for t in queue_tokens if t['status'] == 'In Consultation')

    cursor.execute("SELECT COUNT(*) as count FROM emergency_cases WHERE priority_level = 'Critical' AND status NOT IN ('Discharged')")
    critical_emergency_count = cursor.fetchone()['count']

    return render_template(
        'nurse_dashboard.html',
        employee=employee,
        queue_tokens=queue_tokens,
        waiting_count=waiting_count,
        consulting_count=consulting_count,
        critical_emergency_count=critical_emergency_count,
        today_str=today_str
    )

@app.route('/dashboard/laboratory')
@role_required('laboratory', 'admin')
def laboratory_dashboard():
    db = get_db()
    cursor = db.cursor()

    cursor.execute("SELECT * FROM employees WHERE user_id = ?", (session.get('user_id'),))
    employee = cursor.fetchone()

    stats = {}
    cursor.execute("SELECT COUNT(*) as count FROM lab_requests WHERE status IN ('Requested', 'Sample Collected')")
    stats['pending_requests'] = cursor.fetchone()['count']

    cursor.execute("SELECT COUNT(*) as count FROM lab_requests WHERE status = 'Processing'")
    stats['processing_requests'] = cursor.fetchone()['count']

    cursor.execute("SELECT COUNT(*) as count FROM lab_requests WHERE status = 'Completed'")
    stats['completed_requests'] = cursor.fetchone()['count']

    cursor.execute("SELECT COUNT(*) as count FROM lab_tests")
    stats['total_catalog_tests'] = cursor.fetchone()['count']

    cursor.execute("""
        SELECT lr.*, lt.test_name, lt.category, lt.normal_range, p.full_name as patient_name, p.patient_uid, d.name as doctor_name
        FROM lab_requests lr
        JOIN lab_tests lt ON lr.test_id = lt.id
        JOIN patients p ON lr.patient_id = p.id
        LEFT JOIN doctors d ON lr.doctor_id = d.id
        ORDER BY lr.requested_at DESC
    """)
    lab_requests = cursor.fetchall()

    cursor.execute("SELECT * FROM lab_tests ORDER BY category, test_name")
    catalog_tests = cursor.fetchall()

    cursor.execute("SELECT id, full_name, patient_uid FROM patients ORDER BY full_name")
    patients = cursor.fetchall()

    return render_template(
        'laboratory_dashboard.html',
        employee=employee,
        stats=stats,
        lab_requests=lab_requests,
        catalog_tests=catalog_tests,
        patients=patients
    )

@app.route('/dashboard/pharmacist')
@role_required('pharmacist', 'admin')
def pharmacist_dashboard():
    db = get_db()
    cursor = db.cursor()
    today_str = date.today().strftime('%Y-%m-%d')

    cursor.execute("SELECT * FROM employees WHERE user_id = ?", (session.get('user_id'),))
    employee = cursor.fetchone()

    cursor.execute("SELECT * FROM medicines ORDER BY name ASC")
    medicines = cursor.fetchall()

    cursor.execute("SELECT * FROM medicines WHERE quantity <= reorder_level")
    low_stock_medicines = cursor.fetchall()

    cursor.execute("SELECT COALESCE(SUM(quantity * price), 0.0) as val FROM medicines")
    total_inventory_value = cursor.fetchone()['val']

    cursor.execute("SELECT COUNT(*) as count FROM prescriptions")
    total_prescriptions_count = cursor.fetchone()['count']

    return render_template(
        'pharmacist_dashboard.html',
        employee=employee,
        medicines=medicines,
        low_stock_medicines=low_stock_medicines,
        total_inventory_value=total_inventory_value,
        total_prescriptions_count=total_prescriptions_count,
        today_str=today_str
    )

# ----------------- APPOINTMENTS & SCHEDULING -----------------
@app.route('/appointments')
def appointments():
    db = get_db()
    cursor = db.cursor()
    today_str = date.today().strftime('%Y-%m-%d')

    selected_dept = request.args.get('dept', '')
    selected_status = request.args.get('status', '')
    selected_date = request.args.get('date', '')
    patient_filter_id = request.args.get('patient_id', '')
    doc_filter_id = request.args.get('doc_id', '')

    query = """
        SELECT a.*, p.full_name as patient_name, p.patient_uid, p.phone as patient_phone,
               d.name as doctor_name, d.room_no, d.specialization, dept.name as department_name,
               t.token_number
        FROM appointments a
        JOIN patients p ON a.patient_id = p.id
        JOIN doctors d ON a.doctor_id = d.id
        LEFT JOIN departments dept ON a.department_id = dept.id
        LEFT JOIN tokens t ON a.id = t.appointment_id
        WHERE 1=1
    """
    params = []

    # If logged in as patient, restrict to own appointments unless admin/staff
    if session.get('role') == 'patient':
        cursor.execute("SELECT id FROM patients WHERE user_id = ?", (session['user_id'],))
        pat = cursor.fetchone()
        if pat:
            query += " AND a.patient_id = ?"
            params.append(pat['id'])

    if selected_dept:
        query += " AND dept.name = ?"
        params.append(selected_dept)
    if selected_status:
        query += " AND a.status = ?"
        params.append(selected_status)
    if selected_date:
        query += " AND a.appointment_date = ?"
        params.append(selected_date)
    if patient_filter_id:
        query += " AND a.patient_id = ?"
        params.append(patient_filter_id)
    if doc_filter_id:
        query += " AND a.doctor_id = ?"
        params.append(doc_filter_id)

    query += " ORDER BY a.appointment_date DESC, a.created_at DESC"
    cursor.execute(query, params)
    appointments_list = cursor.fetchall()

    cursor.execute("SELECT * FROM departments WHERE is_active = 1 ORDER BY name ASC")
    departments = cursor.fetchall()

    cursor.execute("SELECT d.*, dept.name as department_name FROM doctors d LEFT JOIN departments dept ON d.department_id = dept.id WHERE d.is_available = 1")
    doctors = cursor.fetchall()

    cursor.execute("SELECT id, full_name, patient_uid, phone FROM patients ORDER BY full_name")
    patients = cursor.fetchall()

    return render_template(
        'appointments.html',
        appointments=appointments_list,
        departments=departments,
        doctors=doctors,
        patients=patients,
        selected_dept=selected_dept,
        selected_status=selected_status,
        selected_date=selected_date
    )

@app.route('/appointments/book', methods=['POST'])
def book_appointment():
    db = get_db()
    cursor = db.cursor()

    # Determine patient_id
    if session.get('role') == 'patient':
        cursor.execute("SELECT id FROM patients WHERE user_id = ?", (session['user_id'],))
        pat = cursor.fetchone()
        if not pat:
            flash("Patient record not found.", "danger")
            return redirect(url_for('appointments'))
        patient_id = pat['id']
    else:
        patient_id = request.form.get('patient_id')
        if not patient_id:
            flash("Please select a patient.", "danger")
            return redirect(url_for('appointments'))
        patient_id = int(patient_id)

    doctor_id = int(request.form.get('doctor_id'))
    appointment_date = request.form.get('appointment_date')
    time_slot = request.form.get('time_slot')
    reason = request.form.get('reason', '').strip()

    # Double Booking Prevention Check:
    cursor.execute("""
        SELECT id FROM appointments 
        WHERE doctor_id = ? AND appointment_date = ? AND time_slot = ? AND status != 'Cancelled'
    """, (doctor_id, appointment_date, time_slot))
    existing = cursor.fetchone()

    if existing:
        flash(f"Slot Collision: That doctor is already booked for {time_slot} on {appointment_date}. Please pick another time slot.", "warning")
        return redirect(url_for('appointments'))

    # Get doctor department
    cursor.execute("SELECT department_id, name, room_no, user_id FROM doctors WHERE id = ?", (doctor_id,))
    doc = cursor.fetchone()
    dept_id = doc['department_id'] if doc else None

    # Generate unique Appointment UID
    cursor.execute("SELECT COUNT(*) as count FROM appointments")
    count_apts = cursor.fetchone()['count'] + 1
    appointment_uid = f"APT-{date.today().year}-{count_apts:04d}"

    cursor.execute("""
        INSERT INTO appointments (appointment_uid, patient_id, doctor_id, department_id, appointment_date, time_slot, reason, status)
        VALUES (?, ?, ?, ?, ?, ?, ?, 'Confirmed')
    """, (appointment_uid, patient_id, doctor_id, dept_id, appointment_date, time_slot, reason))
    appointment_id = cursor.lastrowid

    # Auto Token Generation
    cursor.execute("SELECT COUNT(*) as count FROM tokens WHERE doctor_id = ? AND queue_date = ?", (doctor_id, appointment_date))
    token_seq = cursor.fetchone()['count'] + 101
    token_num = f"TKN-{token_seq}"
    est_wait = (token_seq - 101) * 15

    cursor.execute("""
        INSERT INTO tokens (token_number, appointment_id, patient_id, doctor_id, queue_date, status, estimated_time_minutes)
        VALUES (?, ?, ?, ?, ?, 'Waiting', ?)
    """, (token_num, appointment_id, patient_id, doctor_id, appointment_date, est_wait))

    # Patient Notification
    cursor.execute("SELECT user_id, full_name FROM patients WHERE id = ?", (patient_id,))
    pat_info = cursor.fetchone()
    if pat_info and pat_info['user_id']:
        cursor.execute("""
            INSERT INTO notifications (user_id, title, message, category)
            VALUES (?, 'Appointment Confirmed', 'Appointment ' || ? || ' booked with ' || ? || ' on ' || ? || ' at ' || ? || '. Token: ' || ?, 'appointment')
        """, (pat_info['user_id'], appointment_uid, doc['name'], appointment_date, time_slot, token_num))

    # Doctor Notification
    if doc and doc['user_id']:
        cursor.execute("""
            INSERT INTO notifications (user_id, title, message, category)
            VALUES (?, 'New Patient Scheduled', 'Patient ' || ? || ' scheduled on ' || ? || ' at ' || ? || '. Token: ' || ?, 'appointment')
        """, (doc['user_id'], pat_info['full_name'], appointment_date, time_slot, token_num))

    db.commit()
    flash(f"Appointment booked successfully! Unique ID: {appointment_uid} | Token: {token_num} ({doc['room_no']}).", "success")
    return redirect(url_for('appointments'))

@app.route('/appointments/reschedule', methods=['POST'])
@login_required
def reschedule_appointment():
    appointment_id = int(request.form.get('appointment_id'))
    new_date = request.form.get('new_date')
    new_slot = request.form.get('new_slot')

    db = get_db()
    cursor = db.cursor()

    cursor.execute("SELECT doctor_id FROM appointments WHERE id = ?", (appointment_id,))
    apt = cursor.fetchone()
    if not apt:
        flash("Appointment not found.", "danger")
        return redirect(url_for('appointments'))

    # Check collision
    cursor.execute("""
        SELECT id FROM appointments 
        WHERE doctor_id = ? AND appointment_date = ? AND time_slot = ? AND id != ? AND status != 'Cancelled'
    """, (apt['doctor_id'], new_date, new_slot, appointment_id))
    if cursor.fetchone():
        flash("The selected slot is already occupied on that date. Please choose another slot.", "warning")
        return redirect(url_for('appointments'))

    cursor.execute("UPDATE appointments SET appointment_date = ?, time_slot = ? WHERE id = ?", (new_date, new_slot, appointment_id))
    cursor.execute("UPDATE tokens SET queue_date = ? WHERE appointment_id = ?", (new_date, appointment_id))
    db.commit()

    flash("Appointment rescheduled successfully.", "success")
    return redirect(url_for('appointments'))

@app.route('/appointments/cancel/<int:apt_id>', methods=['POST'])
@login_required
def cancel_appointment(apt_id):
    db = get_db()
    cursor = db.cursor()
    cursor.execute("UPDATE appointments SET status = 'Cancelled' WHERE id = ?", (apt_id,))
    cursor.execute("UPDATE tokens SET status = 'Cancelled' WHERE appointment_id = ?", (apt_id,))
    db.commit()
    flash("Appointment has been cancelled.", "info")
    return redirect(request.referrer or url_for('appointments'))

@app.route('/appointments/status/<int:apt_id>', methods=['POST'])
@role_required('admin', 'doctor', 'receptionist')
def update_appointment_status(apt_id):
    new_status = request.form.get('status')
    db = get_db()
    cursor = db.cursor()
    cursor.execute("UPDATE appointments SET status = ? WHERE id = ?", (new_status, apt_id))
    if new_status == 'Completed':
        cursor.execute("UPDATE tokens SET status = 'Completed', completed_at = CURRENT_TIMESTAMP WHERE appointment_id = ?", (apt_id,))
    elif new_status == 'Cancelled':
        cursor.execute("UPDATE tokens SET status = 'Cancelled' WHERE appointment_id = ?", (apt_id,))
    db.commit()
    flash(f"Appointment status updated to {new_status}.", "success")
    return redirect(request.referrer or url_for('appointments'))

# ----------------- SMART TOKEN & QUEUE MANAGEMENT -----------------
@app.route('/live-queue')
def live_queue():
    db = get_db()
    cursor = db.cursor()
    today_str = date.today().strftime('%Y-%m-%d')

    cursor.execute("""
        SELECT d.*, dept.name as department_name
        FROM doctors d
        LEFT JOIN departments dept ON d.department_id = dept.id
        WHERE d.is_available = 1
        ORDER BY d.name ASC
    """)
    active_doctors = cursor.fetchall()

    doctors_with_queue = []
    for doc in active_doctors:
        # Current token in room
        cursor.execute("""
            SELECT t.*, p.full_name as patient_name
            FROM tokens t
            JOIN patients p ON t.patient_id = p.id
            WHERE t.doctor_id = ? AND t.queue_date = ? AND t.status = 'In Consultation'
            LIMIT 1
        """, (doc['id'], today_str))
        current_token = cursor.fetchone()

        # Next up
        cursor.execute("""
            SELECT t.*, p.full_name as patient_name
            FROM tokens t
            JOIN patients p ON t.patient_id = p.id
            WHERE t.doctor_id = ? AND t.queue_date = ? AND t.status = 'Waiting'
            ORDER BY t.id ASC LIMIT 1
        """, (doc['id'], today_str))
        next_token = cursor.fetchone()

        # Waiting count
        cursor.execute("SELECT COUNT(*) as count FROM tokens WHERE doctor_id = ? AND queue_date = ? AND status = 'Waiting'", (doc['id'], today_str))
        waiting_count = cursor.fetchone()['count']

        doc_dict = dict(doc)
        doc_dict['current_token'] = current_token
        doc_dict['next_token'] = next_token
        doc_dict['waiting_count'] = waiting_count
        doctors_with_queue.append(doc_dict)

    # Master Queue Table
    cursor.execute("""
        SELECT t.*, p.full_name as patient_name, p.patient_uid, d.name as doctor_name, d.specialization, d.room_no, a.time_slot
        FROM tokens t
        JOIN patients p ON t.patient_id = p.id
        JOIN doctors d ON t.doctor_id = d.id
        JOIN appointments a ON t.appointment_id = a.id
        WHERE t.queue_date = ?
        ORDER BY CASE t.status WHEN 'In Consultation' THEN 1 WHEN 'Waiting' THEN 2 ELSE 3 END, t.id ASC
    """, (today_str,))
    all_today_tokens = cursor.fetchall()

    return render_template(
        'live_queue.html',
        doctors_with_queue=doctors_with_queue,
        all_today_tokens=all_today_tokens,
        today_str=today_str
    )

@app.route('/tokens/update/<int:token_id>', methods=['POST'])
@login_required
def update_token_status(token_id):
    status = request.form.get('status')
    db = get_db()
    cursor = db.cursor()

    if status == 'In Consultation':
        cursor.execute("UPDATE tokens SET status = ?, called_at = CURRENT_TIMESTAMP WHERE id = ?", (status, token_id))
    elif status == 'Completed':
        cursor.execute("UPDATE tokens SET status = ?, completed_at = CURRENT_TIMESTAMP WHERE id = ?", (status, token_id))
        cursor.execute("UPDATE appointments SET status = 'Completed' WHERE id = (SELECT appointment_id FROM tokens WHERE id = ?)", (token_id,))
    else:
        cursor.execute("UPDATE tokens SET status = ? WHERE id = ?", (status, token_id))

    db.commit()
    flash(f"Token status updated to {status}.", "success")
    return redirect(request.referrer or url_for('live_queue'))

# ----------------- CLINICAL RECORDS & PRESCRIPTIONS -----------------
@app.route('/medical-records')
@login_required
def medical_records():
    db = get_db()
    cursor = db.cursor()

    query = """
        SELECT m.*, p.full_name as patient_name, p.patient_uid, p.blood_group,
               d.name as doctor_name, d.specialization
        FROM medical_records m
        JOIN patients p ON m.patient_id = p.id
        JOIN doctors d ON m.doctor_id = d.id
        WHERE 1=1
    """
    params = []

    # If patient, show only their own records
    if session.get('role') == 'patient':
        cursor.execute("SELECT id FROM patients WHERE user_id = ?", (session['user_id'],))
        pat = cursor.fetchone()
        if pat:
            query += " AND m.patient_id = ?"
            params.append(pat['id'])
    else:
        patient_id = request.args.get('patient_id')
        if patient_id:
            query += " AND m.patient_id = ?"
            params.append(patient_id)

    query += " ORDER BY m.visit_date DESC, m.created_at DESC"
    cursor.execute(query, params)
    records = cursor.fetchall()

    cursor.execute("SELECT id, full_name, patient_uid FROM patients ORDER BY full_name")
    patients = cursor.fetchall()

    cursor.execute("SELECT id, name, specialization FROM doctors WHERE is_available = 1 ORDER BY name")
    doctors = cursor.fetchall()

    doctor = None
    if session.get('role') == 'doctor':
        cursor.execute("SELECT * FROM doctors WHERE user_id = ?", (session['user_id'],))
        doctor = cursor.fetchone()

    return render_template('medical_records.html', records=records, patients=patients, doctors=doctors, doctor=doctor)

@app.route('/medical-records/add', methods=['POST'])
@role_required('doctor', 'admin', 'nurse')
def add_medical_record():
    patient_id = int(request.form.get('patient_id'))
    doctor_id = request.form.get('doctor_id')
    if not doctor_id:
        if session.get('role') == 'doctor':
            db = get_db()
            cursor = db.cursor()
            cursor.execute("SELECT id FROM doctors WHERE user_id = ?", (session['user_id'],))
            doc = cursor.fetchone()
            doctor_id = doc['id'] if doc else 1
        else:
            doctor_id = 1
    else:
        doctor_id = int(doctor_id)

    visit_date = date.today().strftime('%Y-%m-%d')
    symptoms = request.form.get('symptoms', '').strip()
    diagnosis = request.form.get('diagnosis', 'Clinical Evaluation').strip()
    treatment = request.form.get('treatment', '').strip()
    doctor_notes = request.form.get('doctor_notes', '').strip()
    bp = request.form.get('bp', '').strip()
    pulse = request.form.get('pulse', '').strip()
    temperature = request.form.get('temperature', '').strip()
    spo2 = request.form.get('spo2', '').strip()
    weight = request.form.get('weight', '').strip()
    allergies = request.form.get('allergies', '').strip()
    follow_up_date = request.form.get('follow_up_date', '')

    db = get_db()
    cursor = db.cursor()
    cursor.execute("""
        INSERT INTO medical_records (patient_id, doctor_id, visit_date, symptoms, diagnosis, treatment, doctor_notes, bp, pulse, temperature, spo2, weight, allergies, follow_up_date)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    """, (patient_id, doctor_id, visit_date, symptoms, diagnosis, treatment, doctor_notes, bp, pulse, temperature, spo2, weight, allergies, follow_up_date))

    # Update patient allergies if provided
    if allergies:
        cursor.execute("UPDATE patients SET medical_history_summary = ? WHERE id = ?", (allergies, patient_id))

    db.commit()
    flash("Medical consultation record and vitals saved successfully.", "success")
    return redirect(request.referrer or url_for('medical_records'))

@app.route('/prescriptions')
@login_required
def prescriptions():
    db = get_db()
    cursor = db.cursor()

    query = """
        SELECT r.*, p.full_name as patient_name, p.patient_uid, d.name as doctor_name, d.specialization,
               (SELECT COUNT(*) FROM prescription_items WHERE prescription_id = r.id) as item_count
        FROM prescriptions r
        JOIN patients p ON r.patient_id = p.id
        JOIN doctors d ON r.doctor_id = d.id
        WHERE 1=1
    """
    params = []

    if session.get('role') == 'patient':
        cursor.execute("SELECT id FROM patients WHERE user_id = ?", (session['user_id'],))
        pat = cursor.fetchone()
        if pat:
            query += " AND r.patient_id = ?"
            params.append(pat['id'])

    query += " ORDER BY r.prescription_date DESC, r.created_at DESC"
    cursor.execute(query, params)
    prescriptions_list = cursor.fetchall()

    cursor.execute("SELECT id, full_name, patient_uid FROM patients ORDER BY full_name")
    patients = cursor.fetchall()

    return render_template('prescriptions.html', prescriptions=prescriptions_list, patients=patients)

@app.route('/prescriptions/add', methods=['POST'])
@role_required('doctor', 'admin')
def add_prescription():
    patient_id = int(request.form.get('patient_id'))
    diagnosis = request.form.get('diagnosis', '').strip()
    instructions = request.form.get('instructions', '').strip()
    appointment_id = request.form.get('appointment_id')
    appointment_id = int(appointment_id) if appointment_id else None
    prescription_date = date.today().strftime('%Y-%m-%d')

    db = get_db()
    cursor = db.cursor()

    # Get doctor id
    if session.get('role') == 'doctor':
        cursor.execute("SELECT id FROM doctors WHERE user_id = ?", (session['user_id'],))
        doc = cursor.fetchone()
        doctor_id = doc['id'] if doc else 1
    else:
        doctor_id = 1

    cursor.execute("SELECT COUNT(*) as count FROM prescriptions")
    count_rx = cursor.fetchone()['count'] + 1
    prescription_uid = f"RX-{date.today().year}-{count_rx:04d}"

    cursor.execute("""
        INSERT INTO prescriptions (prescription_uid, patient_id, doctor_id, appointment_id, diagnosis, instructions, prescription_date)
        VALUES (?, ?, ?, ?, ?, ?, ?)
    """, (prescription_uid, patient_id, doctor_id, appointment_id, diagnosis, instructions, prescription_date))
    prescription_id = cursor.lastrowid

    # Items lines
    med_names = request.form.getlist('med_name[]')
    med_dosages = request.form.getlist('med_dosage[]')
    med_freqs = request.form.getlist('med_frequency[]')
    med_durations = request.form.getlist('med_duration[]')
    med_instructions = request.form.getlist('med_instructions[]')

    for i in range(len(med_names)):
        name = med_names[i].strip()
        if name:
            dosage = med_dosages[i].strip() if i < len(med_dosages) else '1 Tab'
            freq = med_freqs[i].strip() if i < len(med_freqs) else 'Once daily'
            duration = med_durations[i].strip() if i < len(med_durations) else '5 Days'
            inst = med_instructions[i].strip() if i < len(med_instructions) else 'After meals'

            cursor.execute("""
                INSERT INTO prescription_items (prescription_id, medicine_name, dosage, frequency, duration, instructions)
                VALUES (?, ?, ?, ?, ?, ?)
            """, (prescription_id, name, dosage, freq, duration, inst))

    # Patient Notification
    cursor.execute("SELECT user_id FROM patients WHERE id = ?", (patient_id,))
    pat = cursor.fetchone()
    if pat and pat['user_id']:
        cursor.execute("""
            INSERT INTO notifications (user_id, title, message, category)
            VALUES (?, 'Digital Prescription Ready', 'Your electronic prescription ' || ? || ' is available to download.', 'prescription')
        """, (pat['user_id'], prescription_uid))

    db.commit()
    flash(f"Digital Prescription {prescription_uid} generated successfully.", "success")
    return redirect(url_for('prescriptions'))

@app.route('/prescriptions/view/<int:rx_id>')
@login_required
def prescription_view(rx_id):
    db = get_db()
    cursor = db.cursor()

    cursor.execute("SELECT * FROM prescriptions WHERE id = ?", (rx_id,))
    prescription = cursor.fetchone()
    if not prescription:
        flash("Prescription not found.", "danger")
        return redirect(url_for('prescriptions'))

    cursor.execute("SELECT * FROM patients WHERE id = ?", (prescription['patient_id'],))
    patient = cursor.fetchone()

    cursor.execute("SELECT * FROM doctors WHERE id = ?", (prescription['doctor_id'],))
    doctor = cursor.fetchone()

    cursor.execute("SELECT * FROM prescription_items WHERE prescription_id = ?", (rx_id,))
    items = cursor.fetchall()

    return render_template('prescription_view.html', prescription=prescription, patient=patient, doctor=doctor, items=items)

# ----------------- LABORATORY -----------------
@app.route('/laboratory')
def laboratory():
    db = get_db()
    cursor = db.cursor()

    query = """
        SELECT lr.*, lt.test_name, lt.category, lt.normal_range, p.full_name as patient_name, p.patient_uid, d.name as doctor_name
        FROM lab_requests lr
        JOIN lab_tests lt ON lr.test_id = lt.id
        JOIN patients p ON lr.patient_id = p.id
        LEFT JOIN doctors d ON lr.doctor_id = d.id
        WHERE 1=1
    """
    params = []

    if session.get('role') == 'patient':
        cursor.execute("SELECT id FROM patients WHERE user_id = ?", (session['user_id'],))
        pat = cursor.fetchone()
        if pat:
            query += " AND lr.patient_id = ?"
            params.append(pat['id'])

    query += " ORDER BY lr.requested_at DESC"
    cursor.execute(query, params)
    lab_requests = cursor.fetchall()

    cursor.execute("SELECT * FROM lab_tests ORDER BY category, test_name")
    catalog_tests = cursor.fetchall()

    cursor.execute("SELECT id, full_name, patient_uid FROM patients ORDER BY full_name")
    patients = cursor.fetchall()

    return render_template('laboratory.html', lab_requests=lab_requests, catalog_tests=catalog_tests, patients=patients)

@app.route('/laboratory/test/add', methods=['POST'])
@role_required('laboratory', 'admin')
def add_lab_test():
    test_code = request.form.get('test_code', '').strip().upper()
    test_name = request.form.get('test_name', '').strip()
    category = request.form.get('category', 'Blood tests')
    description = request.form.get('description', '').strip()
    price = float(request.form.get('price', 0.0))
    normal_range = request.form.get('normal_range', '').strip()
    units = request.form.get('units', '').strip()

    db = get_db()
    cursor = db.cursor()
    cursor.execute("""
        INSERT INTO lab_tests (test_code, test_name, category, description, price, normal_range, units)
        VALUES (?, ?, ?, ?, ?, ?, ?)
    """, (test_code, test_name, category, description, price, normal_range, units))
    db.commit()
    flash(f"Test {test_name} added to diagnostics catalog.", "success")
    return redirect(request.referrer or url_for('laboratory'))

@app.route('/laboratory/order', methods=['POST'])
@login_required
def order_lab_test():
    patient_id = int(request.form.get('patient_id'))
    test_id = int(request.form.get('test_id'))
    sample_type = request.form.get('sample_type', 'Standard specimen').strip()

    db = get_db()
    cursor = db.cursor()

    doctor_id = None
    if session.get('role') == 'doctor':
        cursor.execute("SELECT id FROM doctors WHERE user_id = ?", (session['user_id'],))
        doc = cursor.fetchone()
        doctor_id = doc['id'] if doc else None

    cursor.execute("SELECT COUNT(*) as count FROM lab_requests")
    count_req = cursor.fetchone()['count'] + 1
    request_uid = f"LAB-REQ-{count_req:04d}"

    cursor.execute("""
        INSERT INTO lab_requests (request_uid, patient_id, doctor_id, test_id, sample_type, status)
        VALUES (?, ?, ?, ?, ?, 'Requested')
    """, (request_uid, patient_id, doctor_id, test_id, sample_type))
    db.commit()

    flash(f"Laboratory order {request_uid} submitted.", "success")
    return redirect(request.referrer or url_for('laboratory'))

@app.route('/laboratory/result/update', methods=['POST'])
@role_required('laboratory', 'admin')
def update_lab_result():
    request_id = int(request.form.get('request_id'))
    status = request.form.get('status', 'Completed')
    test_result = request.form.get('test_result', '').strip()
    reference_range = request.form.get('reference_range', '').strip()
    comments = request.form.get('comments', '').strip()

    db = get_db()
    cursor = db.cursor()

    completed_at = datetime.now().strftime('%Y-%m-%d %H:%M:%S') if status == 'Completed' else None

    cursor.execute("""
        UPDATE lab_requests 
        SET status = ?, test_result = ?, reference_range = ?, comments = ?, completed_at = ?
        WHERE id = ?
    """, (status, test_result, reference_range, comments, completed_at, request_id))

    if status == 'Completed':
        # Notify patient
        cursor.execute("SELECT patient_id, request_uid FROM lab_requests WHERE id = ?", (request_id,))
        req = cursor.fetchone()
        cursor.execute("SELECT user_id FROM patients WHERE id = ?", (req['patient_id'],))
        pat = cursor.fetchone()
        if pat and pat['user_id']:
            cursor.execute("""
                INSERT INTO notifications (user_id, title, message, category)
                VALUES (?, 'Laboratory Report Available', 'Results for diagnostic order ' || ? || ' are now available.', 'lab')
            """, (pat['user_id'], req['request_uid']))

    db.commit()
    flash("Diagnostic test findings recorded successfully.", "success")
    return redirect(request.referrer or url_for('laboratory_dashboard'))

# ----------------- PHARMACY -----------------
@app.route('/pharmacy')
def pharmacy():
    db = get_db()
    cursor = db.cursor()
    cursor.execute("SELECT * FROM medicines ORDER BY name ASC")
    medicines = cursor.fetchall()

    cursor.execute("SELECT * FROM medicines WHERE quantity <= reorder_level")
    low_stock_medicines = cursor.fetchall()

    today_str = date.today().strftime('%Y-%m-%d')
    return render_template('pharmacy.html', medicines=medicines, low_stock_medicines=low_stock_medicines, today_str=today_str)

@app.route('/pharmacy/medicine/add', methods=['POST'])
@role_required('pharmacist', 'admin')
def add_medicine():
    medicine_code = request.form.get('medicine_code', '').strip().upper()
    name = request.form.get('name', '').strip()
    category = request.form.get('category', '').strip()
    manufacturer = request.form.get('manufacturer', '').strip()
    quantity = int(request.form.get('quantity', 0))
    reorder_level = int(request.form.get('reorder_level', 20))
    price = float(request.form.get('price', 0.0))
    expiry_date = request.form.get('expiry_date')
    unit = request.form.get('unit', 'Tablets')
    description = request.form.get('description', '').strip()

    db = get_db()
    cursor = db.cursor()
    cursor.execute("""
        INSERT INTO medicines (medicine_code, name, category, manufacturer, quantity, reorder_level, price, expiry_date, unit, description)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    """, (medicine_code, name, category, manufacturer, quantity, reorder_level, price, expiry_date, unit, description))
    db.commit()

    flash(f"Medicine {name} successfully added to inventory.", "success")
    return redirect(request.referrer or url_for('pharmacy'))

@app.route('/pharmacy/medicine/restock', methods=['POST'])
@role_required('pharmacist', 'admin')
def restock_medicine():
    medicine_id = int(request.form.get('medicine_id'))
    add_qty = int(request.form.get('add_quantity', 0))

    db = get_db()
    cursor = db.cursor()
    cursor.execute("UPDATE medicines SET quantity = quantity + ? WHERE id = ?", (add_qty, medicine_id))
    db.commit()

    flash(f"Successfully restocked {add_qty} units.", "success")
    return redirect(request.referrer or url_for('pharmacist_dashboard'))

# ----------------- BILLING & INVOICING -----------------
@app.route('/billing')
@login_required
def billing():
    db = get_db()
    cursor = db.cursor()

    query = """
        SELECT b.*, p.full_name as patient_name, p.patient_uid
        FROM bills b
        JOIN patients p ON b.patient_id = p.id
        WHERE 1=1
    """
    params = []

    if session.get('role') == 'patient':
        cursor.execute("SELECT id FROM patients WHERE user_id = ?", (session['user_id'],))
        pat = cursor.fetchone()
        if pat:
            query += " AND b.patient_id = ?"
            params.append(pat['id'])

    query += " ORDER BY b.bill_date DESC, b.created_at DESC"
    cursor.execute(query, params)
    bills = cursor.fetchall()

    cursor.execute("SELECT id, full_name, patient_uid FROM patients ORDER BY full_name")
    patients = cursor.fetchall()

    total_billed = sum(b['total_amount'] for b in bills)
    total_paid = sum(b['paid_amount'] for b in bills)
    total_pending = sum(b['total_amount'] - b['paid_amount'] for b in bills if b['payment_status'] != 'Paid')

    return render_template(
        'billing.html',
        bills=bills,
        patients=patients,
        total_billed=total_billed,
        total_paid=total_paid,
        total_pending=total_pending
    )

@app.route('/billing/create', methods=['POST'])
@role_required('admin', 'receptionist', 'pharmacist')
def create_bill():
    patient_id = int(request.form.get('patient_id'))
    consultation_charge = float(request.form.get('consultation_charge', 0.0))
    laboratory_charge = float(request.form.get('laboratory_charge', 0.0))
    medicine_charge = float(request.form.get('medicine_charge', 0.0))
    other_charges = float(request.form.get('other_charges', 0.0))
    discount = float(request.form.get('discount', 0.0))
    tax_percent = float(request.form.get('tax_percent', 5.0))
    payment_status = request.form.get('payment_status', 'Pending')
    payment_method = request.form.get('payment_method', 'Cash')
    notes = request.form.get('notes', '').strip()
    bill_date = date.today().strftime('%Y-%m-%d')

    # Total Calculation
    subtotal = consultation_charge + laboratory_charge + medicine_charge + other_charges
    taxable = max(0.0, subtotal - discount)
    tax_amount = taxable * (tax_percent / 100.0)
    total_amount = round(taxable + tax_amount, 2)
    paid_amount = total_amount if payment_status == 'Paid' else 0.0

    db = get_db()
    cursor = db.cursor()

    cursor.execute("SELECT COUNT(*) as count FROM bills")
    count_inv = cursor.fetchone()['count'] + 1
    bill_uid = f"INV-{date.today().year}-{count_inv:04d}"

    cursor.execute("""
        INSERT INTO bills (bill_uid, patient_id, consultation_charge, laboratory_charge, medicine_charge, other_charges, discount, tax_percent, total_amount, paid_amount, payment_status, payment_method, notes, bill_date)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    """, (bill_uid, patient_id, consultation_charge, laboratory_charge, medicine_charge, other_charges, discount, tax_percent, total_amount, paid_amount, payment_status, payment_method, notes, bill_date))

    # Notify patient
    cursor.execute("SELECT user_id FROM patients WHERE id = ?", (patient_id,))
    pat = cursor.fetchone()
    if pat and pat['user_id']:
        cursor.execute("""
            INSERT INTO notifications (user_id, title, message, category)
            VALUES (?, 'Hospital Invoice Issued', 'Invoice ' || ? || ' for $' || ? || ' has been generated.', 'billing')
        """, (pat['user_id'], bill_uid, total_amount))

    db.commit()
    flash(f"Invoice {bill_uid} for ${total_amount:.2f} created successfully.", "success")
    return redirect(url_for('billing'))

@app.route('/billing/pay/<int:bill_id>', methods=['POST'])
@role_required('admin', 'receptionist')
def pay_bill(bill_id):
    db = get_db()
    cursor = db.cursor()
    cursor.execute("UPDATE bills SET payment_status = 'Paid', paid_amount = total_amount WHERE id = ?", (bill_id,))
    db.commit()
    flash("Payment collected and invoice marked as Paid.", "success")
    return redirect(url_for('billing'))

@app.route('/billing/invoice/<int:bill_id>')
@login_required
def invoice_view(bill_id):
    db = get_db()
    cursor = db.cursor()
    cursor.execute("SELECT * FROM bills WHERE id = ?", (bill_id,))
    bill = cursor.fetchone()
    if not bill:
        flash("Invoice not found.", "danger")
        return redirect(url_for('billing'))

    cursor.execute("SELECT * FROM patients WHERE id = ?", (bill['patient_id'],))
    patient = cursor.fetchone()

    return render_template('invoice_view.html', bill=bill, patient=patient)

# ----------------- DOCTORS, PATIENTS & DEPARTMENTS DIRECTORIES -----------------
@app.route('/doctors')
def doctors():
    db = get_db()
    cursor = db.cursor()
    cursor.execute("""
        SELECT d.*, dept.name as department_name 
        FROM doctors d 
        LEFT JOIN departments dept ON d.department_id = dept.id 
        ORDER BY d.name ASC
    """)
    doctors_list = cursor.fetchall()

    cursor.execute("SELECT * FROM departments WHERE is_active = 1 ORDER BY name ASC")
    departments = cursor.fetchall()

    return render_template('doctors.html', doctors=doctors_list, departments=departments)

@app.route('/doctors/add', methods=['POST'])
@role_required('admin')
def add_doctor():
    name = request.form.get('name', '').strip()
    department_id = int(request.form.get('department_id'))
    specialization = request.form.get('specialization', '').strip()
    qualification = request.form.get('qualification', '').strip()
    experience_years = int(request.form.get('experience_years', 5))
    consultation_fee = float(request.form.get('consultation_fee', 500.0))
    room_no = request.form.get('room_no', 'Room 101').strip()
    available_days = request.form.get('available_days', 'Monday to Friday').strip()
    available_timings = request.form.get('available_timings', '09:00 AM - 02:00 PM').strip()
    phone = request.form.get('phone', '').strip()
    email = request.form.get('email', '').strip().lower()
    password = request.form.get('password', 'doctor123')

    db = get_db()
    cursor = db.cursor()

    username = email.split('@')[0]
    pw_hash = generate_password_hash(password)
    cursor.execute("INSERT INTO users (username, email, password_hash, role) VALUES (?, ?, ?, 'doctor')", (username, email, pw_hash))
    user_id = cursor.lastrowid

    cursor.execute("SELECT COUNT(*) as count FROM doctors")
    doc_seq = cursor.fetchone()['count'] + 1
    doctor_uid = f"DOC-{date.today().year}-{doc_seq:04d}"

    cursor.execute("""
        INSERT INTO doctors (user_id, doctor_uid, department_id, name, specialization, qualification, experience_years, phone, email, consultation_fee, available_days, available_timings, room_no, is_available)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 1)
    """, (user_id, doctor_uid, department_id, name, specialization, qualification, experience_years, phone, email, consultation_fee, available_days, available_timings, room_no))
    db.commit()

    flash(f"Doctor {name} registered with UID {doctor_uid}.", "success")
    return redirect(url_for('doctors'))

@app.route('/patients')
@login_required
def patients():
    db = get_db()
    cursor = db.cursor()
    cursor.execute("SELECT * FROM patients ORDER BY full_name ASC")
    patients_list = cursor.fetchall()
    return render_template('patients.html', patients=patients_list)

@app.route('/departments')
def departments():
    db = get_db()
    cursor = db.cursor()
    cursor.execute("""
        SELECT d.*, (SELECT COUNT(*) FROM doctors WHERE department_id = d.id) as doctor_count
        FROM departments d
        WHERE d.is_active = 1
        ORDER BY d.name ASC
    """)
    departments_list = cursor.fetchall()
    return render_template('departments.html', departments=departments_list)

@app.route('/departments/add', methods=['POST'])
@role_required('admin')
def add_department():
    name = request.form.get('name', '').strip()
    code = request.form.get('code', '').strip().upper()
    head_doctor = request.form.get('head_doctor', '').strip()
    icon = request.form.get('icon', 'fa-hospital-user').strip()
    description = request.form.get('description', '').strip()

    db = get_db()
    cursor = db.cursor()
    cursor.execute("""
        INSERT INTO departments (name, code, description, icon, head_doctor)
        VALUES (?, ?, ?, ?, ?)
    """, (name, code, description, icon, head_doctor))
    db.commit()
    flash(f"Department {name} added.", "success")
    return redirect(url_for('departments'))

@app.route('/departments/edit', methods=['POST'])
@role_required('admin')
def edit_department():
    dept_id = int(request.form.get('dept_id'))
    name = request.form.get('name', '').strip()
    code = request.form.get('code', '').strip().upper()
    head_doctor = request.form.get('head_doctor', '').strip()
    icon = request.form.get('icon', 'fa-hospital-user').strip()
    description = request.form.get('description', '').strip()

    db = get_db()
    cursor = db.cursor()
    cursor.execute("""
        UPDATE departments SET name = ?, code = ?, head_doctor = ?, icon = ?, description = ?
        WHERE id = ?
    """, (name, code, head_doctor, icon, description, dept_id))
    db.commit()
    flash("Department updated successfully.", "success")
    return redirect(url_for('departments'))

@app.route('/departments/delete/<int:dept_id>', methods=['POST'])
@role_required('admin')
def delete_department(dept_id):
    db = get_db()
    cursor = db.cursor()
    cursor.execute("UPDATE departments SET is_active = 0 WHERE id = ?", (dept_id,))
    db.commit()
    flash("Department removed.", "info")
    return redirect(url_for('departments'))

# ----------------- STAFF & HUMAN RESOURCES -----------------
@app.route('/staff')
@role_required('admin')
def staff():
    db = get_db()
    cursor = db.cursor()
    today_str = date.today().strftime('%Y-%m-%d')

    cursor.execute("""
        SELECT e.*, dept.name as department_name, att.status as attendance_today, att.check_in
        FROM employees e
        LEFT JOIN departments dept ON e.department_id = dept.id
        LEFT JOIN attendance att ON e.id = att.employee_id AND att.date = ?
        ORDER BY e.name ASC
    """, (today_str,))
    employees = cursor.fetchall()

    cursor.execute("SELECT * FROM departments WHERE is_active = 1 ORDER BY name ASC")
    departments = cursor.fetchall()

    present_count = sum(1 for e in employees if e['attendance_today'] == 'Present')
    leave_count = sum(1 for e in employees if e['attendance_today'] == 'On Leave')
    total_payroll = sum(e['salary'] for e in employees)

    return render_template(
        'staff.html',
        employees=employees,
        departments=departments,
        present_count=present_count,
        leave_count=leave_count,
        total_payroll=total_payroll
    )

@app.route('/staff/add', methods=['POST'])
@role_required('admin')
def add_employee():
    name = request.form.get('name', '').strip()
    role = request.form.get('role', 'receptionist')
    designation = request.form.get('designation', '').strip()
    department_id = request.form.get('department_id')
    department_id = int(department_id) if department_id else None
    phone = request.form.get('phone', '').strip()
    email = request.form.get('email', '').strip().lower()
    address = request.form.get('address', '').strip()
    salary = float(request.form.get('salary', 35000.0))
    duty_schedule = request.form.get('duty_schedule', 'Morning Shift').strip()
    password = request.form.get('password', 'staff123')
    joining_date = date.today().strftime('%Y-%m-%d')

    db = get_db()
    cursor = db.cursor()

    username = email.split('@')[0]
    pw_hash = generate_password_hash(password)
    cursor.execute("INSERT INTO users (username, email, password_hash, role) VALUES (?, ?, ?, ?)", (username, email, pw_hash, role))
    user_id = cursor.lastrowid

    cursor.execute("SELECT COUNT(*) as count FROM employees")
    emp_seq = cursor.fetchone()['count'] + 1
    employee_uid = f"EMP-{date.today().year}-{emp_seq:04d}"

    cursor.execute("""
        INSERT INTO employees (user_id, employee_uid, name, department_id, role, designation, phone, email, address, joining_date, salary, duty_schedule, status)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 'Active')
    """, (user_id, employee_uid, name, department_id, role, designation, phone, email, address, joining_date, salary, duty_schedule))
    db.commit()

    flash(f"Staff member {name} registered with Employee ID {employee_uid}.", "success")
    return redirect(url_for('staff'))

@app.route('/staff/attendance', methods=['POST'])
@role_required('admin')
def mark_attendance():
    employee_id = int(request.form.get('employee_id'))
    status = request.form.get('status', 'Present')
    check_in = request.form.get('check_in', '08:00 AM')
    check_out = request.form.get('check_out', '04:00 PM')
    notes = request.form.get('notes', '').strip()
    today_str = date.today().strftime('%Y-%m-%d')

    db = get_db()
    cursor = db.cursor()

    cursor.execute("SELECT id FROM attendance WHERE employee_id = ? AND date = ?", (employee_id, today_str))
    existing = cursor.fetchone()

    if existing:
        cursor.execute("""
            UPDATE attendance SET status = ?, check_in = ?, check_out = ?, notes = ?
            WHERE id = ?
        """, (status, check_in, check_out, notes, existing['id']))
    else:
        cursor.execute("""
            INSERT INTO attendance (employee_id, date, status, check_in, check_out, notes)
            VALUES (?, ?, ?, ?, ?, ?)
        """, (employee_id, today_str, status, check_in, check_out, notes))

    db.commit()
    flash("Attendance log updated successfully.", "success")
    return redirect(url_for('staff'))

# ----------------- EMERGENCY & RESUSCITATION -----------------
@app.route('/emergency')
def emergency():
    db = get_db()
    cursor = db.cursor()

    cursor.execute("""
        SELECT e.*, d.name as doctor_name, dept.name as department_name
        FROM emergency_cases e
        LEFT JOIN doctors d ON e.assigned_doctor_id = d.id
        LEFT JOIN departments dept ON e.department_id = dept.id
        ORDER BY CASE e.priority_level WHEN 'Critical' THEN 1 WHEN 'Urgent' THEN 2 ELSE 3 END, e.arrival_time DESC
    """)
    emergencies = cursor.fetchall()

    critical_count = sum(1 for e in emergencies if e['priority_level'] == 'Critical' and e['status'] != 'Discharged')
    urgent_count = sum(1 for e in emergencies if e['priority_level'] == 'Urgent' and e['status'] != 'Discharged')
    semi_urgent_count = sum(1 for e in emergencies if e['priority_level'] == 'Semi-Urgent' and e['status'] != 'Discharged')

    cursor.execute("SELECT id, name, specialization FROM doctors WHERE is_available = 1 ORDER BY name")
    doctors = cursor.fetchall()

    return render_template(
        'emergency.html',
        emergencies=emergencies,
        critical_count=critical_count,
        urgent_count=urgent_count,
        semi_urgent_count=semi_urgent_count,
        doctors=doctors
    )

@app.route('/emergency/add', methods=['POST'])
def add_emergency_case():
    patient_name = request.form.get('patient_name', 'Unknown').strip()
    age = int(request.form.get('age', 30))
    gender = request.form.get('gender', 'Male')
    phone = request.form.get('phone', '').strip()
    condition_description = request.form.get('condition_description', '').strip()
    priority_level = request.form.get('priority_level', 'Critical')
    assigned_doctor_id = request.form.get('assigned_doctor_id')
    assigned_doctor_id = int(assigned_doctor_id) if assigned_doctor_id else None
    status = request.form.get('status', 'In Treatment')
    triage_notes = request.form.get('triage_notes', '').strip()

    db = get_db()
    cursor = db.cursor()

    cursor.execute("SELECT COUNT(*) as count FROM emergency_cases")
    emg_seq = cursor.fetchone()['count'] + 1
    case_uid = f"EMG-{date.today().year}-{emg_seq:04d}"

    cursor.execute("""
        INSERT INTO emergency_cases (case_uid, patient_name, age, gender, phone, condition_description, priority_level, assigned_doctor_id, department_id, status, triage_notes)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, 12, ?, ?)
    """, (case_uid, patient_name, age, gender, phone, condition_description, priority_level, assigned_doctor_id, status, triage_notes))

    # Broadcast emergency notification to admins
    cursor.execute("SELECT id FROM users WHERE role = 'admin'")
    for admin_user in cursor.fetchall():
        cursor.execute("""
            INSERT INTO notifications (user_id, title, message, category)
            VALUES (?, 'EMERGENCY INTAKE: ' || ?, 'New ' || ? || ' case: ' || ? || ' admitted to Trauma Center.', 'emergency')
        """, (admin_user['id'], case_uid, priority_level, patient_name))

    db.commit()
    flash(f"Emergency Case {case_uid} admitted and prioritized as {priority_level}.", "danger")
    return redirect(url_for('emergency'))

@app.route('/emergency/status/<int:case_id>', methods=['POST'])
@login_required
def update_emergency_status(case_id):
    new_status = request.form.get('status')
    db = get_db()
    cursor = db.cursor()
    cursor.execute("UPDATE emergency_cases SET status = ? WHERE id = ?", (new_status, case_id))
    db.commit()
    flash(f"Emergency status updated to {new_status}.", "info")
    return redirect(url_for('emergency'))

# ----------------- REPORTS & CSV DATA EXPORT -----------------
@app.route('/reports')
@role_required('admin')
def reports():
    db = get_db()
    cursor = db.cursor()

    stats = {}
    cursor.execute("SELECT COUNT(*) as count FROM appointments")
    stats['total_appointments'] = cursor.fetchone()['count']

    cursor.execute("SELECT COALESCE(SUM(paid_amount), 0.0) as revenue FROM bills")
    stats['total_revenue'] = cursor.fetchone()['revenue']

    cursor.execute("SELECT COUNT(*) as count FROM lab_requests WHERE status = 'Completed'")
    stats['completed_tests'] = cursor.fetchone()['count']

    cursor.execute("SELECT COUNT(*) as count FROM emergency_cases")
    stats['emergency_cases'] = cursor.fetchone()['count']

    cursor.execute("SELECT COUNT(*) as count FROM medicines")
    stats['total_medicines'] = cursor.fetchone()['count']

    cursor.execute("SELECT COUNT(*) as count FROM medicines WHERE quantity <= reorder_level")
    stats['low_stock_medicines'] = cursor.fetchone()['count']

    cursor.execute("SELECT COALESCE(SUM(quantity * price), 0.0) as val FROM medicines")
    stats['inventory_valuation'] = cursor.fetchone()['val']

    cursor.execute("SELECT COUNT(*) as count FROM employees")
    stats['total_employees'] = cursor.fetchone()['count']

    cursor.execute("SELECT COALESCE(SUM(salary), 0.0) as payroll FROM employees")
    stats['monthly_payroll'] = cursor.fetchone()['payroll']

    cursor.execute("""
        SELECT d.name, d.code, d.head_doctor,
               (SELECT COUNT(*) FROM doctors WHERE department_id = d.id) as doctor_count,
               (SELECT COUNT(*) FROM appointments WHERE department_id = d.id) as appointment_count
        FROM departments d
        WHERE d.is_active = 1
        ORDER BY appointment_count DESC
    """)
    dept_reports = cursor.fetchall()

    return render_template('reports.html', stats=stats, dept_reports=dept_reports)

@app.route('/reports/export/<report_type>')
@role_required('admin')
def export_report_csv(report_type):
    db = get_db()
    cursor = db.cursor()
    output = io.StringIO()
    writer = csv.writer(output)

    if report_type == 'appointments':
        writer.writerow(['Appointment UID', 'Patient Name', 'Doctor Name', 'Department', 'Date', 'Time Slot', 'Status', 'Reason'])
        cursor.execute("""
            SELECT a.appointment_uid, p.full_name, d.name, dept.name as dept_name, a.appointment_date, a.time_slot, a.status, a.reason
            FROM appointments a
            JOIN patients p ON a.patient_id = p.id
            JOIN doctors d ON a.doctor_id = d.id
            LEFT JOIN departments dept ON a.department_id = dept.id
        """)
        for row in cursor.fetchall():
            writer.writerow([row[0], row[1], row[2], row[3], row[4], row[5], row[6], row[7]])
        filename = f"appointments_report_{date.today()}.csv"

    elif report_type == 'billing':
        writer.writerow(['Invoice UID', 'Patient Name', 'Consultation ($)', 'Lab ($)', 'Pharmacy ($)', 'Other ($)', 'Total ($)', 'Paid ($)', 'Status', 'Method', 'Date'])
        cursor.execute("""
            SELECT b.bill_uid, p.full_name, b.consultation_charge, b.laboratory_charge, b.medicine_charge, b.other_charges, b.total_amount, b.paid_amount, b.payment_status, b.payment_method, b.bill_date
            FROM bills b
            JOIN patients p ON b.patient_id = p.id
        """)
        for row in cursor.fetchall():
            writer.writerow([row[0], row[1], row[2], row[3], row[4], row[5], row[6], row[7], row[8], row[9], row[10]])
        filename = f"revenue_billing_report_{date.today()}.csv"

    elif report_type == 'medicines':
        writer.writerow(['Code', 'Name', 'Category', 'Manufacturer', 'Stock', 'Reorder Level', 'Unit Price ($)', 'Expiry Date'])
        cursor.execute("SELECT medicine_code, name, category, manufacturer, quantity, reorder_level, price, expiry_date FROM medicines")
        for row in cursor.fetchall():
            writer.writerow([row[0], row[1], row[2], row[3], row[4], row[5], row[6], row[7]])
        filename = f"pharmacy_inventory_{date.today()}.csv"

    elif report_type == 'employees':
        writer.writerow(['Employee UID', 'Name', 'Role', 'Designation', 'Phone', 'Email', 'Salary ($)', 'Duty Schedule'])
        cursor.execute("SELECT employee_uid, name, role, designation, phone, email, salary, duty_schedule FROM employees")
        for row in cursor.fetchall():
            writer.writerow([row[0], row[1], row[2], row[3], row[4], row[5], row[6], row[7]])
        filename = f"staff_directory_{date.today()}.csv"

    else:
        writer.writerow(['Department', 'Code', 'Head Doctor', 'Doctors Count', 'Appointments Count'])
        cursor.execute("""
            SELECT d.name, d.code, d.head_doctor,
                   (SELECT COUNT(*) FROM doctors WHERE department_id = d.id),
                   (SELECT COUNT(*) FROM appointments WHERE department_id = d.id)
            FROM departments d WHERE d.is_active = 1
        """)
        for row in cursor.fetchall():
            writer.writerow([row[0], row[1], row[2], row[3], row[4]])
        filename = f"departments_report_{date.today()}.csv"

    response = make_response(output.getvalue())
    response.headers['Content-Disposition'] = f'attachment; filename={filename}'
    response.headers['Content-Type'] = 'text/csv; charset=utf-8'
    return response

# ----------------- MAIN RUNNER -----------------
if __name__ == '__main__':
    database.init_db()
    database.seed_db()
    print("Hospital server starting on http://127.0.0.1:5000 ...")
    app.run(debug=True, host='127.0.0.1', port=5000)
