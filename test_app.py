import unittest
import os
from app import app
import database

class SmartHospitalTestCase(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        database.init_db()
        database.seed_db()
        app.config['TESTING'] = True
        cls.client = app.test_client()

    def test_01_homepage(self):
        response = self.client.get('/')
        self.assertEqual(response.status_code, 200)
        self.assertIn(b'MedCare', response.data)
        self.assertIn(b'Cardiology', response.data)
        self.assertIn(b'EMERGENCY', response.data)

    def test_02_login_page(self):
        response = self.client.get('/login')
        self.assertEqual(response.status_code, 200)
        self.assertIn(b'Portal Login', response.data)
        self.assertIn(b'Quick Demo Logins', response.data)

    def test_03_admin_login_and_dashboard(self):
        login_res = self.client.post('/login', data={
            'login_id': 'admin@smarthospital.com',
            'password': 'admin123'
        }, follow_redirects=True)
        self.assertEqual(login_res.status_code, 200)
        self.assertIn(b'Hospital Executive Dashboard', login_res.data)
        self.assertIn(b'Total Patients', login_res.data)
        self.assertIn(b'Total Doctors', login_res.data)

    def test_04_doctor_dashboard(self):
        # Login as Dr. Vance
        self.client.get('/logout', follow_redirects=True)
        login_res = self.client.post('/login', data={
            'login_id': 'robert.vance@smarthospital.com',
            'password': 'doctor123'
        }, follow_redirects=True)
        self.assertEqual(login_res.status_code, 200)
        self.assertIn(b'Doctor Workspace', login_res.data)
        self.assertIn(b'Dr. Robert Vance', login_res.data)

    def test_05_patient_dashboard(self):
        # Login as patient John Doe
        self.client.get('/logout', follow_redirects=True)
        login_res = self.client.post('/login', data={
            'login_id': 'patient@smarthospital.com',
            'password': 'patient123'
        }, follow_redirects=True)
        self.assertEqual(login_res.status_code, 200)
        self.assertIn(b'My Health Dashboard', login_res.data)
        self.assertIn(b'John Doe', login_res.data)

    def test_06_receptionist_dashboard(self):
        self.client.get('/logout', follow_redirects=True)
        login_res = self.client.post('/login', data={
            'login_id': 'receptionist@smarthospital.com',
            'password': 'recep123'
        }, follow_redirects=True)
        self.assertEqual(login_res.status_code, 200)
        self.assertIn(b'Front Desk & Reception Station', login_res.data)

    def test_07_nurse_dashboard(self):
        self.client.get('/logout', follow_redirects=True)
        login_res = self.client.post('/login', data={
            'login_id': 'nurse@smarthospital.com',
            'password': 'nurse123'
        }, follow_redirects=True)
        self.assertEqual(login_res.status_code, 200)
        self.assertIn(b'Nursing & OPD Vitals Station', login_res.data)

    def test_08_laboratory_dashboard(self):
        self.client.get('/logout', follow_redirects=True)
        login_res = self.client.post('/login', data={
            'login_id': 'labtech@smarthospital.com',
            'password': 'lab123'
        }, follow_redirects=True)
        self.assertEqual(login_res.status_code, 200)
        self.assertIn(b'Central Diagnostic & Pathology Station', login_res.data)

    def test_09_pharmacist_dashboard(self):
        self.client.get('/logout', follow_redirects=True)
        login_res = self.client.post('/login', data={
            'login_id': 'pharmacist@smarthospital.com',
            'password': 'pharma123'
        }, follow_redirects=True)
        self.assertEqual(login_res.status_code, 200)
        self.assertIn(b'Central Hospital Pharmacy Station', login_res.data)

    def test_10_public_and_core_modules(self):
        # Admin session for full module access
        self.client.get('/logout', follow_redirects=True)
        self.client.post('/login', data={'login_id': 'admin', 'password': 'admin123'}, follow_redirects=True)

        routes = [
            ('/appointments', b'Hospital Appointment Center'),
            ('/doctors', b'Medical Specialists & Physicians'),
            ('/patients', b'Patient Master Directory'),
            ('/departments', b'Clinical & Medical Departments'),
            ('/medical-records', b'Electronic Medical Records'),
            ('/prescriptions', b'Digital Prescriptions Registry'),
            ('/prescriptions/view/1', b'Prescription UID'),
            ('/laboratory', b'Central Laboratory Diagnostics'),
            ('/pharmacy', b'Hospital Pharmacy & Dispensary'),
            ('/billing', b'Patient Billing & Financial Accounts'),
            ('/billing/invoice/1', b'TAX INVOICE'),
            ('/staff', b'Hospital Staff & Duty Rosters'),
            ('/reports', b'Hospital Analytics & Reports Center'),
            ('/live-queue', b'Live OPD Queue & Token Display Board'),
            ('/emergency', b'24/7 Emergency & Critical Care Triage')
        ]

        for route, expected_text in routes:
            with self.subTest(route=route):
                res = self.client.get(route)
                self.assertEqual(res.status_code, 200, f"Route {route} failed with {res.status_code}")
                self.assertIn(expected_text, res.data, f"Text {expected_text} not found in {route}")

    def test_11_csv_export(self):
        self.client.get('/logout', follow_redirects=True)
        self.client.post('/login', data={'login_id': 'admin', 'password': 'admin123'}, follow_redirects=True)
        res = self.client.get('/reports/export/appointments')
        self.assertEqual(res.status_code, 200)
        self.assertEqual(res.headers.get('Content-Type'), 'text/csv; charset=utf-8')
        self.assertIn(b'Appointment UID', res.data)

if __name__ == '__main__':
    unittest.main()
