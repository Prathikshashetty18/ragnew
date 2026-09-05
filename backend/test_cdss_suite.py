import os
import sys
import unittest
import uuid
import numpy as np
from datetime import datetime
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session
from pypdf import PdfReader

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from app.main import app
from app.database import (
    get_db, SessionLocal, User, Patient, PatientVitals, 
    LabResult, RadiologyReport, Document, ClinicalReport, ChatSession, ChatMessage
)
from app.auth import create_access_token, hash_password
from app.nli_validator import (
    check_clinical_contradiction, validate_response_with_nli, split_sentences
)
from app.rag_pipeline import (
    get_embedding_model, get_cross_encoder_model, evaluate_evidence_quality_gate,
    synthesize_clinical_answer, query_pipeline, process_pdf
)
from app.config import UPLOAD_DIR

client = TestClient(app)

def create_sample_pdf(filepath: str, title: str, content: str):
    clean_title = title.replace('(', '').replace(')', '')
    clean_content = content.replace('\n', ' ').replace('(', '').replace(')', '')
    stream_content = f'BT /F1 12 Tf 50 750 Td ({clean_title}) Tj 0 -20 Td ({clean_content}) Tj ET'
    stream_bytes = stream_content.encode('latin-1', errors='ignore')
    
    obj1 = b'1 0 obj\n<< /Type /Catalog /Pages 2 0 R >>\nendobj\n'
    obj2 = b'2 0 obj\n<< /Type /Pages /Kids [3 0 R] /Count 1 >>\nendobj\n'
    obj3 = b'3 0 obj\n<< /Type /Page /Parent 2 0 R /MediaBox [0 0 612 792] /Contents 4 0 R /Resources << /Font << /F1 << /Type /Font /Subtype /Type1 /BaseFont /Helvetica >> >> >> >>\nendobj\n'
    obj4_header = f'4 0 obj\n<< /Length {len(stream_bytes)} >>\nstream\n'.encode('latin-1')
    obj4_footer = b'\nendstream\nendobj\n'
    obj4 = obj4_header + stream_bytes + obj4_footer
    
    header = b'%PDF-1.4\n'
    off1 = len(header)
    off2 = off1 + len(obj1)
    off3 = off2 + len(obj2)
    off4 = off3 + len(obj3)
    xref_off = off4 + len(obj4)
    
    xref = f'xref\n0 5\n0000000000 65535 f \n{off1:010d} 00000 n \n{off2:010d} 00000 n \n{off3:010d} 00000 n \n{off4:010d} 00000 n \ntrailer\n<< /Size 5 /Root 1 0 R >>\nstartxref\n{xref_off}\n%%EOF\n'.encode('latin-1')
    
    with open(filepath, 'wb') as f:
        f.write(header + obj1 + obj2 + obj3 + obj4 + xref)

