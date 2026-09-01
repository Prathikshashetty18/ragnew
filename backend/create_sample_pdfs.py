import os
from pypdf import PdfWriter, PdfReader
import io

def create_pdf_with_text(output_path, title, pages_text):
    """
    Creates a valid PDF with selectable text pages using pure standard streams.
    """
    writer = PdfWriter()
    
    # We will build simple PDF streams
    # Or use a minimal PDF structure
    for page_num, content in enumerate(pages_text):
        # Format lines for PDF text object
        lines = content.split("\n")
        stream_content = "BT\n/F1 12 Tf\n50 750 Td\n16 TL\n"
        for line in lines:
            # Escape parenthesis
            safe_line = line.replace("\\", "\\\\").replace("(", "\\(").replace(")", "\\)")
            stream_content += f"({safe_line}) '\n"
        stream_content += "ET"
        
        pdf_page_raw = f"""%PDF-1.4
1 0 obj
<< /Type /Catalog /Pages 2 0 R >>
endobj
2 0 obj
<< /Type /Pages /Kids [3 0 R] /Count 1 >>
endobj
3 0 obj
<< /Type /Page /Parent 2 0 R /MediaBox [0 0 612 792] /Contents 4 0 R /Resources << /Font << /F1 5 0 R >> >> >>
endobj
4 0 obj
<< /Length {len(stream_content)} >>
stream
{stream_content}
endstream
endobj
5 0 obj
<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>
endobj
xref
0 6
0000000000 65535 f 
0000000009 00000 n 
0000000058 00000 n 
0000000115 00000 n 
0000000234 00000 n 
0000000300 00000 n 
trailer
<< /Size 6 /Root 1 0 R >>
startxref
380
%%EOF"""
        reader = PdfReader(io.BytesIO(pdf_page_raw.encode("latin-1")))
        writer.add_page(reader.pages[0])
        
    os.makedirs(os.path.dirname(output_path), exist_ok=True)
    with open(output_path, "wb") as f:
        writer.write(f)
    print(f"Created: {output_path}")

