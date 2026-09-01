export interface UserProfile {
  id: number;
  username: string;
  role: string;
  name: string;
  department?: string;
  employee_id?: string;
  status: string;
  must_change_password?: boolean;
}

export interface Patient {
  id: string;
  name: string;
  age: number;
  dob?: string;
  gender: string;
  blood_group?: string;
  contact_details?: string;
  department: string;
  health_status?: string;
  status: string;
  assigned_doctor?: string;
  assigned_doctor_id?: number;
  admission_date?: string;
  discharge_date?: string;
}

export interface Document {
  id: number;
  name: string;
  status: string;
  approval_status: string;
  version?: string;
  chunk_count: number;
  scope: string;
  patient_id?: string | null;
  uploaded_by?: string;
  uploader_role?: string;
  document_type?: string;
  medical_relevance_score?: number;
  created_at: string;
}

export interface Session {
  id: string;
  title: string;
  created_at: string;
}

export interface Evidence {
  pdf_name: string;
  page_number: number;
  version?: string;
  document_type?: string;
  supporting_text: string;
  response_sentence?: string;
  nli_label?: string;
}

export interface VerificationResult {
  sentence: string;
  status: string;
  nli_label?: string;
  score: number;
  source_sentence?: string;
  pdf_name?: string;
  page_number?: number;
  version?: string;
  explanation?: string;
}

export interface Message {
  id: string;
  role: "user" | "assistant" | string;
  content: string;
  confidence_level?: string;
  confidence_score?: number;
  evidence?: Evidence[];
  verification_results?: VerificationResult[];
  created_at: string;
}

export interface ClinicalReport {
  id: number;
  patient_id: string;
  patient_name?: string;
  doctor_name?: string;
  title: string;
  chief_complaint?: string;
  clinical_history?: string;
  observations?: string;
  investigations?: string;
  clinical_assessment?: string;
  relevant_evidence?: string;
  recommendations?: string;
  sources?: string;
  status: string;
  created_at: string;
  approved_at?: string;
}