class TestClinicalRAGCDSS(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.db: Session = SessionLocal()
        cls.embedder = get_embedding_model()
        cls.cross_encoder = get_cross_encoder_model()

    @classmethod
    def tearDownClass(cls):
        cls.db.close()

    def get_token(self, username: str) -> str:
        user = self.db.query(User).filter(User.username == username).first()
        self.assertIsNotNone(user, f'User {username} not found in database')
        return create_access_token({'sub': user.username, 'role': user.role, 'name': user.name})

    # ================= 1. AUTHENTICATION & TOKEN TESTS =================
    def test_01_valid_login(self):
        res = client.post('/api/auth/login', json={'username': 'arun', 'password': 'Doctor@123'})
        self.assertEqual(res.status_code, 200)
        data = res.json()
        self.assertIn('access_token', data)
        self.assertEqual(data['user']['role'], 'DOCTOR')

    def test_02_invalid_login(self):
        res = client.post('/api/auth/login', json={'username': 'arun', 'password': 'WrongPassword!'})
        self.assertEqual(res.status_code, 401)

    def test_03_unauthenticated_request_blocked(self):
        res = client.get('/api/patients')
        self.assertEqual(res.status_code, 401)

    def test_04_deactivated_user_blocked(self):
        u = self.db.query(User).filter(User.username == 'inactive_tester').first()
        if not u:
            u = User(
                username='inactive_tester',
                password_hash=hash_password('Test@123'),
                role='DOCTOR',
                name='Inactive Tester',
                status='INACTIVE'
            )
            self.db.add(u)
            self.db.commit()
        else:
            u.status = 'INACTIVE'
            self.db.commit()

        res = client.post('/api/auth/login', json={'username': 'inactive_tester', 'password': 'Test@123'})
        self.assertEqual(res.status_code, 403)
        self.assertIn('deactivated', res.json()['detail'].lower())

    # ================= 2. ROLE-BASED ACCESS CONTROL (RBAC) =================
    def test_05_frontdesk_cannot_approve_reports(self):
        token = self.get_token('frontdesk')
        headers = {'Authorization': f'Bearer {token}'}
        res = client.post('/api/reports/1/approve', headers=headers)
        self.assertEqual(res.status_code, 403)

    def test_06_frontdesk_can_discharge_patient(self):
        token = self.get_token('frontdesk')
        headers = {'Authorization': f'Bearer {token}'}
        res = client.post('/api/patients/PAT-2026-000103/discharge', headers=headers)
        self.assertIn(res.status_code, [200, 400])

    def test_07_radiologist_workspace_access(self):
        token = self.get_token('rahul_rad')
        headers = {'Authorization': f'Bearer {token}'}
        res = client.get('/api/radiology', headers=headers)
        self.assertEqual(res.status_code, 200)
        self.assertIsInstance(res.json(), list)

    def test_08_laboratory_workspace_access(self):
        token = self.get_token('ananya_lab')
        headers = {'Authorization': f'Bearer {token}'}
        res = client.get('/api/laboratory', headers=headers)
        self.assertEqual(res.status_code, 200)
        self.assertIsInstance(res.json(), list)

    # ================= 3. CLAIM-LEVEL NLI GROUNDING UNIT TESTS =================
    def test_09_nli_entailment_supported(self):
        context_chunks = [{
            'text': 'Community-acquired pneumonia first-line outpatient treatment is Amoxicillin 1g orally three times daily for 5 to 7 days.',
            'pdf_name': 'IDSA CAP Guidelines 2026',
            'page_number': 14,
            'scope': 'knowledge_base',
            'document_type': 'Hospital Guideline'
        }]
        answer = 'According to hospital guidelines, the first-line oral regimen for community-acquired pneumonia is Amoxicillin 1g three times daily.'
        res = validate_response_with_nli(answer, context_chunks, self.embedder, self.cross_encoder)
        self.assertGreaterEqual(res['entailment_count'], 1)
        self.assertEqual(res['contradiction_count'], 0)
        self.assertIn(res['confidence_level'], ['Medium', 'High'])

    def test_10_nli_contradiction_detection(self):
        context_chunks = [{
            'text': 'Macrolide monotherapy is strictly contraindicated in patients with severe refractory pneumonia.',
            'pdf_name': 'CAP Treatment Guidelines',
            'page_number': 22,
            'scope': 'knowledge_base',
            'document_type': 'Hospital Guideline'
        }]
        answer = 'Macrolide monotherapy is highly recommended for severe refractory pneumonia.'
        res = validate_response_with_nli(answer, context_chunks, self.embedder, self.cross_encoder)
        self.assertGreaterEqual(res['contradiction_count'], 1)
        self.assertEqual(res['confidence_level'], 'Low')

    def test_11_nli_unsupported_neutral(self):
        context_chunks = [{
            'text': 'Aspirin is prescribed for secondary cardiovascular prevention at 75-100mg daily.',
            'pdf_name': 'Cardiology Guidelines',
            'page_number': 5,
            'scope': 'knowledge_base',
            'document_type': 'Hospital Guideline'
        }]
        answer = 'Aspirin should be given at 500mg intravenously for acute malaria.'
        res = validate_response_with_nli(answer, context_chunks, self.embedder, self.cross_encoder)
        self.assertGreaterEqual(res['neutral_count'], 1)

    # ================= 4. EVIDENCE QUALITY GATE TESTS =================
    def test_12_evidence_quality_gate_blocks_irrelevant_query(self):
        chunks = [{
            'text': 'The standard dosing for metformin in type 2 diabetes starts at 500mg orally once daily with meals.',
            'rerank_score': -8.5,
            'bm25_score': 0.0
        }]
        is_sufficient = evaluate_evidence_quality_gate('Explain quantum mechanical wave functions and string theory', chunks)
        self.assertFalse(is_sufficient, 'Evidence Gate must block irrelevant queries before LLM call')

    def test_13_evidence_quality_gate_passes_relevant_evidence(self):
        chunks = [{
            'text': 'Metformin titration: start 500mg daily with dinner, titrate weekly up to 2000mg daily as tolerated.',
            'rerank_score': 4.2,
            'bm25_score': 8.5
        }]
        is_sufficient = evaluate_evidence_quality_gate('What is the recommended metformin starting dose and titration schedule?', chunks)
        self.assertTrue(is_sufficient)

    # ================= 5. LLM PROVIDER UNAVAILABLE / NO FAKE FALLBACK =================
    def test_14_no_fabricated_clinical_fallback(self):
        orig_groq = os.environ.get('GROQ_API_KEY', '')
        orig_gemini = os.environ.get('GEMINI_API_KEY', '')
        try:
            os.environ['GROQ_API_KEY'] = ''
            os.environ['GEMINI_API_KEY'] = ''
            ans, available = synthesize_clinical_answer('Test Prompt')
            self.assertFalse(available)
            self.assertIn('AI generation is currently unavailable', ans)
        finally:
            if orig_groq: os.environ['GROQ_API_KEY'] = orig_groq
            if orig_gemini: os.environ['GEMINI_API_KEY'] = orig_gemini

    # ================= 6. PATIENT ISOLATION TESTS =================
    def test_15_patient_record_rag_and_isolation(self):
        token = self.get_token('arun')
        headers = {'Authorization': f'Bearer {token}'}

        s_res = client.post('/api/sessions', json={'title': 'Rahul Sharma Consult'}, headers=headers)
        self.assertEqual(s_res.status_code, 200)
        session_id = s_res.json()['id']

        res_a = client.post('/api/ask', json={
            'session_id': session_id,
            'query': 'What were Rahul Sharma previous vitals, lab markers, and chest x-ray findings?',
            'filters': {'scope': 'patient', 'patient_id': 'PAT-2026-000101'}
        }, headers=headers)
        self.assertEqual(res_a.status_code, 200)
        data_a = res_a.json()
        self.assertIn('content', data_a)
        for src in data_a.get('sources', []):
            self.assertIn('Rahul Sharma', src.get('title', ''))

    # ================= 7. SESSION PDF ISOLATION TESTS =================
    def test_16_session_pdf_isolation(self):
        token = self.get_token('arun')
        headers = {'Authorization': f'Bearer {token}'}

        uniq_id = uuid.uuid4().hex[:6]
        pdf_filename = f'test_session_isolated_{uniq_id}.pdf'
        test_pdf = os.path.join(UPLOAD_DIR, pdf_filename)
        create_sample_pdf(
            test_pdf,
            'Special Session Clinical Protocol Alpha',
            'SECTION 1: EXPERIMENTAL PROTOCOL All patients should receive compound XYZ-909 at 25mg IV Q12H. Contraindicated in renal clearance below 30 mL/min.'
        )

        with open(test_pdf, 'rb') as f:
            up_res = client.post('/api/upload', files={'file': (pdf_filename, f, 'application/pdf')}, data={'scope': 'temporary'}, headers=headers)
        self.assertEqual(up_res.status_code, 200)
        doc_id = up_res.json()['document_id']

        process_pdf(
            test_pdf,
            pdf_filename,
            doc_id=doc_id,
            scope='temporary',
            version='1.0',
            document_type='Special Protocol'
        )

        s_res = client.post('/api/sessions', json={'title': 'PDF Chat Session'}, headers=headers)
        session_id = s_res.json()['id']

        q_res = client.post('/api/ask', json={
            'session_id': session_id,
            'query': 'What is the dosage for compound XYZ-909?',
            'filters': {'scope': 'temporary', 'document_id': str(doc_id)}
        }, headers=headers)
        self.assertEqual(q_res.status_code, 200)
        q_data = q_res.json()
        self.assertIn('content', q_data)

        missing_res = client.post('/api/ask', json={
            'session_id': session_id,
            'query': 'What is the flight speed of a peregrine falcon in miles per hour?',
            'filters': {'scope': 'temporary', 'document_id': str(doc_id)}
        }, headers=headers)
        self.assertEqual(missing_res.status_code, 200)
        self.assertIn('couldn\'t find', missing_res.json()['content'].lower())

    # ================= 8. END-TO-END DOCUMENT LIFECYCLE & DATABASE GATE TEST =================
    def test_17_full_document_lifecycle_and_archive_exclusion(self):
        token = self.get_token('admin')
        headers = {'Authorization': f'Bearer {token}'}

        uniq_id = uuid.uuid4().hex[:6]
        pdf_filename = f'hospital_guideline_cardio_{uniq_id}.pdf'
        test_pdf = os.path.join(UPLOAD_DIR, pdf_filename)
        create_sample_pdf(
            test_pdf,
            f'Hospital Guideline for Acute Coronary Syndrome {uniq_id}',
            f'SECTION 1: ACUTE CORONARY SYNDROME PROTOCOL {uniq_id} All suspected NSTEMI patients must immediately receive chewable Aspirin 300mg and sublingual Nitroglycerin 0.4mg unless systolic BP is under 90 mmHg. Follow with Ticagrelor 180mg loading dose.'
        )

        with open(test_pdf, 'rb') as f:
            up_res = client.post('/api/upload', files={'file': (pdf_filename, f, 'application/pdf')}, data={'scope': 'knowledge_base', 'document_type': 'Hospital Guideline'}, headers=headers)
        self.assertEqual(up_res.status_code, 200)
        doc_id = up_res.json()['document_id']

        db_doc = self.db.query(Document).filter(Document.id == doc_id).first()
        self.assertIsNotNone(db_doc)
        self.assertEqual(db_doc.name, pdf_filename)

        appr_res = client.post(f'/api/documents/{doc_id}/approve', headers=headers)
        self.assertEqual(appr_res.status_code, 200)

        process_pdf(
            db_doc.file_path,
            db_doc.name,
            doc_id=db_doc.id,
            scope='knowledge_base',
            version='1.0',
            document_type='Hospital Guideline'
        )

        s_res = client.post('/api/sessions', json={'title': 'Cardiology Query Session'}, headers=headers)
        session_id = s_res.json()['id']

        q_res = client.post('/api/ask', json={
            'session_id': session_id,
            'query': 'What is the initial medication and dosing for suspected NSTEMI acute coronary syndrome according to hospital guideline?',
            'filters': {'scope': 'knowledge_base'}
        }, headers=headers)
        self.assertEqual(q_res.status_code, 200)
        ans_data = q_res.json()
        self.assertIn('content', ans_data)
        doc_ids_in_sources = [s.get('document_id') for s in ans_data.get('sources', [])]
        self.assertIn(str(doc_id), doc_ids_in_sources, 'Uploaded & active document MUST appear in structured sources')

        # Archive document
        arch_res = client.post(f'/api/documents/{doc_id}/archive', headers=headers)
        self.assertEqual(arch_res.status_code, 200)

        # Query again -> Database-Authoritative Gate MUST exclude archived document
        q2_res = client.post('/api/ask', json={
            'session_id': session_id,
            'query': 'What is the initial medication and dosing for suspected NSTEMI acute coronary syndrome according to hospital guideline?',
            'filters': {'scope': 'knowledge_base'}
        }, headers=headers)
        self.assertEqual(q2_res.status_code, 200)
        ans2_data = q2_res.json()
        doc_ids_after_archive = [s.get('document_id') for s in ans2_data.get('sources', [])]
        self.assertNotIn(str(doc_id), doc_ids_after_archive, 'Archived document MUST NOT appear in active RAG sources')

if __name__ == '__main__':
    unittest.main()
