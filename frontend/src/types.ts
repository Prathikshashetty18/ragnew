export type UserRole =
  | "ADMIN"
  | "DOCTOR"
  | "INTERN"
  | "NURSE"
  | "RADIOLOGIST"
  | "LABORATORY_TECHNICIAN"
  | "FRONT_DESK"
  | "OTHER_STAFF";

export interface User {
  id: number;
  username: string;
  name: string;
  role: UserRole;
  department?: string;
  employee_id?: string;
  email?: string;
  status: "ACTIVE" | "INACTIVE";
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
  health_status: string;
  status: "ACTIVE" | "DISCHARGED" | "ARCHIVED" | "DELETED";
  assigned_doctor?: string;
  assigned_doctor_id?: number;
  admission_date?: string;
  discharge_date?: string;
}

export interface PatientVitals {
  id: number;
  blood_pressure?: string;
  pulse?: number;
  respiratory_rate?: number;
  temperature?: number;
  spo2?: number;
  blood_glucose?: number;
  pain_score?: number;
  intake_output?: string;
  notes?: string;
  recorded_by?: string;
  timestamp: string;
}

export interface LabResult {
  id: number;
  patient_id?: string;
  patient_name?: string;
  hemoglobin?: number;
  wbc?: number;
  crp?: string;
  platelets?: number;
  notes?: string;
  recorded_by?: string;
  technician_name?: string;
  timestamp: string;
}

export interface RadiologyRecord {
  id: number;
  patient_id: string;
  patient_name?: string;
  modality: string;
  findings: string;
  impression?: string;
  image_path?: string;
  document_id?: number;
  status: string;
  radiologist_name?: string;
  timestamp: string;
}

export interface ClinicalNote {
  id: number;
  notes: string;
  author?: string;
  timestamp: string;
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
  status: "AI-GENERATED DRAFT" | "APPROVED" | "ARCHIVED";
  created_at: string;
  approved_at?: string;
}

export interface SourceCard {
  document_id: string;
  citation_id?: number;
  title: string;
  type?: string;
  page?: number;
  section?: string;
  subsection?: string;
  relevance: number;
  view_url?: string;
  supporting_text?: string;
}

export interface ChatMessage {
  id: string;
  role: "user" | "assistant";
  content: string;
  mode?: "strict_rag" | "direct_llm";
  confidence_level?: string;
  confidence_score?: number;
  sources?: SourceCard[];
  evidence?: any[];
  verification_results?: any[];
  created_at?: string;
}

export interface ChatSession {
  id: string;
  title: string;
  patient_id?: string;
  created_at: string;
}

export interface DocumentItem {
  id: number;
  name: string;
  status: string;
  approval_status: "PENDING" | "APPROVED" | "ACTIVE" | "FLAGGED" | "ARCHIVED" | "DELETED";
  version: string;
  chunk_count: number;
  scope: string;
  patient_id?: string;
  uploaded_by?: string;
  uploader_role?: string;
  document_type?: string;
  medical_relevance_score?: number;
  created_at: string;
}

export interface AuditLogItem {
  id: number;
  user_id?: number;
  user_name?: string;
  user_role?: string;
  action: string;
  resource_type: string;
  resource_id?: string;
  status: string;
  details?: string;
  timestamp: string;
}
