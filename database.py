import sqlite3
import os
from datetime import datetime, date, timedelta
from werkzeug.security import generate_password_hash

DB_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'hospital.db')

def get_db():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn

def init_db():
    conn = get_db()
    cursor = conn.cursor()

    # Users Table
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS users (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        username TEXT UNIQUE NOT NULL,
        email TEXT UNIQUE NOT NULL,
        password_hash TEXT NOT NULL,
        role TEXT NOT NULL CHECK(role IN ('admin', 'doctor', 'patient', 'receptionist', 'nurse', 'laboratory', 'pharmacist')),
        status TEXT DEFAULT 'active',
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    )
    """)

    # Patients Table
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS patients (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id INTEGER UNIQUE,
        patient_uid TEXT UNIQUE NOT NULL,
        full_name TEXT NOT NULL,
        dob TEXT,
        age INTEGER,
        gender TEXT,
        phone TEXT,
        email TEXT,
        address TEXT,
        blood_group TEXT,
        emergency_contact TEXT,
        emergency_phone TEXT,
        medical_history_summary TEXT,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY (user_id) REFERENCES users (id) ON DELETE SET NULL
    )
    """)

    # Departments Table
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS departments (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        name TEXT UNIQUE NOT NULL,
        code TEXT UNIQUE NOT NULL,
        description TEXT,
        icon TEXT DEFAULT 'fa-hospital-user',
        head_doctor TEXT,
        is_active INTEGER DEFAULT 1,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    )
    """)

    # Doctors Table
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS doctors (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id INTEGER UNIQUE,
        doctor_uid TEXT UNIQUE NOT NULL,
        department_id INTEGER,
        name TEXT NOT NULL,
        specialization TEXT NOT NULL,
        qualification TEXT,
        experience_years INTEGER DEFAULT 5,
        phone TEXT,
        email TEXT,
        consultation_fee REAL DEFAULT 500.0,
        available_days TEXT DEFAULT 'Monday to Friday',
        available_timings TEXT DEFAULT '09:00 AM - 02:00 PM',
        room_no TEXT DEFAULT 'Room 101',
        profile_image TEXT DEFAULT 'doctor_default.png',
        is_available INTEGER DEFAULT 1,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY (user_id) REFERENCES users (id) ON DELETE SET NULL,
        FOREIGN KEY (department_id) REFERENCES departments (id) ON DELETE SET NULL
    )
    """)

    # Appointments Table
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS appointments (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        appointment_uid TEXT UNIQUE NOT NULL,
        patient_id INTEGER NOT NULL,
        doctor_id INTEGER NOT NULL,
        department_id INTEGER,
        appointment_date TEXT NOT NULL,
        time_slot TEXT NOT NULL,
        reason TEXT,
        status TEXT DEFAULT 'Pending' CHECK(status IN ('Pending', 'Confirmed', 'Completed', 'Cancelled')),
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY (patient_id) REFERENCES patients (id) ON DELETE CASCADE,
        FOREIGN KEY (doctor_id) REFERENCES doctors (id) ON DELETE CASCADE,
        FOREIGN KEY (department_id) REFERENCES departments (id) ON DELETE SET NULL
    )
    """)

    # Tokens / Queue Table
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS tokens (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        token_number TEXT NOT NULL,
        appointment_id INTEGER UNIQUE,
        patient_id INTEGER NOT NULL,
        doctor_id INTEGER NOT NULL,
        queue_date TEXT NOT NULL,
        status TEXT DEFAULT 'Waiting' CHECK(status IN ('Waiting', 'In Consultation', 'Completed', 'Skipped', 'Cancelled')),
        estimated_time_minutes INTEGER DEFAULT 15,
        called_at TIMESTAMP,
        completed_at TIMESTAMP,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY (appointment_id) REFERENCES appointments (id) ON DELETE CASCADE,
        FOREIGN KEY (patient_id) REFERENCES patients (id) ON DELETE CASCADE,
        FOREIGN KEY (doctor_id) REFERENCES doctors (id) ON DELETE CASCADE
    )
    """)

    # Medical Records Table
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS medical_records (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        patient_id INTEGER NOT NULL,
        doctor_id INTEGER NOT NULL,
        visit_date TEXT NOT NULL,
        symptoms TEXT,
        diagnosis TEXT NOT NULL,
        treatment TEXT,
        doctor_notes TEXT,
        bp TEXT,
        pulse TEXT,
        temperature TEXT,
        spo2 TEXT,
        weight TEXT,
        allergies TEXT,
        follow_up_date TEXT,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY (patient_id) REFERENCES patients (id) ON DELETE CASCADE,
        FOREIGN KEY (doctor_id) REFERENCES doctors (id) ON DELETE CASCADE
    )
    """)

    # Prescriptions Table
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS prescriptions (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        prescription_uid TEXT UNIQUE NOT NULL,
        patient_id INTEGER NOT NULL,
        doctor_id INTEGER NOT NULL,
        appointment_id INTEGER,
        diagnosis TEXT NOT NULL,
        instructions TEXT,
        prescription_date TEXT NOT NULL,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY (patient_id) REFERENCES patients (id) ON DELETE CASCADE,
        FOREIGN KEY (doctor_id) REFERENCES doctors (id) ON DELETE CASCADE,
        FOREIGN KEY (appointment_id) REFERENCES appointments (id) ON DELETE SET NULL
    )
    """)

    # Prescription Items Table
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS prescription_items (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        prescription_id INTEGER NOT NULL,
        medicine_name TEXT NOT NULL,
        dosage TEXT NOT NULL,
        frequency TEXT NOT NULL,
        duration TEXT NOT NULL,
        instructions TEXT,
        FOREIGN KEY (prescription_id) REFERENCES prescriptions (id) ON DELETE CASCADE
    )
    """)

    # Laboratory Tests Catalog
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS lab_tests (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        test_code TEXT UNIQUE NOT NULL,
        test_name TEXT NOT NULL,
        category TEXT NOT NULL CHECK(category IN ('Blood tests', 'Urine tests', 'X-ray', 'CT scan', 'MRI', 'Biochemistry', 'Pathology', 'Other')),
        description TEXT,
        price REAL NOT NULL DEFAULT 0.0,
        normal_range TEXT,
        units TEXT,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    )
    """)

    # Laboratory Test Requests / Reports
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS lab_requests (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        request_uid TEXT UNIQUE NOT NULL,
        patient_id INTEGER NOT NULL,
        doctor_id INTEGER,
        test_id INTEGER NOT NULL,
        sample_type TEXT,
        status TEXT DEFAULT 'Requested' CHECK(status IN ('Requested', 'Sample Collected', 'Processing', 'Completed')),
        test_result TEXT,
        reference_range TEXT,
        comments TEXT,
        requested_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        completed_at TIMESTAMP,
        FOREIGN KEY (patient_id) REFERENCES patients (id) ON DELETE CASCADE,
        FOREIGN KEY (doctor_id) REFERENCES doctors (id) ON DELETE SET NULL,
        FOREIGN KEY (test_id) REFERENCES lab_tests (id) ON DELETE CASCADE
    )
    """)

    # Medicines Inventory Table
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS medicines (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        medicine_code TEXT UNIQUE NOT NULL,
        name TEXT NOT NULL,
        category TEXT NOT NULL,
        manufacturer TEXT,
        quantity INTEGER NOT NULL DEFAULT 0,
        reorder_level INTEGER DEFAULT 20,
        price REAL NOT NULL DEFAULT 0.0,
        expiry_date TEXT NOT NULL,
        unit TEXT DEFAULT 'Tablets',
        description TEXT,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    )
    """)

    # Bills / Invoices Table
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS bills (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        bill_uid TEXT UNIQUE NOT NULL,
        patient_id INTEGER NOT NULL,
        appointment_id INTEGER,
        consultation_charge REAL DEFAULT 0.0,
        laboratory_charge REAL DEFAULT 0.0,
        medicine_charge REAL DEFAULT 0.0,
        other_charges REAL DEFAULT 0.0,
        discount REAL DEFAULT 0.0,
        tax_percent REAL DEFAULT 5.0,
        total_amount REAL NOT NULL,
        paid_amount REAL DEFAULT 0.0,
        payment_status TEXT DEFAULT 'Pending' CHECK(payment_status IN ('Pending', 'Partially Paid', 'Paid')),
        payment_method TEXT DEFAULT 'Cash',
        notes TEXT,
        bill_date TEXT NOT NULL,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY (patient_id) REFERENCES patients (id) ON DELETE CASCADE,
        FOREIGN KEY (appointment_id) REFERENCES appointments (id) ON DELETE SET NULL
    )
    """)

    # Employees / Staff Table
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS employees (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id INTEGER UNIQUE,
        employee_uid TEXT UNIQUE NOT NULL,
        name TEXT NOT NULL,
        department_id INTEGER,
        role TEXT NOT NULL,
        designation TEXT NOT NULL,
        phone TEXT,
        email TEXT,
        address TEXT,
        joining_date TEXT,
        salary REAL DEFAULT 35000.0,
        duty_schedule TEXT DEFAULT 'Day Shift (08:00 AM - 04:00 PM)',
        status TEXT DEFAULT 'Active',
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY (user_id) REFERENCES users (id) ON DELETE SET NULL,
        FOREIGN KEY (department_id) REFERENCES departments (id) ON DELETE SET NULL
    )
    """)

    # Staff Attendance Table
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS attendance (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        employee_id INTEGER NOT NULL,
        date TEXT NOT NULL,
        status TEXT DEFAULT 'Present' CHECK(status IN ('Present', 'Absent', 'On Leave', 'Half Day')),
        check_in TEXT,
        check_out TEXT,
        notes TEXT,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY (employee_id) REFERENCES employees (id) ON DELETE CASCADE
    )
    """)

    # Notifications Table
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS notifications (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id INTEGER NOT NULL,
        title TEXT NOT NULL,
        message TEXT NOT NULL,
        category TEXT DEFAULT 'system',
        is_read INTEGER DEFAULT 0,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY (user_id) REFERENCES users (id) ON DELETE CASCADE
    )
    """)

    # Emergency Cases Table
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS emergency_cases (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        case_uid TEXT UNIQUE NOT NULL,
        patient_name TEXT NOT NULL,
        age INTEGER,
        gender TEXT,
        phone TEXT,
        condition_description TEXT NOT NULL,
        priority_level TEXT NOT NULL CHECK(priority_level IN ('Critical', 'Urgent', 'Semi-Urgent')),
        assigned_doctor_id INTEGER,
        department_id INTEGER,
        status TEXT DEFAULT 'Triage' CHECK(status IN ('Triage', 'Stabilizing', 'In Treatment', 'Admitted', 'Discharged')),
        triage_notes TEXT,
        arrival_time TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY (assigned_doctor_id) REFERENCES doctors (id) ON DELETE SET NULL,
        FOREIGN KEY (department_id) REFERENCES departments (id) ON DELETE SET NULL
    )
    """)

    conn.commit()
    conn.close()

def seed_db():
    conn = get_db()
    cursor = conn.cursor()

    # Check if already seeded
    cursor.execute("SELECT COUNT(*) as count FROM users")
    if cursor.fetchone()['count'] > 0:
        conn.close()
        return

    today_str = date.today().strftime('%Y-%m-%d')
    pw_hash = generate_password_hash("admin123")
    doc_hash = generate_password_hash("doctor123")
    pat_hash = generate_password_hash("patient123")
    rec_hash = generate_password_hash("recep123")
    nur_hash = generate_password_hash("nurse123")
    lab_hash = generate_password_hash("lab123")
    phr_hash = generate_password_hash("pharma123")

    # 1. Seed Core Users
    users_data = [
        ('admin', 'admin@smarthospital.com', pw_hash, 'admin'),
        ('dr_robert', 'robert.vance@smarthospital.com', doc_hash, 'doctor'),
        ('dr_sarah', 'sarah.jenkins@smarthospital.com', doc_hash, 'doctor'),
        ('dr_emily', 'emily.watson@smarthospital.com', doc_hash, 'doctor'),
        ('dr_david', 'david.miller@smarthospital.com', doc_hash, 'doctor'),
        ('dr_michael', 'michael.chang@smarthospital.com', doc_hash, 'doctor'),
        ('dr_lisa', 'lisa.ray@smarthospital.com', doc_hash, 'doctor'),
        ('patient_john', 'patient@smarthospital.com', pat_hash, 'patient'),
        ('patient_jane', 'jane@smarthospital.com', pat_hash, 'patient'),
        ('receptionist1', 'receptionist@smarthospital.com', rec_hash, 'receptionist'),
        ('nurse_clara', 'nurse@smarthospital.com', nur_hash, 'nurse'),
        ('labtech_alex', 'labtech@smarthospital.com', lab_hash, 'laboratory'),
        ('pharma_priya', 'pharmacist@smarthospital.com', phr_hash, 'pharmacist')
    ]
    cursor.executemany("INSERT INTO users (username, email, password_hash, role) VALUES (?, ?, ?, ?)", users_data)

    # 2. Seed 12 Hospital Departments
    departments_data = [
        ('General Medicine', 'GMED', 'Comprehensive primary care, chronic illness management, and diagnostic consultation.', 'fa-stethoscope', 'Dr. Michael Chang'),
        ('Cardiology', 'CARD', 'Advanced heart care, ECG, cardiac catheterization, and preventative cardiology.', 'fa-heart-pulse', 'Dr. Robert Vance'),
        ('Neurology', 'NEUR', 'Specialized treatment for brain, spinal cord, nerve disorders, and stroke rehabilitation.', 'fa-brain', 'Dr. Sarah Jenkins'),
        ('Dermatology', 'DERM', 'Clinical, surgical, and cosmetic skin care, allergy testing, and laser therapy.', 'fa-hand-dots', 'Dr. Lisa Ray'),
        ('Orthopedics', 'ORTH', 'Joint replacements, sports injuries, fractures, and spine surgery.', 'fa-bone', 'Dr. David Miller'),
        ('Pediatrics', 'PED', 'Child healthcare, newborn intensive care, vaccinations, and growth monitoring.', 'fa-baby', 'Dr. Emily Watson'),
        ('Gynecology', 'GYN', 'Women health, prenatal care, obstetric delivery, and reproductive wellness.', 'fa-venus', 'Dr. Eleanor Brooks'),
        ('ENT', 'ENT', 'Ear, nose, and throat disorders, audiology services, and endoscopic sinus procedures.', 'fa-head-side-cough', 'Dr. Marcus Webb'),
        ('Ophthalmology', 'OPHTH', 'Eye exams, cataract surgeries, glaucoma management, and vision correction.', 'fa-eye', 'Dr. Rachel Patel'),
        ('Dentistry', 'DENT', 'Dental implants, oral surgery, pediatric dentistry, and cosmetic orthodontics.', 'fa-tooth', 'Dr. Alan Grant'),
        ('Psychiatry', 'PSYC', 'Mental health counseling, clinical psychology, psychotherapy, and psychiatric care.', 'fa-head-side-virus', 'Dr. Maya Lin'),
        ('Emergency Medicine', 'EMERG', '24/7 Level 1 Trauma Care, critical resuscitation, and acute emergency stabilization.', 'fa-truck-medical', 'Dr. James Ford')
    ]
    cursor.executemany("INSERT INTO departments (name, code, description, icon, head_doctor) VALUES (?, ?, ?, ?, ?)", departments_data)

    # 3. Seed Doctors
    doctors_data = [
        (2, 'DOC-2026-0001', 2, 'Dr. Robert Vance', 'Cardiology', 'MD, FACC, Harvard Medical School', 14, '+1 (555) 234-5678', 'robert.vance@smarthospital.com', 850.0, 'Monday, Wednesday, Friday', '09:00 AM - 01:00 PM', 'Room 204', 'doc1.jpg', 1),
        (3, 'DOC-2026-0002', 3, 'Dr. Sarah Jenkins', 'Neurology', 'MD, DM Neurology, Johns Hopkins', 12, '+1 (555) 234-5679', 'sarah.jenkins@smarthospital.com', 900.0, 'Tuesday, Thursday, Saturday', '10:00 AM - 02:00 PM', 'Room 310', 'doc2.jpg', 1),
        (4, 'DOC-2026-0003', 6, 'Dr. Emily Watson', 'Pediatrics', 'MBBS, MD Pediatrics, Stanford Medicine', 10, '+1 (555) 234-5680', 'emily.watson@smarthospital.com', 600.0, 'Monday to Friday', '09:30 AM - 01:30 PM', 'Room 105', 'doc3.jpg', 1),
        (5, 'DOC-2026-0004', 5, 'Dr. David Miller', 'Orthopedics', 'MS Ortho, MCh, Oxford University', 15, '+1 (555) 234-5681', 'david.miller@smarthospital.com', 750.0, 'Monday, Wednesday, Thursday', '02:00 PM - 06:00 PM', 'Room 118', 'doc4.jpg', 1),
        (6, 'DOC-2026-0005', 1, 'Dr. Michael Chang', 'General Medicine', 'MD Internal Medicine, Columbia University', 11, '+1 (555) 234-5682', 'michael.chang@smarthospital.com', 500.0, 'Monday to Saturday', '08:30 AM - 02:30 PM', 'Room 101', 'doc5.jpg', 1),
        (7, 'DOC-2026-0006', 4, 'Dr. Lisa Ray', 'Dermatology', 'MD Dermatology, Mayo Clinic', 8, '+1 (555) 234-5683', 'lisa.ray@smarthospital.com', 650.0, 'Tuesday, Thursday, Friday', '11:00 AM - 04:00 PM', 'Room 215', 'doc6.jpg', 1)
    ]
    cursor.executemany("""
        INSERT INTO doctors (user_id, doctor_uid, department_id, name, specialization, qualification, experience_years, phone, email, consultation_fee, available_days, available_timings, room_no, profile_image, is_available)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    """, doctors_data)

    # 4. Seed Patients
    patients_data = [
        (8, 'PAT-2026-0001', 'John Doe', '1988-06-15', 38, 'Male', '+1 (555) 345-9871', 'patient@smarthospital.com', '742 Evergreen Terrace, Springfield', 'O+', 'Martha Doe (Spouse)', '+1 (555) 345-9872', 'Mild hypertension, penicillin allergy'),
        (9, 'PAT-2026-0002', 'Jane Smith', '1995-11-22', 31, 'Female', '+1 (555) 456-7890', 'jane@smarthospital.com', '124 Conch Street, Pacific City', 'B+', 'Robert Smith (Father)', '+1 (555) 456-7891', 'Seasonal asthma, no known drug allergies')
    ]
    cursor.executemany("""
        INSERT INTO patients (user_id, patient_uid, full_name, dob, age, gender, phone, email, address, blood_group, emergency_contact, emergency_phone, medical_history_summary)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    """, patients_data)

    # 5. Seed Employees / Staff
    employees_data = [
        (10, 'EMP-2026-0001', 'Alice Cooper', 1, 'receptionist', 'Head Receptionist', '+1 (555) 678-0001', 'receptionist@smarthospital.com', '45 Baker St, Metro City', '2022-01-15', 38000.0, 'Morning (07:00 AM - 03:00 PM)', 'Active'),
        (11, 'EMP-2026-0002', 'Clara Barton', 12, 'nurse', 'Senior Critical Care Nurse', '+1 (555) 678-0002', 'nurse@smarthospital.com', '88 Florence Way, Metro City', '2021-06-10', 48000.0, 'Day Shift (08:00 AM - 04:00 PM)', 'Active'),
        (12, 'EMP-2026-0003', 'Alex Morgan', 1, 'laboratory', 'Lead Medical Technologist', '+1 (555) 678-0003', 'labtech@smarthospital.com', '12 Lab Lane, Metro City', '2023-03-01', 52000.0, 'General Shift (09:00 AM - 05:00 PM)', 'Active'),
        (13, 'EMP-2026-0004', 'Priya Sharma', 1, 'pharmacist', 'Chief Clinical Pharmacist', '+1 (555) 678-0004', 'pharmacist@smarthospital.com', '93 Apothecary Blvd, Metro City', '2020-09-18', 55000.0, 'Day Shift (08:30 AM - 04:30 PM)', 'Active')
    ]
    cursor.executemany("""
        INSERT INTO employees (user_id, employee_uid, name, department_id, role, designation, phone, email, address, joining_date, salary, duty_schedule, status)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    """, employees_data)

    # 6. Seed Attendance for today
    attendance_data = [
        (1, today_str, 'Present', '06:55 AM', '03:05 PM', 'On time'),
        (2, today_str, 'Present', '07:50 AM', 'In Progress', 'Assigned to Trauma/ICU triage'),
        (3, today_str, 'Present', '08:45 AM', 'In Progress', 'Operating Hematology analyzer'),
        (4, today_str, 'Present', '08:25 AM', 'In Progress', 'Inventory check completed')
    ]
    cursor.executemany("INSERT INTO attendance (employee_id, date, status, check_in, check_out, notes) VALUES (?, ?, ?, ?, ?, ?)", attendance_data)

    # 7. Seed Lab Tests Catalog
    lab_tests_data = [
        ('LAB-CBC', 'Complete Blood Count (CBC)', 'Blood tests', 'Analyzes red cells, white cells, hemoglobin, and platelets.', 350.0, 'Hb: 13.5-17.5 g/dL, WBC: 4.5-11.0 k/uL, Platelets: 150-450 k/uL', 'cells/mcL'),
        ('LAB-LIPID', 'Comprehensive Lipid Profile', 'Blood tests', 'Assesses Total Cholesterol, HDL, LDL, and Triglycerides.', 600.0, 'Cholesterol: <200 mg/dL, HDL: >40 mg/dL, LDL: <100 mg/dL', 'mg/dL'),
        ('LAB-GLUC', 'Fasting Blood Glucose (FBS)', 'Blood tests', 'Measures baseline glucose levels for diabetes screening.', 150.0, '70 - 99', 'mg/dL'),
        ('LAB-HBA1C', 'Glycated Hemoglobin (HbA1c)', 'Blood tests', 'Three-month average plasma glucose concentration.', 550.0, '< 5.7% (Normal), 5.7-6.4% (Prediabetes)', '%'),
        ('LAB-LFT', 'Liver Function Test (LFT)', 'Biochemistry', 'Measures SGOT, SGPT, Bilirubin, and Albumin for hepatic health.', 700.0, 'SGOT: 8-48 U/L, SGPT: 7-56 U/L, Bilirubin: 0.1-1.2 mg/dL', 'U/L'),
        ('LAB-KFT', 'Kidney Function Test (KFT / RFT)', 'Biochemistry', 'Evaluates serum creatinine, blood urea nitrogen, and electrolytes.', 650.0, 'Creatinine: 0.6-1.2 mg/dL, BUN: 7-20 mg/dL', 'mg/dL'),
        ('LAB-URINE', 'Routine Urine Analysis', 'Urine tests', 'Assesses color, protein, glucose, ketones, and microscopic findings.', 200.0, 'Protein: Nil, Sugar: Nil, Pus cells: 1-2 /HPF', 'Visual/HPF'),
        ('LAB-XRAY-CHEST', 'Chest X-Ray (PA View)', 'X-ray', 'Digital radiological imaging of lungs, heart contour, and ribs.', 500.0, 'Clear lung fields, normal cardiothoracic ratio', 'Digital Image'),
        ('LAB-CT-HEAD', 'CT Scan - Brain / Head', 'CT scan', 'High-resolution computed tomography for cranial assessment.', 2800.0, 'No acute hemorrhage, mass effect, or midline shift', 'Contrast / Non-contrast Scan'),
        ('LAB-MRI-LSPINE', 'MRI - Lumbar Spine', 'MRI', 'Detailed magnetic resonance imaging of discs and spinal cord.', 4500.0, 'Normal disc heights, no significant canal stenosis', 'High Tesla MRI')
    ]
    cursor.executemany("INSERT INTO lab_tests (test_code, test_name, category, description, price, normal_range, units) VALUES (?, ?, ?, ?, ?, ?, ?)", lab_tests_data)

    # 8. Seed Pharmacy Medicines
    medicines_data = [
        ('MED-001', 'Amoxicillin 500mg', 'Antibiotic', 'Pfizer Healthcare', 150, 30, 120.0, '2027-08-30', 'Capsules (Strip of 10)', 'Broad-spectrum penicillin antibiotic'),
        ('MED-002', 'Paracetamol 650mg (Dolo)', 'Antipyretic / Analgesic', 'Micro Labs', 420, 50, 35.0, '2028-02-15', 'Tablets (Strip of 15)', 'For fever and mild to moderate pain relief'),
        ('MED-003', 'Atorvastatin 20mg', 'Cardiovascular', 'Sun Pharma', 85, 25, 180.0, '2027-11-20', 'Tablets (Strip of 10)', 'Cholesterol-lowering statin medication'),
        ('MED-004', 'Metformin 500mg ER', 'Antidiabetic', 'Cipla Ltd', 210, 40, 65.0, '2027-12-05', 'Tablets (Strip of 20)', 'First-line medication for type 2 diabetes'),
        ('MED-005', 'Azithromycin 500mg', 'Antibiotic', 'Zydus Lifesciences', 60, 20, 135.0, '2027-04-18', 'Tablets (Strip of 5)', 'Macrolide antibiotic for respiratory tract infections'),
        ('MED-006', 'Omeprazole 20mg', 'Gastrointestinal', 'Dr. Reddys', 180, 35, 75.0, '2027-10-12', 'Capsules (Strip of 15)', 'Proton pump inhibitor for acidity and GERD'),
        ('MED-007', 'Cetirizine 10mg', 'Antihistamine', 'Torrent Pharma', 300, 40, 28.0, '2028-01-25', 'Tablets (Strip of 10)', 'Relief from allergic rhinitis and skin allergies'),
        ('MED-008', 'Ibuprofen 400mg', 'NSAID / Painkiller', 'Abbott Healthcare', 14, 25, 45.0, '2026-12-31', 'Tablets (Strip of 10)', 'Anti-inflammatory and analgesic (Low Stock Alert)'),
        ('MED-009', 'Salbutamol Inhaler 100mcg', 'Respiratory', 'GlaxoSmithKline', 45, 15, 220.0, '2027-06-30', 'Metered Dose Inhaler', 'Bronchodilator for acute asthma relief'),
        ('MED-010', 'Losartan Potassium 50mg', 'Antihypertensive', 'Lupin Pharma', 90, 20, 110.0, '2027-09-15', 'Tablets (Strip of 14)', 'Angiotensin receptor blocker for blood pressure')
    ]
    cursor.executemany("""
        INSERT INTO medicines (medicine_code, name, category, manufacturer, quantity, reorder_level, price, expiry_date, unit, description)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    """, medicines_data)

    # 9. Seed Appointments & Queue Tokens
    appointments_data = [
        ('APT-2026-0001', 1, 1, 2, today_str, '09:30 AM', 'Routine cardiac evaluation and ECG follow-up', 'Confirmed'),
        ('APT-2026-0002', 2, 5, 1, today_str, '10:00 AM', 'Persistent seasonal cough and low-grade fatigue', 'Confirmed'),
        ('APT-2026-0003', 1, 2, 3, (date.today() + timedelta(days=2)).strftime('%Y-%m-%d'), '10:30 AM', 'Frequent tension headaches and sleep disturbance', 'Pending'),
        ('APT-2026-0004', 2, 4, 5, (date.today() + timedelta(days=4)).strftime('%Y-%m-%d'), '02:30 PM', 'Right knee pain after light jogging', 'Pending')
    ]
    cursor.executemany("""
        INSERT INTO appointments (appointment_uid, patient_id, doctor_id, department_id, appointment_date, time_slot, reason, status)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
    """, appointments_data)

    # Tokens for today's appointments
    tokens_data = [
        ('TKN-101', 1, 1, 1, today_str, 'In Consultation', 0, datetime.now().strftime('%Y-%m-%d %H:%M:%S'), None),
        ('TKN-102', 2, 2, 5, today_str, 'Waiting', 15, None, None)
    ]
    cursor.executemany("""
        INSERT INTO tokens (token_number, appointment_id, patient_id, doctor_id, queue_date, status, estimated_time_minutes, called_at, completed_at)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
    """, tokens_data)

    # 10. Seed Medical Records
    records_data = [
        (1, 1, '2026-10-12', 'Mild chest tightness on brisk climbing, slight palpitation', 'Early Stage Essential Hypertension', 'Prescribed lifestyle modification, reduced salt diet, Losartan 50mg daily', 'Patient advised to log daily BP readings and return for follow-up.', '138/88 mmHg', '76 bpm', '98.4 F', '99%', '78 kg', 'Penicillin', (date.today() + timedelta(days=14)).strftime('%Y-%m-%d')),
        (2, 5, '2026-11-02', 'Allergic rhinitis symptoms, runny nose, nocturnal coughing', 'Allergic Bronchitis with Mild Bronchospasm', 'Steam inhalation twice daily, Cetirizine 10mg at bedtime, Salbutamol SOS', 'Advised to avoid cold beverages and dust exposure.', '118/74 mmHg', '72 bpm', '98.6 F', '98%', '58 kg', 'Dust, Pollen', (date.today() + timedelta(days=20)).strftime('%Y-%m-%d'))
    ]
    cursor.executemany("""
        INSERT INTO medical_records (patient_id, doctor_id, visit_date, symptoms, diagnosis, treatment, doctor_notes, bp, pulse, temperature, spo2, weight, allergies, follow_up_date)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    """, records_data)

    # 11. Seed Digital Prescription & Items
    cursor.execute("""
        INSERT INTO prescriptions (prescription_uid, patient_id, doctor_id, appointment_id, diagnosis, instructions, prescription_date)
        VALUES ('RX-2026-0001', 1, 1, 1, 'Essential Hypertension & Mild Hypercholesterolemia', 'Take medications strictly after meals. Low sodium diet and 30 minutes brisk walking daily.', ?)
    """, (today_str,))
    rx_id = cursor.lastrowid

    rx_items_data = [
        (rx_id, 'Losartan Potassium 50mg', '1 Tablet', 'Once daily (Morning)', '30 Days', 'After breakfast with water'),
        (rx_id, 'Atorvastatin 20mg', '1 Tablet', 'Once daily (Night)', '30 Days', 'At bedtime after food')
    ]
    cursor.executemany("""
        INSERT INTO prescription_items (prescription_id, medicine_name, dosage, frequency, duration, instructions)
        VALUES (?, ?, ?, ?, ?, ?)
    """, rx_items_data)

    # 12. Seed Lab Requests
    lab_requests_data = [
        ('LAB-REQ-0001', 1, 1, 2, 'Venous Blood', 'Completed', 'Total Cholesterol: 228 mg/dL, HDL: 44 mg/dL, LDL: 148 mg/dL, Triglycerides: 180 mg/dL', 'Normal: Total <200 mg/dL, LDL <100 mg/dL', 'Borderline elevated cholesterol; statin therapy initiated.', datetime.now().strftime('%Y-%m-%d %H:%M:%S'), datetime.now().strftime('%Y-%m-%d %H:%M:%S')),
        ('LAB-REQ-0002', 1, 1, 1, 'Whole Blood EDTA', 'Completed', 'Hemoglobin: 14.8 g/dL, WBC: 6,800 /mcL, Platelets: 260,000 /mcL', 'Hb: 13.5-17.5 g/dL, WBC: 4.5-11.0 k/uL', 'Hematological parameters well within normal physiological limits.', datetime.now().strftime('%Y-%m-%d %H:%M:%S'), datetime.now().strftime('%Y-%m-%d %H:%M:%S')),
        ('LAB-REQ-0003', 2, 5, 8, 'Chest Imaging', 'Processing', 'Imaging in progress in Radiology Unit 2', 'Clear lung fields', 'Screening for any infiltrates or bronchiectasis', datetime.now().strftime('%Y-%m-%d %H:%M:%S'), None)
    ]
    cursor.executemany("""
        INSERT INTO lab_requests (request_uid, patient_id, doctor_id, test_id, sample_type, status, test_result, reference_range, comments, requested_at, completed_at)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    """, lab_requests_data)

    # 13. Seed Bills
    bills_data = [
        ('INV-2026-0001', 1, 1, 850.0, 950.0, 290.0, 50.0, 50.0, 5.0, 2194.50, 2194.50, 'Paid', 'Card', 'Comprehensive cardiac consultation, CBC, and Lipid Panel', today_str),
        ('INV-2026-0002', 2, 2, 500.0, 500.0, 0.0, 0.0, 0.0, 5.0, 1050.00, 0.0, 'Pending', 'Cash', 'General consultation and pending Chest X-Ray', today_str)
    ]
    cursor.executemany("""
        INSERT INTO bills (bill_uid, patient_id, appointment_id, consultation_charge, laboratory_charge, medicine_charge, other_charges, discount, tax_percent, total_amount, paid_amount, payment_status, payment_method, notes, bill_date)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    """, bills_data)

    # 14. Seed Emergency Cases
    emergency_data = [
        ('EMG-2026-0001', 'Arthur Dent', 42, 'Male', '+1 (555) 998-1212', 'Acute severe retrosternal chest pain radiating to left arm with diaphoresis', 'Critical', 1, 2, 'In Treatment', 'Administered sublingual nitroglycerin, 12-lead ECG showed STEMI in V1-V4. Cath lab on alert.', datetime.now().strftime('%Y-%m-%d %H:%M:%S')),
        ('EMG-2026-0002', 'Sophia Martinez', 19, 'Female', '+1 (555) 887-2345', 'Road traffic collision; suspected closed fracture of right clavicle and superficial contusions', 'Urgent', 4, 5, 'Stabilizing', 'IV analgesia administered. Upper extremity splint applied. Orthopedic surgeon on call.', datetime.now().strftime('%Y-%m-%d %H:%M:%S')),
        ('EMG-2026-0003', 'Liam Johnson', 8, 'Male', '+1 (555) 776-3456', 'High grade fever (103.5 F) with dehydration and vomiting', 'Semi-Urgent', 3, 6, 'Triage', 'Pediatric triage nurse evaluating vitals; oral rehydration started.', datetime.now().strftime('%Y-%m-%d %H:%M:%S'))
    ]
    cursor.executemany("""
        INSERT INTO emergency_cases (case_uid, patient_name, age, gender, phone, condition_description, priority_level, assigned_doctor_id, department_id, status, triage_notes, arrival_time)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    """, emergency_data)

    # 15. Seed Notifications
    notifications_data = [
        (8, 'Appointment Confirmed', 'Your appointment with Dr. Robert Vance is confirmed for today at 09:30 AM.', 'appointment', 0),
        (8, 'Live Queue Token Issued', 'Your token number is TKN-101. Dr. Vance will see you in Room 204.', 'queue', 0),
        (8, 'Lab Report Ready', 'Your Lipid Profile and Complete Blood Count results are now available to view.', 'lab', 0),
        (8, 'Digital Prescription Ready', 'Dr. Vance has issued your digital prescription RX-2026-0001.', 'prescription', 0),
        (1, 'New Emergency Patient Admitted', 'Critical case EMG-2026-0001 admitted to Trauma bay with acute chest pain.', 'emergency', 0),
        (2, 'Upcoming Patient Appointment', 'Patient John Doe is currently in the queue with Token TKN-101.', 'queue', 0)
    ]
    cursor.executemany("""
        INSERT INTO notifications (user_id, title, message, category, is_read)
        VALUES (?, ?, ?, ?, ?)
    """, notifications_data)

    conn.commit()
    conn.close()

if __name__ == '__main__':
    init_db()
    seed_db()
    print("Database initialized and seeded successfully.")
