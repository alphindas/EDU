export type Role = "superadmin" | "admin" | "teacher" | "student" | "parent";
export type Lang = "en" | "te" | "hi";

export interface SchoolBrief { id: number; name: string; code: string; default_language: Lang; logo_url: string }
export interface User {
  id: number; role: Role; login_id: string; full_name: string; phone: string; email: string; language: Lang;
  school_id: number | null; must_change_password: boolean; school: SchoolBrief | null;
  student_id: number | null; teacher_id: number | null; parent_id: number | null;
}
export interface TokenOut { access_token: string; refresh_token: string; must_change_password: boolean; user: User }
export interface Page<T> { items: T[]; total: number; limit: number; offset: number }

export interface SchoolClass { id: number; name: string; sort_order: number }
export interface Section { id: number; class_id: number; name: string; class_teacher_id: number | null }
export interface Subject { id: number; name: string; code: string }
export interface Assignment { id: number; teacher_id: number; section_id: number; subject_id: number }
export interface Teacher {
  id: number; employee_id: string; full_name: string; phone: string; email: string; qualification: string;
  joining_date: string | null; photo_url: string; is_active: boolean; temp_password?: string | null;
}
export interface Student {
  id: number; admission_no: string; full_name: string; class_id: number; section_id: number; roll_no: number | null;
  dob: string; gender: string; photo_url: string; parent_mobile: string; address: string; language: Lang;
  category: string; medical_notes: string; temp_password?: string | null;
}
export interface Parent {
  id: number; full_name: string; mobile: string; relation: string; language: Lang; alert_channels: string[];
  emergency_contact: string; children: Student[];
}

// ---------------------------------------------------------------- Phase 2
export type AttStatus = "present" | "absent" | "late";
export interface SheetRow { student_id: number; admission_no: string; full_name: string; roll_no: number | null; status: AttStatus | null; note: string }
export interface Sheet { section_id: number; date: string; period: number; exists: boolean; source: string | null; rows: SheetRow[] }
export interface AttRecordIn { student_id: number; status: AttStatus; note?: string; confidence?: number | null }
export interface SummaryRow { section_id: number; total: number; marked: boolean; present: number; absent: number; late: number }
export interface HistoryOut { student_id: number; items: { date: string; period: number; status: AttStatus; note: string }[]; present: number; absent: number; late: number; percentage: number | null }
export interface FaceRow { student_id: number; admission_no: string; full_name: string; status: AttStatus; confidence: number | null; time: string | null }
export interface FaceStatus { running: boolean; demo: boolean; period: number; section_id: number; total: number; detected: FaceRow[]; unmatched: number }
export interface FaceStop { section_id: number; period: number; proposal: AttRecordIn[]; unmatched: number }

export interface Period { id: number; number: number; label: string; start_time: string; end_time: string; is_break: boolean }
export interface TtEntry { id: number; section_id: number; day: number; period_id: number; subject_id: number; teacher_id: number | null; room: string }
export interface TtUpload { id: number; section_id: number; kind: "image" | "text"; text: string; content_type: string; original_name: string; uploaded_by: number | null; created_at: string }
export interface Timetable { section_id: number; entries: TtEntry[]; uploads: TtUpload[] }

export interface Submission { id: number; homework_id: number; student_id: number; text: string; original_name: string; content_type: string; submitted_at: string; is_late: boolean; status: "submitted" | "reviewed" | "returned"; feedback: string; grade: string; reviewed_at: string | null }
export interface Homework {
  id: number; section_id: number; subject_id: number; teacher_id: number; title: string; description: string; due_date: string; attachment_name: string; created_at: string;
  total_students: number | null; submitted_count: number | null; reviewed_count: number | null; my_submission: Submission | null;
}
export interface SubmissionRow { student_id: number; admission_no: string; full_name: string; roll_no: number | null; submission: Submission | null }

export type LeaveStatus = "pending_parent" | "pending_teacher" | "pending_admin" | "approved" | "rejected" | "cancelled";
export interface Leave {
  id: number; applicant_role: "student" | "teacher"; applicant_name: string; student_id: number | null; teacher_id: number | null; section_id: number | null;
  leave_type: string; from_date: string; to_date: string; days: number; reason: string; attachment_name: string; status: LeaveStatus; created_at: string;
  approvals: { step: string; approver_name: string; decision: string; comment: string; decided_at: string }[]; can_act: boolean; can_cancel: boolean;
}
export interface IdCard {
  student_id: number; admission_no: string; full_name: string; class_name: string; section_name: string; roll_no: number | null; dob: string; gender: string;
  photo_url: string; parent_mobile: string; school_name: string; school_code: string; school_address: string; logo_url: string; academic_year: string; qr_payload: string;
}
export interface IdVerify { valid: boolean; reason: string; student: IdCard | null }
export interface Notice { id: number; kind: string; key: string; params: Record<string, string | number>; link: string; read: boolean; created_at: string }

