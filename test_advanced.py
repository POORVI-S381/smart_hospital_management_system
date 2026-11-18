import unittest
from datetime import date
from app import app
import database

class AdvancedFunctionalTestCase(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        database.init_db()
        database.seed_db()
        app.config['TESTING'] = True
        cls.client = app.test_client()

    def test_appointment_booking_and_duplicate_prevention(self):
        # 1. Login as patient
        self.client.post('/login', data={'login_id': 'patient@smarthospital.com', 'password': 'patient123'}, follow_redirects=True)

        today_str = date.today().strftime('%Y-%m-%d')
        # 2. Book appointment for Dr. Vance at 11:30 AM
        res = self.client.post('/appointments/book', data={
            'doctor_id': 1,
            'appointment_date': today_str,
            'time_slot': '11:30 AM',
            'reason': 'Cardiac palpitations follow-up'
        }, follow_redirects=True)
        self.assertEqual(res.status_code, 200)
        self.assertIn(b'Appointment booked successfully', res.data)

        # 3. Attempt duplicate booking for same doctor, same date, same time slot
        res_dup = self.client.post('/appointments/book', data={
            'doctor_id': 1,
            'appointment_date': today_str,
            'time_slot': '11:30 AM',
            'reason': 'Duplicate attempt'
        }, follow_redirects=True)
        self.assertEqual(res_dup.status_code, 200)
        self.assertIn(b'Slot Collision', res_dup.data)

    def test_emergency_case_flow(self):
        # Admit acute case
        res = self.client.post('/emergency/add', data={
            'patient_name': 'Carlos Santana',
            'age': 55,
            'gender': 'Male',
            'phone': '+1 (555) 333-8888',
            'condition_description': 'Acute anaphylaxis following bee sting',
            'priority_level': 'Critical',
            'status': 'In Treatment',
            'triage_notes': 'IM Epinephrine 0.5mg administered, high-flow O2'
        }, follow_redirects=True)
        self.assertEqual(res.status_code, 200)
        self.assertIn(b'admitted and prioritized as Critical', res.data)
        self.assertIn(b'Carlos Santana', res.data)

    def test_walkin_registration(self):
        # Login as receptionist
        self.client.get('/logout', follow_redirects=True)
        self.client.post('/login', data={'login_id': 'receptionist@smarthospital.com', 'password': 'recep123'}, follow_redirects=True)

        res = self.client.post('/receptionist/walkin', data={
            'full_name': 'Eleanor Rigby',
            'age': 62,
            'gender': 'Female',
            'phone': '+1 (555) 777-1111',
            'blood_group': 'AB+',
            'doctor_id': 5, # Dr. Michael Chang
            'time_slot': '02:00 PM',
            'reason': 'Severe sore throat and dysphagia'
        }, follow_redirects=True)
        self.assertEqual(res.status_code, 200)
        self.assertIn(b'Walk-in patient registered', res.data)
        self.assertIn(b'Eleanor Rigby', res.data)

    def test_lab_order_and_results(self):
        # Login as lab technician
        self.client.get('/logout', follow_redirects=True)
        self.client.post('/login', data={'login_id': 'labtech@smarthospital.com', 'password': 'lab123'}, follow_redirects=True)

        # Order test for John Doe (id=1)
        res_order = self.client.post('/laboratory/order', data={
            'patient_id': 1,
            'test_id': 3, # Fasting Blood Glucose
            'sample_type': 'Fluoride Oxalate Plasma'
        }, follow_redirects=True)
        self.assertEqual(res_order.status_code, 200)
        self.assertIn(b'submitted', res_order.data)

    def test_prescription_generation(self):
        # Login as Dr. Vance
        self.client.get('/logout', follow_redirects=True)
        self.client.post('/login', data={'login_id': 'robert.vance@smarthospital.com', 'password': 'doctor123'}, follow_redirects=True)

        res = self.client.post('/prescriptions/add', data={
            'patient_id': 1,
            'diagnosis': 'Borderline Sinus Tachycardia',
            'instructions': 'Reduce caffeine intake and hydrate',
            'med_name[]': ['Metoprolol Tartrate 25mg'],
            'med_dosage[]': ['1/2 Tablet'],
            'med_frequency[]': ['Twice daily (BD)'],
            'med_duration[]': ['14 Days'],
            'med_instructions[]': ['After breakfast and dinner']
        }, follow_redirects=True)
        self.assertEqual(res.status_code, 200)
        self.assertIn(b'Digital Prescription', res.data)

    def test_billing_invoice_and_payment(self):
        # Login as admin
        self.client.get('/logout', follow_redirects=True)
        self.client.post('/login', data={'login_id': 'admin', 'password': 'admin123'}, follow_redirects=True)

        # Create Bill
        res = self.client.post('/billing/create', data={
            'patient_id': 1,
            'consultation_charge': '600.00',
            'laboratory_charge': '150.00',
            'medicine_charge': '50.00',
            'other_charges': '25.00',
            'discount': '25.00',
            'tax_percent': '5.0',
            'payment_status': 'Pending',
            'payment_method': 'Cash',
            'notes': 'Cardiology consultation and glucose test'
        }, follow_redirects=True)
        self.assertEqual(res.status_code, 200)
        self.assertIn(b'created successfully', res.data)

if __name__ == '__main__':
    unittest.main()
