# MedCare+ | Smart Hospital Management System

A modern, responsive, role-based, and fully functional web application designed for comprehensive hospital management and clinical workflow automation.

Built with **Python Flask**, **SQLite**, **Bootstrap 5**, **Font Awesome**, and **Chart.js**.

---

## 🌟 Key Features & Functional Modules

1. **Welcome & Landing Page**
   - High-impact hospital landing portal with medical departments, specialist directories, 24/7 emergency hotline bar, hospital facilities, patient testimonials, and instant appointment booking.
2. **Multi-Role Authentication & Security**
   - Secure password hashing using PBKDF2/SHA256 (`werkzeug.security`).
   - Role-Based Access Control (RBAC) with dedicated dashboards for **7 hospital roles**:
     - 🛡️ **Hospital Administrator**
     - 👨‍⚕️ **Doctor / Physician**
     - 🏥 **Patient**
     - 🎧 **Receptionist (Front Desk)**
     - 👩‍⚕️ **Clinical Nurse (Vitals & Triage)**
     - 🔬 **Laboratory Technologist**
     - 💊 **Clinical Pharmacist**
   - Quick Demo Login switchers for instant role testing.
   - Show/hide password, session management, and password recovery.
3. **Patient Portal & Registration**
   - Self-registration with auto-generated unique Patient IDs (e.g., `PAT-2026-0001`).
   - Personal health profile, appointment history, active token queue status, digital prescriptions, lab results, and billing invoices.
4. **Physician / Doctor Workspace**
   - Consultation room queue with live patient call-in button.
   - Duty availability toggle (On Duty / Paused).
   - Electronic Medical Records (EMR) with vital signs logging (BP, Pulse, Temp, SpO2, Weight, Allergies).
   - Multi-item digital prescriptions with dosages, frequencies, and instructions.
5. **Smart Token & Live Queue Management**
   - Automated token numbers (e.g., `TKN-101`, `TKN-102`).
   - Real-time waiting time estimation based on queue density.
   - Dedicated **Live Public Display Board** (`/live-queue`) showing active doctor consultation rooms, next in line, and queue counters.
   - Token status progression: *Waiting* ➔ *In Consultation* ➔ *Completed* / *Skipped*.
6. **Double-Booking Prevention**
   - Collision validation prevents two patients from booking the same doctor for the same time slot on the same day.
7. **24/7 Emergency & Critical Care Triage**
   - Rapid emergency intake with color-coded triage priorities: **Critical**, **Urgent**, and **Semi-Urgent**.
   - Immediate attending doctor assignment and resuscitation status updates.
8. **Automated Laboratory Diagnostics**
   - Test catalog across Blood, Urine, X-Ray, CT Scan, MRI, Biochemistry, and Pathology.
   - Specimen tracking (*Requested* ➔ *Sample Collected* ➔ *Processing* ➔ *Completed*).
   - Quantitative result entry, physiological reference ranges, and pathologist comments.
9. **Central Pharmacy & Dispensary**
   - Barcode inventory management, stock threshold monitoring, and automatic low-stock alerts.
   - Batch restock modal and inventory valuation calculations.
10. **Billing, Invoicing & Tax Calculations**
    - Itemized charges for doctor consultations, laboratory diagnostics, pharmacy medicines, and facility fees.
    - Automatic subtotal, discount, and hospital tax calculation.
    - Settlement tracking: *Paid*, *Pending*, *Partially Paid*.
    - **Print / Download PDF Invoices** with `@media print` styling.
11. **Interactive AI Hospital Assistant (SmartBot)**
    - Floating AI healthcare assistant widget on every page.
    - Recommends the appropriate medical department and physician based on patient-described symptoms.
    - Answers FAQ queries on OPD timings, visiting hours, emergency hotlines, and appointment procedures.
    - Includes medical disclaimer regarding clinical diagnosis.
12. **Analytics & Reports Center**
    - Chart.js visualizations: Weekly appointment flow, department distributions, monthly outpatients, and revenue trajectories.
    - **One-click CSV Exports** for appointments, billing, pharmacy stock, and staff registers.

---

## 🔑 Pre-Configured Demo Accounts

All accounts are pre-seeded in the SQLite database and can be tested immediately:

| Role | Username / Email | Password | Access Highlights |
| :--- | :--- | :--- | :--- |
| **Admin** | `admin@smarthospital.com` | `admin123` | Executive dashboard, analytics, staff, departments, revenue |
| **Doctor** | `robert.vance@smarthospital.com` | `doctor123` | Consultation queue, EMR diagnosis, digital prescriptions |
| **Doctor** | `sarah.jenkins@smarthospital.com` | `doctor123` | Neurology OPD, patient history, active tokens |
| **Patient** | `patient@smarthospital.com` | `patient123` | Appointments, live tokens, prescription PDF, lab reports, bills |
| **Patient** | `jane@smarthospital.com` | `patient123` | Asthma history, ER follow-ups, invoices |
| **Receptionist** | `receptionist@smarthospital.com` | `recep123` | Walk-in registration, token issuance, emergency desk |
| **Nurse** | `nurse@smarthospital.com` | `nurse123` | Vitals logging (BP, Pulse, Temp, SpO2), queue triage |
| **Laboratory** | `labtech@smarthospital.com` | `lab123` | Test requests, sample processing, diagnostic results entry |
| **Pharmacist** | `pharmacist@smarthospital.com` | `pharma123` | Medicine inventory, restock alerts, prescription dispensing |

---

## 🛠️ Technology Stack

- **Backend**: Python 3.12+, Flask 3.1+
- **Database**: SQLite3 (`hospital.db`) with foreign key constraints
- **Frontend**: HTML5, Modern CSS3, JavaScript (ES6)
- **UI Framework**: Bootstrap 5.3.3
- **Icons**: Font Awesome 6.5.2
- **Data Visualizations**: Chart.js 4.4+
- **Security**: Werkzeug PBKDF2 Password Hashing, Session Protection, Input Validation

---

## 🚀 How to Run Locally

### 1. Navigate to the project directory
```bash
cd "C:\Users\POORVI S\.gemini\antigravity\scratch\smart_hospital"
```

### 2. Install requirements
```bash
pip install -r requirements.txt
```

### 3. Initialize and seed the database (if not already initialized)
```bash
python database.py
```

### 4. Run the application
```bash
python app.py
```

### 5. Access the application in your browser
Open your web browser and navigate to:
```
http://127.0.0.1:5000
```

---

## 🧪 Running the Automated Test Suite

To verify all 17 unit and functional tests across all 7 user roles:
```bash
python test_app.py
python test_advanced.py
```