// ---------------------------------------------------------------- Phase 3
export type QType = "mcq" | "true_false" | "fill_blank" | "descriptive";
export type QAnswer = number | boolean | string | string[] | null;
export interface QuestionStaff { id?: number; position?: number; qtype: QType; text: string; options: string[]; answer: QAnswer; explanation: string; topic: string; difficulty: "easy" | "medium" | "hard"; marks: number }
export interface AttemptBrief { id: number; status: "in_progress" | "submitted" | "graded"; score: number; max_score: number; submitted_at: string | null }
export interface Quiz {
  id: number; section_id: number; subject_id: number; teacher_id: number; title: string; description: string; status: "draft" | "published" | "closed";
  time_limit_minutes: number | null; source: "manual" | "pdf"; created_at: string; question_count: number; total_marks: number;
  attempt_count: number | null; pending_grading: number | null; my_attempt: AttemptBrief | null;
}
export interface QuizDetail extends Quiz { questions: QuestionStaff[] }
export interface QuestionPlay { id: number; qtype: QType; text: string; options: string[]; marks: number }
export interface AttemptPlay { attempt_id: number; quiz_id: number; title: string; started_at: string; deadline: string | null; questions: QuestionPlay[] }
export interface AnswerResult {
  answer_id: number; question_id: number; qtype: QType; text: string; options: string[]; marks: number; topic: string; your_answer: number | boolean | string | null;
  correct_answer: QAnswer; is_correct: boolean | null; marks_awarded: number | null; explanation: string; feedback: string;
}
export interface AttemptResult {
  id: number; quiz_id: number; quiz_title: string; student_id: number; student_name: string; status: "submitted" | "graded"; score: number; max_score: number;
  percentage: number | null; submitted_at: string | null; timed_out: boolean; answers: AnswerResult[];
}
export interface AttemptRow { student_id: number; admission_no: string; full_name: string; roll_no: number | null; attempt: AttemptBrief | null; attempt_id: number | null }

export interface MyResult { marks: number | null; absent: boolean; percentage: number | null; passed: boolean | null; remarks: string }
export interface Exam {
  id: number; name: string; kind: "mock" | "main"; section_id: number; subject_id: number; teacher_id: number; exam_date: string; max_marks: number; pass_marks: number;
  status: "draft" | "published"; published_at: string | null; has_paper: boolean; has_key: boolean; entered_count: number | null; total_students: number | null; my_result: MyResult | null;
}
export interface MarkRow { student_id: number; admission_no: string; full_name: string; roll_no: number | null; marks: number | null; absent: boolean; remarks: string; percentage: number | null }
export interface MarksSheet { exam: Exam; rows: MarkRow[]; stats: { entered: number; absent: number; average: number | null; highest: number | null; lowest: number | null; passed: number; failed: number } }

export interface SubjectResult {
  subject_id: number; subject: string; main_percentage: number | null; mock_percentage: number | null; quiz_percentage: number | null; grade: string | null;
  exams: { name: string; kind: "mock" | "main"; date: string; marks: number | null; max_marks: number; percentage: number | null; absent: boolean }[];
}
export interface ProgressPoint { date: string; kind: "main" | "mock" | "quiz"; label: string; subject: string; percentage: number }
export interface TopicStat { topic: string; correct: number; total: number; percentage: number; weak: boolean }
export interface ReportCardData {
  student_id: number; student_name: string; admission_no: string; class_name: string; section_name: string; roll_no: number | null; academic_year: string;
  subjects: SubjectResult[]; overall_percentage: number | null; overall_grade: string | null; progress: ProgressPoint[]; topics: TopicStat[];
  homework: { total: number; submitted: number; reviewed: number; late: number };
}

// ---------------------------------------------------------------- Phase 4: AI learning
export interface PracticeQuestion { question_id: number; qtype: QType; text: string; options: string[]; topic: string; marks: number }
export interface RoboOut { mode: "explain" | "why_wrong" | "next"; text: string; provider: string; cached: boolean; practice: PracticeQuestion | null }
export interface PracticeCheck { is_correct: boolean; correct_answer: QAnswer; explanation: string }
export interface AiMessage { id: number; role: "user" | "assistant"; content: string; sources: { document_id: number; name: string; snippet: string }[]; attachment_id: number | null; provider: string; created_at: string }
export interface AiConversation { id: number; title: string; created_at: string; updated_at: string }
export interface AiConversationDetail extends AiConversation { messages: AiMessage[] }
export interface AiDocument { id: number; name: string; content_type: string; chunk_count: number; readable: boolean; created_at: string }
export interface ChatTurn { user_message: AiMessage; assistant_message: AiMessage; document: AiDocument | null }
export interface MasteryTopic { subject_id: number; subject: string; topic: string; correct: number; total: number; mastery: number; level: "weak" | "ok" | "strong" }
export interface MasteryReport { student_id: number; topics: MasteryTopic[]; weak_count: number }
export interface PlanItem { id: number; day: number; kind: "revise" | "practice" | "flashcards" | "maintain" | "start" | "rest"; topic: string; subject_id: number | null; subject: string; minutes: number; difficulty: "easy" | "medium"; done: boolean }
export interface LearningPlan { id: number; student_id: number; week_start: string; items: PlanItem[]; stale: boolean; due_cards: number }
export interface GapTopic { subject_id: number; subject: string; topic: string; students_attempted: number; weak_students: number; avg_mastery: number; weak_list: { student_id: number; name: string; mastery: number }[] }
export interface Flashcard { id: number; subject_id: number | null; topic: string; front: string; back: string; source: "manual" | "mistakes" | "notes"; ease: number; interval_days: number; repetitions: number; lapses: number; due_date: string; last_reviewed: string | null }
export interface FlashcardGen { created: number; skipped_duplicates: number; cards: Flashcard[] }
export interface FlashcardStats { total: number; due: number; new: number; learned: number }