def generate_all_samples():
    sample_dir = os.path.join(os.path.dirname(__file__), "sample_demo_files")
    
    # 1. Chest X-Ray Report for Patient P001 (Rahul)
    create_pdf_with_text(
        os.path.join(sample_dir, "Chest_XRay_Report.pdf"),
        "Chest X-Ray Report",
        [
            """DEPARTMENT OF RADIOLOGY & IMAGING
PATIENT ID: P001
PATIENT NAME: Rahul
EXAMINATION: CHEST X-RAY (POSTEROANTERIOR VIEW)
DATE OF EXAMINATION: 2026-08-31
REFERRING PHYSICIAN: Dr. Arun

CLINICAL INDICATION:
45-year-old male presenting with persistent productive cough, fever of 38.2 C, and pleuritic right-sided chest pain for 4 days.

FINDINGS:
1. LUNGS: There is a prominent airspace consolidation with patchy opacity noted in the right lower lobe. Air bronchograms are visualized within the consolidation, indicative of alveolar airspace filling.
2. The left lung field is clear without focal consolidation, pneumothorax, or vascular congestion.
3. PLEURAL SPACES: Minimal right-sided blunting of the costophrenic angle suggesting trace reactive pleural effusion. No pneumothorax detected.
4. CARDIAC & MEDIASTINUM: Cardiothoracic ratio is within normal limits. Mediastinal contours and hila are unremarkable.
5. OSSEOUS STRUCTURES: Bony thorax appears intact with no acute fractures.

IMPRESSION / KEY FINDINGS:
Right lower lobe acute alveolar pneumonia with minimal reactive pleural effusion.
RECOMMENDATION: Clinical correlation and empirical antibiotic therapy as per hospital pneumonia guidelines. Follow-up chest radiograph recommended in 4-6 weeks to ensure complete radiological clearance."""
        ]
    )

    # 2. Blood Report for Patient P001 (Rahul)
    create_pdf_with_text(
        os.path.join(sample_dir, "Blood_Report.pdf"),
        "Hematology & Biochemistry Blood Report",
        [
            """CENTRAL CLINICAL LABORATORY REPORT
PATIENT ID: P001
PATIENT NAME: Rahul
AGE: 45 Years | GENDER: Male
SAMPLE COLLECTED: 2026-08-31 08:30 AM
REPORT STATUS: Finalized

COMPLETE BLOOD COUNT (CBC):
- Hemoglobin (Hb): 10.2 g/dL (Reference: 13.5 - 17.5 g/dL) [LOW - Mild Anemia]
- Total Leukocyte Count (WBC): 14,000 /uL (Reference: 4,500 - 11,000 /uL) [ELEVATED - Leukocytosis]
- Neutrophils: 82% (Reference: 40 - 70%) [ELEVATED - Neutrophilia]
- Lymphocytes: 12% (Reference: 20 - 40%) [LOW]
- Platelet Count: 280,000 /uL (Reference: 150,000 - 450,000 /uL) [NORMAL]

INFLAMMATORY MARKERS & BIOCHEMISTRY:
- C-Reactive Protein (CRP): 48.5 mg/L (Reference: < 5.0 mg/L) [ELEVATED - Significant Acute Phase Response]
- Erythrocyte Sedimentation Rate (ESR): 42 mm/hr (Reference: 0 - 15 mm/hr) [ELEVATED]
- Serum Creatinine: 0.9 mg/dL (Reference: 0.7 - 1.3 mg/dL) [NORMAL]
- Blood Urea Nitrogen (BUN): 16 mg/dL (Reference: 7 - 20 mg/dL) [NORMAL]

LABORATORY INTERPRETATION:
The marked leukocytosis with left shift (neutrophilia) combined with significantly elevated CRP (48.5 mg/L) is strongly indicative of acute bacterial infection or active inflammatory process."""
        ]
    )

    # 3. Diabetes Textbook Chapter (Personal / Temporary PDF Demo)
    create_pdf_with_text(
        os.path.join(sample_dir, "Diabetes_Textbook.pdf"),
        "Clinical Endocrinology: Principles of Diabetes Mellitus",
        [
            """CLINICAL ENDOCRINOLOGY & METABOLISM: COMPREHENSIVE GUIDE
CHAPTER 12: ACUTE AND CHRONIC COMPLICATIONS OF DIABETES MELLITUS

12.1 INTRODUCTION AND PATHOPHYSIOLOGY
Diabetes mellitus represents a group of metabolic disorders characterized by persistent hyperglycemia resulting from defects in insulin secretion, insulin action, or both. Chronic elevation of blood glucose causes progressive microvascular and macrovascular damage across multiple organ systems.

12.2 ACUTE METABOLIC COMPLICATIONS
1. Diabetic Ketoacidosis (DKA): Characterized by absolute insulin deficiency, severe hyperglycemia (>250 mg/dL), metabolic acidosis (pH < 7.30, serum bicarbonate < 18 mEq/L), and elevated serum/urine ketone bodies. Key clinical signs include Kussmaul respirations, dehydration, acetone breath odor, and altered mental status.
2. Hyperosmolar Hyperglycemic State (HHS): Predominantly in Type 2 Diabetes, characterized by extreme hyperglycemia (>600 mg/dL), severe hyperosmolality (>320 mOsm/kg), and profound dehydration without significant ketoacidosis.

12.3 CHRONIC MICROVASCULAR COMPLICATIONS
1. Diabetic Nephropathy: Leading cause of end-stage renal disease (ESRD). Starts with persistent microalbuminuria (urinary albumin excretion 30-300 mg/day) and progresses to overt proteinuria, nodular glomerulosclerosis (Kimmelstiel-Wilson lesions), and declining GFR. First-line renoprotective management includes ACE inhibitors or ARBs.
2. Diabetic Retinopathy: Non-proliferative (microaneurysms, cotton-wool spots) and proliferative (neovascularization leading to vitreous hemorrhage and retinal detachment).
3. Diabetic Neuropathy: Distal symmetrical sensorimotor polyneuropathy (glove-and-stocking distribution), autonomic neuropathy (gastroparesis, postural hypotension, resting tachycardia).

12.4 MACROVASCULAR COMPLICATIONS
Coronary artery disease, cerebrovascular disease (ischemic stroke), and peripheral arterial disease (PAD) leading to diabetic foot ulcers and non-traumatic lower extremity amputations."""
        ]
    )

    # 4. Hospital Guideline for Pneumonia & Respiratory Infections (Knowledge Base)
    create_pdf_with_text(
        os.path.join(sample_dir, "Hospital_Guideline_Pneumonia.pdf"),
        "Hospital Clinical Practice Guideline: Management of Pneumonia",
        [
            """HOSPITAL APPROVED CLINICAL PRACTICE GUIDELINE: RESPIRATORY INFECTIONS
DOCUMENT REF: HCG-RESP-2026-04
APPROVAL COMMITTEE: Clinical Quality & Safety Board

SECTION 1: COMMUNITY-ACQUIRED PNEUMONIA (CAP)
1.1 DIAGNOSTIC CRITERIA:
Diagnosis requires the presence of acute respiratory symptoms (cough, fever, dyspnea, pleuritic chest pain) accompanied by a new focal infiltrate on chest radiography and supported by systemic inflammatory markers (WBC > 11,000/uL or elevated CRP).

1.2 RISK STRATIFICATION (CURB-65 SCORE):
- Confusion (mental status)
- Urea > 7 mmol/L (BUN > 19 mg/dL)
- Respiratory rate >= 30 breaths/min
- Blood pressure (Systolic < 90 mmHg or Diastolic <= 60 mmHg)
- Age >= 65 years
Score 0-1: Low risk (Outpatient management suitable).
Score 2: Moderate risk (Consider short inpatient admission).
Score >= 3: High risk (Urgent inpatient admission, assess for ICU care).

1.3 EMPIRICAL ANTIMICROBIAL THERAPY GUIDELINES:
- Outpatient / Low Risk: Amoxicillin 1g TID orally or Doxycycline 100mg BID.
- Inpatient Non-Severe CAP: Intravenous Beta-lactam (Ceftriaxone 1g-2g daily or Ampicillin-Sulbactam 1.5g Q6H) PLUS Macrolide (Azithromycin 500mg daily) or respiratory fluoroquinolone (Levofloxacin 750mg daily).
- Severe / ICU Admission: Ceftriaxone 2g daily PLUS Azithromycin 500mg IV daily, with MRSA coverage (Vancomycin) if risk factors are present.

1.4 MONITORING AND DISCHARGE CRITERIA:
Afebrile for at least 48 hours, normalized heart rate (<100 bpm), respiratory rate (<24 bpm), oxygen saturation >= 92% on room air, and ability to maintain oral intake."""
        ]
    )

    # 5. Hospital Guideline for Tuberculosis Diagnosis (Knowledge Base)
    create_pdf_with_text(
        os.path.join(sample_dir, "Hospital_Guideline_Tuberculosis.pdf"),
        "Hospital Clinical Practice Guideline: Tuberculosis Screening and Diagnosis",
        [
            """HOSPITAL APPROVED CLINICAL PRACTICE GUIDELINE: TUBERCULOSIS (TB)
DOCUMENT REF: HCG-INF-2026-09
APPROVAL: WHO Aligned Hospital Clinical Standards

SECTION 2: TUBERCULOSIS DIAGNOSTIC PROTOCOL
2.1 CLINICAL SUSPICION:
Suspect active pulmonary tuberculosis in any patient with:
- Persistent unexplained cough lasting >= 2 weeks
- Unexplained weight loss, night sweats, or low-grade evening fever
- Hemoptysis (coughing up blood)
- Chest radiography showing apical or upper lobe cavitary lesions or nodular infiltrates.

2.2 DIAGNOSTIC WORKUP:
1. Sputum Examination: Collect two sputum specimens (one spot, one early morning) for Acid-Fast Bacilli (AFB) Ziehl-Neelsen stain and rapid molecular testing (GeneXpert MTB/RIF).
2. Molecular Testing: GeneXpert MTB/RIF provides simultaneous detection of Mycobacterium tuberculosis and rifampicin resistance within 2 hours.
3. Culture Confirmation: Liquid culture (MGIT) is the gold standard for definitive diagnosis and comprehensive drug-susceptibility testing (DST).

2.3 INFECTION PREVENTION & ISOLATION:
Patients with suspected or confirmed infectious pulmonary TB must be placed in a negative pressure airborne infection isolation room (AIIR) until three consecutive negative sputum smears are obtained."""
        ]
    )

if __name__ == "__main__":
    generate_all_samples()
