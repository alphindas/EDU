-- EduNest 2.0 schema (sqlite). Generated from SQLAlchemy models: python -m scripts.export_schema

CREATE TABLE schools (
	id INTEGER NOT NULL, 
	name VARCHAR(200) NOT NULL, 
	code VARCHAR(32) NOT NULL, 
	address TEXT NOT NULL, 
	district VARCHAR(100) NOT NULL, 
	mandal VARCHAR(100) NOT NULL, 
	logo_url VARCHAR(500) NOT NULL, 
	default_language VARCHAR(5) NOT NULL, 
	headmaster_name VARCHAR(120) NOT NULL, 
	headmaster_phone VARCHAR(20) NOT NULL, 
	created_at DATETIME NOT NULL, 
	PRIMARY KEY (id)
);

CREATE UNIQUE INDEX ix_schools_code ON schools (code);

CREATE TABLE academic_years (
	id INTEGER NOT NULL, 
	label VARCHAR(20) NOT NULL, 
	start_date DATE NOT NULL, 
	end_date DATE NOT NULL, 
	is_current BOOLEAN NOT NULL, 
	school_id INTEGER NOT NULL, 
	created_at DATETIME NOT NULL, 
	updated_at DATETIME NOT NULL, 
	created_by INTEGER, 
	PRIMARY KEY (id), 
	FOREIGN KEY(school_id) REFERENCES schools (id)
);

CREATE INDEX ix_academic_years_school_id ON academic_years (school_id);

CREATE TABLE audit_logs (
	id INTEGER NOT NULL, 
	school_id INTEGER, 
	user_id INTEGER, 
	role VARCHAR(12) NOT NULL, 
	action VARCHAR(10) NOT NULL, 
	path VARCHAR(300) NOT NULL, 
	status_code INTEGER NOT NULL, 
	detail TEXT NOT NULL, 
	created_at DATETIME NOT NULL, 
	updated_at DATETIME NOT NULL, 
	created_by INTEGER, 
	PRIMARY KEY (id), 
	FOREIGN KEY(school_id) REFERENCES schools (id)
);

CREATE INDEX ix_audit_logs_school_id ON audit_logs (school_id);

CREATE INDEX ix_audit_logs_user_id ON audit_logs (user_id);

CREATE TABLE classes (
	id INTEGER NOT NULL, 
	name VARCHAR(20) NOT NULL, 
	sort_order INTEGER NOT NULL, 
	school_id INTEGER NOT NULL, 
	created_at DATETIME NOT NULL, 
	updated_at DATETIME NOT NULL, 
	created_by INTEGER, 
	PRIMARY KEY (id), 
	UNIQUE (school_id, name), 
	FOREIGN KEY(school_id) REFERENCES schools (id)
);

CREATE INDEX ix_classes_school_id ON classes (school_id);

CREATE TABLE otp_codes (
	id INTEGER NOT NULL, 
	mobile VARCHAR(20) NOT NULL, 
	code_hash VARCHAR(100) NOT NULL, 
	expires_at DATETIME NOT NULL, 
	attempts INTEGER NOT NULL, 
	used BOOLEAN NOT NULL, 
	school_id INTEGER NOT NULL, 
	created_at DATETIME NOT NULL, 
	updated_at DATETIME NOT NULL, 
	created_by INTEGER, 
	PRIMARY KEY (id), 
	FOREIGN KEY(school_id) REFERENCES schools (id)
);

CREATE INDEX ix_otp_codes_mobile ON otp_codes (mobile);

CREATE INDEX ix_otp_codes_school_id ON otp_codes (school_id);

CREATE TABLE periods (
	id INTEGER NOT NULL, 
	number INTEGER NOT NULL, 
	label VARCHAR(40) NOT NULL, 
	start_time TIME NOT NULL, 
	end_time TIME NOT NULL, 
	is_break BOOLEAN NOT NULL, 
	school_id INTEGER NOT NULL, 
	created_at DATETIME NOT NULL, 
	updated_at DATETIME NOT NULL, 
	created_by INTEGER, 
	PRIMARY KEY (id), 
	UNIQUE (school_id, number), 
	FOREIGN KEY(school_id) REFERENCES schools (id)
);

CREATE INDEX ix_periods_school_id ON periods (school_id);

CREATE TABLE subjects (
	id INTEGER NOT NULL, 
	name VARCHAR(100) NOT NULL, 
	code VARCHAR(20) NOT NULL, 
	school_id INTEGER NOT NULL, 
	created_at DATETIME NOT NULL, 
	updated_at DATETIME NOT NULL, 
	created_by INTEGER, 
	PRIMARY KEY (id), 
	UNIQUE (school_id, name), 
	FOREIGN KEY(school_id) REFERENCES schools (id)
);

CREATE INDEX ix_subjects_school_id ON subjects (school_id);

CREATE TABLE transport_routes (
	id INTEGER NOT NULL, 
	name VARCHAR(100) NOT NULL, 
	stops JSON NOT NULL, 
	start_time VARCHAR(5) NOT NULL, 
	school_id INTEGER NOT NULL, 
	created_at DATETIME NOT NULL, 
	updated_at DATETIME NOT NULL, 
	created_by INTEGER, 
	PRIMARY KEY (id), 
	FOREIGN KEY(school_id) REFERENCES schools (id)
);

CREATE INDEX ix_transport_routes_school_id ON transport_routes (school_id);

CREATE TABLE users (
	id INTEGER NOT NULL, 
	school_id INTEGER, 
	role VARCHAR(12) NOT NULL, 
	login_id VARCHAR(64) NOT NULL, 
	password_hash VARCHAR(100), 
	must_change_password BOOLEAN NOT NULL, 
	is_active BOOLEAN NOT NULL, 
	full_name VARCHAR(120) NOT NULL, 
	phone VARCHAR(20) NOT NULL, 
	email VARCHAR(200) NOT NULL, 
	language VARCHAR(5) NOT NULL, 
	last_login_at DATETIME, 
	created_at DATETIME NOT NULL, 
	updated_at DATETIME NOT NULL, 
	created_by INTEGER, 
	PRIMARY KEY (id), 
	UNIQUE (school_id, role, login_id), 
	FOREIGN KEY(school_id) REFERENCES schools (id)
);

CREATE INDEX ix_users_role ON users (role);

CREATE INDEX ix_users_school_id ON users (school_id);

CREATE TABLE ai_calls (
	id INTEGER NOT NULL, 
	user_id INTEGER NOT NULL, 
	kind VARCHAR(20) NOT NULL, 
	provider VARCHAR(20) NOT NULL, 
	school_id INTEGER NOT NULL, 
	created_at DATETIME NOT NULL, 
	updated_at DATETIME NOT NULL, 
	created_by INTEGER, 
	PRIMARY KEY (id), 
	FOREIGN KEY(user_id) REFERENCES users (id), 
	FOREIGN KEY(school_id) REFERENCES schools (id)
);

CREATE INDEX ix_ai_calls_school_id ON ai_calls (school_id);

CREATE INDEX ix_ai_calls_user_id ON ai_calls (user_id);

CREATE TABLE ai_conversations (
	id INTEGER NOT NULL, 
	user_id INTEGER NOT NULL, 
	title VARCHAR(120) NOT NULL, 
	school_id INTEGER NOT NULL, 
	created_at DATETIME NOT NULL, 
	updated_at DATETIME NOT NULL, 
	created_by INTEGER, 
	PRIMARY KEY (id), 
	FOREIGN KEY(user_id) REFERENCES users (id), 
	FOREIGN KEY(school_id) REFERENCES schools (id)
);

CREATE INDEX ix_ai_conversations_school_id ON ai_conversations (school_id);

CREATE INDEX ix_ai_conversations_user_id ON ai_conversations (user_id);

CREATE TABLE ai_documents (
	id INTEGER NOT NULL, 
	user_id INTEGER NOT NULL, 
	name VARCHAR(200) NOT NULL, 
	content_type VARCHAR(80) NOT NULL, 
	file_path VARCHAR(300) NOT NULL, 
	text TEXT NOT NULL, 
	chunk_count INTEGER NOT NULL, 
	school_id INTEGER NOT NULL, 
	created_at DATETIME NOT NULL, 
	updated_at DATETIME NOT NULL, 
	created_by INTEGER, 
	PRIMARY KEY (id), 
	FOREIGN KEY(user_id) REFERENCES users (id), 
	FOREIGN KEY(school_id) REFERENCES schools (id)
);

CREATE INDEX ix_ai_documents_school_id ON ai_documents (school_id);

CREATE INDEX ix_ai_documents_user_id ON ai_documents (user_id);

CREATE TABLE counselling_threads (
	id INTEGER NOT NULL, 
	student_user_id INTEGER NOT NULL, 
	topic VARCHAR(20) NOT NULL, 
	anonymous BOOLEAN NOT NULL, 
	status VARCHAR(10) NOT NULL, 
	school_id INTEGER NOT NULL, 
	created_at DATETIME NOT NULL, 
	updated_at DATETIME NOT NULL, 
	created_by INTEGER, 
	PRIMARY KEY (id), 
	FOREIGN KEY(student_user_id) REFERENCES users (id), 
	FOREIGN KEY(school_id) REFERENCES schools (id)
);

CREATE INDEX ix_counselling_threads_school_id ON counselling_threads (school_id);

CREATE INDEX ix_counselling_threads_student_user_id ON counselling_threads (student_user_id);

CREATE TABLE direct_messages (
	id INTEGER NOT NULL, 
	sender_user_id INTEGER NOT NULL, 
	recipient_user_id INTEGER NOT NULL, 
	body TEXT NOT NULL, 
	read BOOLEAN NOT NULL, 
	school_id INTEGER NOT NULL, 
	created_at DATETIME NOT NULL, 
	updated_at DATETIME NOT NULL, 
	created_by INTEGER, 
	PRIMARY KEY (id), 
	FOREIGN KEY(sender_user_id) REFERENCES users (id), 
	FOREIGN KEY(recipient_user_id) REFERENCES users (id), 
	FOREIGN KEY(school_id) REFERENCES schools (id)
);

CREATE INDEX ix_direct_messages_recipient_user_id ON direct_messages (recipient_user_id);

CREATE INDEX ix_direct_messages_school_id ON direct_messages (school_id);

CREATE INDEX ix_direct_messages_sender_user_id ON direct_messages (sender_user_id);

CREATE TABLE notifications (
	id INTEGER NOT NULL, 
	user_id INTEGER NOT NULL, 
	kind VARCHAR(30) NOT NULL, 
	"key" VARCHAR(80) NOT NULL, 
	params JSON NOT NULL, 
	link VARCHAR(200) NOT NULL, 
	read BOOLEAN NOT NULL, 
	school_id INTEGER NOT NULL, 
	created_at DATETIME NOT NULL, 
	updated_at DATETIME NOT NULL, 
	created_by INTEGER, 
	PRIMARY KEY (id), 
	FOREIGN KEY(user_id) REFERENCES users (id), 
	FOREIGN KEY(school_id) REFERENCES schools (id)
);

CREATE INDEX ix_notifications_school_id ON notifications (school_id);

CREATE INDEX ix_notifications_user_id ON notifications (user_id);

CREATE TABLE parents (
	id INTEGER NOT NULL, 
	user_id INTEGER NOT NULL, 
	mobile VARCHAR(20) NOT NULL, 
	relation VARCHAR(30) NOT NULL, 
	alert_channels JSON NOT NULL, 
	emergency_contact VARCHAR(20) NOT NULL, 
	school_id INTEGER NOT NULL, 
	created_at DATETIME NOT NULL, 
	updated_at DATETIME NOT NULL, 
	created_by INTEGER, 
	PRIMARY KEY (id), 
	UNIQUE (school_id, mobile), 
	UNIQUE (user_id), 
	FOREIGN KEY(user_id) REFERENCES users (id), 
	FOREIGN KEY(school_id) REFERENCES schools (id)
);

CREATE INDEX ix_parents_school_id ON parents (school_id);

CREATE TABLE projects (
	id INTEGER NOT NULL, 
	owner_user_id INTEGER NOT NULL, 
	title VARCHAR(200) NOT NULL, 
	summary TEXT NOT NULL, 
	category VARCHAR(20) NOT NULL, 
	status VARCHAR(12) NOT NULL, 
	max_members INTEGER NOT NULL, 
	members JSON NOT NULL, 
	emoji VARCHAR(8) NOT NULL, 
	school_id INTEGER NOT NULL, 
	created_at DATETIME NOT NULL, 
	updated_at DATETIME NOT NULL, 
	created_by INTEGER, 
	PRIMARY KEY (id), 
	FOREIGN KEY(owner_user_id) REFERENCES users (id), 
	FOREIGN KEY(school_id) REFERENCES schools (id)
);

CREATE INDEX ix_projects_owner_user_id ON projects (owner_user_id);

CREATE INDEX ix_projects_school_id ON projects (school_id);

CREATE TABLE resources (
	id INTEGER NOT NULL, 
	kind VARCHAR(10) NOT NULL, 
	title VARCHAR(200) NOT NULL, 
	description TEXT NOT NULL, 
	class_id INTEGER, 
	subject_id INTEGER, 
	year INTEGER, 
	institution VARCHAR(120) NOT NULL, 
	chapters JSON NOT NULL, 
	text TEXT NOT NULL, 
	file_path VARCHAR(300) NOT NULL, 
	content_type VARCHAR(80) NOT NULL, 
	original_name VARCHAR(200) NOT NULL, 
	url VARCHAR(500) NOT NULL, 
	approved BOOLEAN NOT NULL, 
	school_id INTEGER NOT NULL, 
	created_at DATETIME NOT NULL, 
	updated_at DATETIME NOT NULL, 
	created_by INTEGER, 
	PRIMARY KEY (id), 
	FOREIGN KEY(class_id) REFERENCES classes (id), 
	FOREIGN KEY(subject_id) REFERENCES subjects (id), 
	FOREIGN KEY(school_id) REFERENCES schools (id)
);

CREATE INDEX ix_resources_class_id ON resources (class_id);

CREATE INDEX ix_resources_kind ON resources (kind);

CREATE INDEX ix_resources_school_id ON resources (school_id);

CREATE INDEX ix_resources_subject_id ON resources (subject_id);

CREATE TABLE staff_flags (
	id INTEGER NOT NULL, 
	user_id INTEGER NOT NULL, 
	counsellor BOOLEAN NOT NULL, 
	school_id INTEGER NOT NULL, 
	created_at DATETIME NOT NULL, 
	updated_at DATETIME NOT NULL, 
	created_by INTEGER, 
	PRIMARY KEY (id), 
	UNIQUE (user_id), 
	FOREIGN KEY(user_id) REFERENCES users (id), 
	FOREIGN KEY(school_id) REFERENCES schools (id)
);

CREATE INDEX ix_staff_flags_school_id ON staff_flags (school_id);

CREATE INDEX ix_staff_flags_user_id ON staff_flags (user_id);

CREATE TABLE teachers (
	id INTEGER NOT NULL, 
	user_id INTEGER NOT NULL, 
	employee_id VARCHAR(32) NOT NULL, 
	qualification VARCHAR(200) NOT NULL, 
	joining_date DATE, 
	photo_url VARCHAR(500) NOT NULL, 
	school_id INTEGER NOT NULL, 
	created_at DATETIME NOT NULL, 
	updated_at DATETIME NOT NULL, 
	created_by INTEGER, 
	PRIMARY KEY (id), 
	UNIQUE (school_id, employee_id), 
	UNIQUE (user_id), 
	FOREIGN KEY(user_id) REFERENCES users (id), 
	FOREIGN KEY(school_id) REFERENCES schools (id)
);

CREATE INDEX ix_teachers_school_id ON teachers (school_id);

CREATE TABLE vehicles (
	id INTEGER NOT NULL, 
	route_id INTEGER, 
	number VARCHAR(20) NOT NULL, 
	driver_name VARCHAR(100) NOT NULL, 
	driver_phone VARCHAR(20) NOT NULL, 
	capacity INTEGER NOT NULL, 
	device_token VARCHAR(64) NOT NULL, 
	school_id INTEGER NOT NULL, 
	created_at DATETIME NOT NULL, 
	updated_at DATETIME NOT NULL, 
	created_by INTEGER, 
	PRIMARY KEY (id), 
	FOREIGN KEY(route_id) REFERENCES transport_routes (id), 
	FOREIGN KEY(school_id) REFERENCES schools (id)
);

CREATE INDEX ix_vehicles_route_id ON vehicles (route_id);

CREATE INDEX ix_vehicles_school_id ON vehicles (school_id);

CREATE TABLE ai_chunks (
	id INTEGER NOT NULL, 
	document_id INTEGER NOT NULL, 
	user_id INTEGER NOT NULL, 
	position INTEGER NOT NULL, 
	text TEXT NOT NULL, 
	embedding JSON NOT NULL, 
	embed_model VARCHAR(40) NOT NULL, 
	school_id INTEGER NOT NULL, 
	created_at DATETIME NOT NULL, 
	updated_at DATETIME NOT NULL, 
	created_by INTEGER, 
	PRIMARY KEY (id), 
	FOREIGN KEY(document_id) REFERENCES ai_documents (id), 
	FOREIGN KEY(user_id) REFERENCES users (id), 
	FOREIGN KEY(school_id) REFERENCES schools (id)
);

CREATE INDEX ix_ai_chunks_document_id ON ai_chunks (document_id);

CREATE INDEX ix_ai_chunks_school_id ON ai_chunks (school_id);

CREATE INDEX ix_ai_chunks_user_id ON ai_chunks (user_id);

CREATE TABLE ai_messages (
	id INTEGER NOT NULL, 
	conversation_id INTEGER NOT NULL, 
	role VARCHAR(10) NOT NULL, 
	content TEXT NOT NULL, 
	sources JSON NOT NULL, 
	attachment_id INTEGER, 
	provider VARCHAR(20) NOT NULL, 
	school_id INTEGER NOT NULL, 
	created_at DATETIME NOT NULL, 
	updated_at DATETIME NOT NULL, 
	created_by INTEGER, 
	PRIMARY KEY (id), 
	FOREIGN KEY(conversation_id) REFERENCES ai_conversations (id), 
	FOREIGN KEY(attachment_id) REFERENCES ai_documents (id) ON DELETE SET NULL, 
	FOREIGN KEY(school_id) REFERENCES schools (id)
);

CREATE INDEX ix_ai_messages_conversation_id ON ai_messages (conversation_id);

CREATE INDEX ix_ai_messages_school_id ON ai_messages (school_id);

CREATE TABLE counselling_messages (
	id INTEGER NOT NULL, 
	thread_id INTEGER NOT NULL, 
	from_staff BOOLEAN NOT NULL, 
	staff_user_id INTEGER, 
	body TEXT NOT NULL, 
	school_id INTEGER NOT NULL, 
	created_at DATETIME NOT NULL, 
	updated_at DATETIME NOT NULL, 
	created_by INTEGER, 
	PRIMARY KEY (id), 
	FOREIGN KEY(thread_id) REFERENCES counselling_threads (id), 
	FOREIGN KEY(staff_user_id) REFERENCES users (id), 
	FOREIGN KEY(school_id) REFERENCES schools (id)
);

CREATE INDEX ix_counselling_messages_school_id ON counselling_messages (school_id);

CREATE INDEX ix_counselling_messages_thread_id ON counselling_messages (thread_id);

CREATE TABLE project_comments (
	id INTEGER NOT NULL, 
	project_id INTEGER NOT NULL, 
	author_user_id INTEGER NOT NULL, 
	body TEXT NOT NULL, 
	school_id INTEGER NOT NULL, 
	created_at DATETIME NOT NULL, 
	updated_at DATETIME NOT NULL, 
	created_by INTEGER, 
	PRIMARY KEY (id), 
	FOREIGN KEY(project_id) REFERENCES projects (id), 
	FOREIGN KEY(author_user_id) REFERENCES users (id), 
	FOREIGN KEY(school_id) REFERENCES schools (id)
);

CREATE INDEX ix_project_comments_project_id ON project_comments (project_id);

CREATE INDEX ix_project_comments_school_id ON project_comments (school_id);

CREATE TABLE resource_progress (
	id INTEGER NOT NULL, 
	resource_id INTEGER NOT NULL, 
	user_id INTEGER NOT NULL, 
	completed_chapters JSON NOT NULL, 
	bookmarks JSON NOT NULL, 
	school_id INTEGER NOT NULL, 
	created_at DATETIME NOT NULL, 
	updated_at DATETIME NOT NULL, 
	created_by INTEGER, 
	PRIMARY KEY (id), 
	UNIQUE (resource_id, user_id), 
	FOREIGN KEY(resource_id) REFERENCES resources (id), 
	FOREIGN KEY(user_id) REFERENCES users (id), 
	FOREIGN KEY(school_id) REFERENCES schools (id)
);

CREATE INDEX ix_resource_progress_resource_id ON resource_progress (resource_id);

CREATE INDEX ix_resource_progress_school_id ON resource_progress (school_id);

CREATE INDEX ix_resource_progress_user_id ON resource_progress (user_id);

CREATE TABLE sections (
	id INTEGER NOT NULL, 
	class_id INTEGER NOT NULL, 
	name VARCHAR(10) NOT NULL, 
	class_teacher_id INTEGER, 
	school_id INTEGER NOT NULL, 
	created_at DATETIME NOT NULL, 
	updated_at DATETIME NOT NULL, 
	created_by INTEGER, 
	PRIMARY KEY (id), 
	UNIQUE (school_id, class_id, name), 
	FOREIGN KEY(class_id) REFERENCES classes (id), 
	FOREIGN KEY(class_teacher_id) REFERENCES teachers (id), 
	FOREIGN KEY(school_id) REFERENCES schools (id)
);

CREATE INDEX ix_sections_class_id ON sections (class_id);

CREATE INDEX ix_sections_class_teacher_id ON sections (class_teacher_id);

CREATE INDEX ix_sections_school_id ON sections (school_id);

CREATE TABLE vehicle_locations (
	id INTEGER NOT NULL, 
	vehicle_id INTEGER NOT NULL, 
	lat FLOAT NOT NULL, 
	lng FLOAT NOT NULL, 
	speed_kmh FLOAT NOT NULL, 
	recorded_at DATETIME NOT NULL, 
	school_id INTEGER NOT NULL, 
	created_at DATETIME NOT NULL, 
	updated_at DATETIME NOT NULL, 
	created_by INTEGER, 
	PRIMARY KEY (id), 
	FOREIGN KEY(vehicle_id) REFERENCES vehicles (id), 
	FOREIGN KEY(school_id) REFERENCES schools (id)
);

CREATE INDEX ix_vehicle_locations_recorded_at ON vehicle_locations (recorded_at);

CREATE INDEX ix_vehicle_locations_school_id ON vehicle_locations (school_id);

CREATE INDEX ix_vehicle_locations_vehicle_id ON vehicle_locations (vehicle_id);

CREATE TABLE announcements (
	id INTEGER NOT NULL, 
	title VARCHAR(200) NOT NULL, 
	body TEXT NOT NULL, 
	audience VARCHAR(10) NOT NULL, 
	section_id INTEGER, 
	pinned BOOLEAN NOT NULL, 
	emoji VARCHAR(8) NOT NULL, 
	author_user_id INTEGER NOT NULL, 
	school_id INTEGER NOT NULL, 
	created_at DATETIME NOT NULL, 
	updated_at DATETIME NOT NULL, 
	created_by INTEGER, 
	PRIMARY KEY (id), 
	FOREIGN KEY(section_id) REFERENCES sections (id), 
	FOREIGN KEY(author_user_id) REFERENCES users (id), 
	FOREIGN KEY(school_id) REFERENCES schools (id)
);

CREATE INDEX ix_announcements_school_id ON announcements (school_id);

CREATE TABLE attendance_sessions (
	id INTEGER NOT NULL, 
	section_id INTEGER NOT NULL, 
	date DATE NOT NULL, 
	period INTEGER NOT NULL, 
	subject_id INTEGER, 
	marked_by INTEGER, 
	source VARCHAR(10) NOT NULL, 
	school_id INTEGER NOT NULL, 
	created_at DATETIME NOT NULL, 
	updated_at DATETIME NOT NULL, 
	created_by INTEGER, 
	PRIMARY KEY (id), 
	UNIQUE (school_id, section_id, date, period), 
	FOREIGN KEY(section_id) REFERENCES sections (id), 
	FOREIGN KEY(subject_id) REFERENCES subjects (id), 
	FOREIGN KEY(marked_by) REFERENCES users (id), 
	FOREIGN KEY(school_id) REFERENCES schools (id)
);

CREATE INDEX ix_attendance_sessions_date ON attendance_sessions (date);

CREATE INDEX ix_attendance_sessions_school_id ON attendance_sessions (school_id);

CREATE INDEX ix_attendance_sessions_section_id ON attendance_sessions (section_id);

CREATE TABLE exams (
	id INTEGER NOT NULL, 
	name VARCHAR(200) NOT NULL, 
	kind VARCHAR(6) NOT NULL, 
	section_id INTEGER NOT NULL, 
	subject_id INTEGER NOT NULL, 
	teacher_id INTEGER NOT NULL, 
	exam_date DATE NOT NULL, 
	max_marks FLOAT NOT NULL, 
	pass_marks FLOAT NOT NULL, 
	status VARCHAR(10) NOT NULL, 
	published_at DATETIME, 
	school_id INTEGER NOT NULL, 
	created_at DATETIME NOT NULL, 
	updated_at DATETIME NOT NULL, 
	created_by INTEGER, 
	PRIMARY KEY (id), 
	FOREIGN KEY(section_id) REFERENCES sections (id), 
	FOREIGN KEY(subject_id) REFERENCES subjects (id), 
	FOREIGN KEY(teacher_id) REFERENCES teachers (id), 
	FOREIGN KEY(school_id) REFERENCES schools (id)
);

CREATE INDEX ix_exams_kind ON exams (kind);

CREATE INDEX ix_exams_school_id ON exams (school_id);

CREATE INDEX ix_exams_section_id ON exams (section_id);

CREATE INDEX ix_exams_subject_id ON exams (subject_id);

CREATE INDEX ix_exams_teacher_id ON exams (teacher_id);

CREATE TABLE forum_posts (
	id INTEGER NOT NULL, 
	author_user_id INTEGER NOT NULL, 
	section_id INTEGER, 
	subject_id INTEGER, 
	kind VARCHAR(10) NOT NULL, 
	title VARCHAR(200) NOT NULL, 
	body TEXT NOT NULL, 
	solved BOOLEAN NOT NULL, 
	hidden BOOLEAN NOT NULL, 
	likes JSON NOT NULL, 
	school_id INTEGER NOT NULL, 
	created_at DATETIME NOT NULL, 
	updated_at DATETIME NOT NULL, 
	created_by INTEGER, 
	PRIMARY KEY (id), 
	FOREIGN KEY(author_user_id) REFERENCES users (id), 
	FOREIGN KEY(section_id) REFERENCES sections (id), 
	FOREIGN KEY(subject_id) REFERENCES subjects (id), 
	FOREIGN KEY(school_id) REFERENCES schools (id)
);

CREATE INDEX ix_forum_posts_author_user_id ON forum_posts (author_user_id);

CREATE INDEX ix_forum_posts_school_id ON forum_posts (school_id);

CREATE INDEX ix_forum_posts_section_id ON forum_posts (section_id);

CREATE TABLE homework (
	id INTEGER NOT NULL, 
	section_id INTEGER NOT NULL, 
	subject_id INTEGER NOT NULL, 
	teacher_id INTEGER NOT NULL, 
	title VARCHAR(200) NOT NULL, 
	description TEXT NOT NULL, 
	due_date DATE NOT NULL, 
	file_path VARCHAR(300) NOT NULL, 
	content_type VARCHAR(80) NOT NULL, 
	original_name VARCHAR(200) NOT NULL, 
	school_id INTEGER NOT NULL, 
	created_at DATETIME NOT NULL, 
	updated_at DATETIME NOT NULL, 
	created_by INTEGER, 
	PRIMARY KEY (id), 
	FOREIGN KEY(section_id) REFERENCES sections (id), 
	FOREIGN KEY(subject_id) REFERENCES subjects (id), 
	FOREIGN KEY(teacher_id) REFERENCES teachers (id), 
	FOREIGN KEY(school_id) REFERENCES schools (id)
);

CREATE INDEX ix_homework_school_id ON homework (school_id);

CREATE INDEX ix_homework_section_id ON homework (section_id);

CREATE INDEX ix_homework_subject_id ON homework (subject_id);

CREATE INDEX ix_homework_teacher_id ON homework (teacher_id);

CREATE TABLE quizzes (
	id INTEGER NOT NULL, 
	section_id INTEGER NOT NULL, 
	subject_id INTEGER NOT NULL, 
	teacher_id INTEGER NOT NULL, 
	title VARCHAR(200) NOT NULL, 
	description TEXT NOT NULL, 
	status VARCHAR(10) NOT NULL, 
	time_limit_minutes INTEGER, 
	source VARCHAR(10) NOT NULL, 
	source_file VARCHAR(300) NOT NULL, 
	school_id INTEGER NOT NULL, 
	created_at DATETIME NOT NULL, 
	updated_at DATETIME NOT NULL, 
	created_by INTEGER, 
	PRIMARY KEY (id), 
	FOREIGN KEY(section_id) REFERENCES sections (id), 
	FOREIGN KEY(subject_id) REFERENCES subjects (id), 
	FOREIGN KEY(teacher_id) REFERENCES teachers (id), 
	FOREIGN KEY(school_id) REFERENCES schools (id)
);

CREATE INDEX ix_quizzes_school_id ON quizzes (school_id);

CREATE INDEX ix_quizzes_section_id ON quizzes (section_id);

CREATE INDEX ix_quizzes_status ON quizzes (status);

CREATE INDEX ix_quizzes_subject_id ON quizzes (subject_id);

CREATE INDEX ix_quizzes_teacher_id ON quizzes (teacher_id);

CREATE TABLE students (
	id INTEGER NOT NULL, 
	user_id INTEGER NOT NULL, 
	admission_no VARCHAR(32) NOT NULL, 
	class_id INTEGER NOT NULL, 
	section_id INTEGER NOT NULL, 
	roll_no INTEGER, 
	dob DATE NOT NULL, 
	gender VARCHAR(10) NOT NULL, 
	photo_url VARCHAR(500) NOT NULL, 
	parent_mobile VARCHAR(20) NOT NULL, 
	address TEXT NOT NULL, 
	category VARCHAR(20) NOT NULL, 
	medical_notes TEXT NOT NULL, 
	deleted_at DATETIME, 
	school_id INTEGER NOT NULL, 
	created_at DATETIME NOT NULL, 
	updated_at DATETIME NOT NULL, 
	created_by INTEGER, 
	PRIMARY KEY (id), 
	UNIQUE (school_id, admission_no), 
	UNIQUE (user_id), 
	FOREIGN KEY(user_id) REFERENCES users (id), 
	FOREIGN KEY(class_id) REFERENCES classes (id), 
	FOREIGN KEY(section_id) REFERENCES sections (id), 
	FOREIGN KEY(school_id) REFERENCES schools (id)
);

CREATE INDEX ix_students_class_id ON students (class_id);

CREATE INDEX ix_students_parent_mobile ON students (parent_mobile);

CREATE INDEX ix_students_school_id ON students (school_id);

CREATE INDEX ix_students_section_id ON students (section_id);

CREATE TABLE teacher_assignments (
	id INTEGER NOT NULL, 
	teacher_id INTEGER NOT NULL, 
	section_id INTEGER NOT NULL, 
	subject_id INTEGER NOT NULL, 
	school_id INTEGER NOT NULL, 
	created_at DATETIME NOT NULL, 
	updated_at DATETIME NOT NULL, 
	created_by INTEGER, 
	PRIMARY KEY (id), 
	UNIQUE (teacher_id, section_id, subject_id), 
	FOREIGN KEY(teacher_id) REFERENCES teachers (id), 
	FOREIGN KEY(section_id) REFERENCES sections (id), 
	FOREIGN KEY(subject_id) REFERENCES subjects (id), 
	FOREIGN KEY(school_id) REFERENCES schools (id)
);

CREATE INDEX ix_teacher_assignments_school_id ON teacher_assignments (school_id);

CREATE INDEX ix_teacher_assignments_section_id ON teacher_assignments (section_id);

CREATE INDEX ix_teacher_assignments_subject_id ON teacher_assignments (subject_id);

CREATE INDEX ix_teacher_assignments_teacher_id ON teacher_assignments (teacher_id);

CREATE TABLE timetable_entries (
	id INTEGER NOT NULL, 
	section_id INTEGER NOT NULL, 
	day INTEGER NOT NULL, 
	period_id INTEGER NOT NULL, 
	subject_id INTEGER NOT NULL, 
	teacher_id INTEGER, 
	room VARCHAR(30) NOT NULL, 
	school_id INTEGER NOT NULL, 
	created_at DATETIME NOT NULL, 
	updated_at DATETIME NOT NULL, 
	created_by INTEGER, 
	PRIMARY KEY (id), 
	UNIQUE (school_id, section_id, day, period_id), 
	FOREIGN KEY(section_id) REFERENCES sections (id), 
	FOREIGN KEY(period_id) REFERENCES periods (id), 
	FOREIGN KEY(subject_id) REFERENCES subjects (id), 
	FOREIGN KEY(teacher_id) REFERENCES teachers (id), 
	FOREIGN KEY(school_id) REFERENCES schools (id)
);

CREATE INDEX ix_timetable_entries_period_id ON timetable_entries (period_id);

CREATE INDEX ix_timetable_entries_school_id ON timetable_entries (school_id);

CREATE INDEX ix_timetable_entries_section_id ON timetable_entries (section_id);

CREATE INDEX ix_timetable_entries_teacher_id ON timetable_entries (teacher_id);

CREATE TABLE timetable_uploads (
	id INTEGER NOT NULL, 
	section_id INTEGER NOT NULL, 
	kind VARCHAR(10) NOT NULL, 
	text TEXT NOT NULL, 
	file_path VARCHAR(300) NOT NULL, 
	content_type VARCHAR(60) NOT NULL, 
	original_name VARCHAR(200) NOT NULL, 
	uploaded_by INTEGER, 
	school_id INTEGER NOT NULL, 
	created_at DATETIME NOT NULL, 
	updated_at DATETIME NOT NULL, 
	created_by INTEGER, 
	PRIMARY KEY (id), 
	FOREIGN KEY(section_id) REFERENCES sections (id), 
	FOREIGN KEY(uploaded_by) REFERENCES users (id), 
	FOREIGN KEY(school_id) REFERENCES schools (id)
);

CREATE INDEX ix_timetable_uploads_school_id ON timetable_uploads (school_id);

CREATE INDEX ix_timetable_uploads_section_id ON timetable_uploads (section_id);

CREATE TABLE attendance_records (
	id INTEGER NOT NULL, 
	session_id INTEGER NOT NULL, 
	student_id INTEGER NOT NULL, 
	status VARCHAR(10) NOT NULL, 
	note VARCHAR(200) NOT NULL, 
	confidence FLOAT, 
	school_id INTEGER NOT NULL, 
	created_at DATETIME NOT NULL, 
	updated_at DATETIME NOT NULL, 
	created_by INTEGER, 
	PRIMARY KEY (id), 
	UNIQUE (session_id, student_id), 
	FOREIGN KEY(session_id) REFERENCES attendance_sessions (id), 
	FOREIGN KEY(student_id) REFERENCES students (id), 
	FOREIGN KEY(school_id) REFERENCES schools (id)
);

CREATE INDEX ix_attendance_records_school_id ON attendance_records (school_id);

CREATE INDEX ix_attendance_records_session_id ON attendance_records (session_id);

CREATE INDEX ix_attendance_records_student_id ON attendance_records (student_id);

CREATE TABLE brain_attempts (
	id INTEGER NOT NULL, 
	student_id INTEGER NOT NULL, 
	skill VARCHAR(12) NOT NULL, 
	difficulty INTEGER NOT NULL, 
	correct BOOLEAN NOT NULL, 
	time_ms INTEGER NOT NULL, 
	nonce VARCHAR(32) NOT NULL, 
	school_id INTEGER NOT NULL, 
	created_at DATETIME NOT NULL, 
	updated_at DATETIME NOT NULL, 
	created_by INTEGER, 
	PRIMARY KEY (id), 
	FOREIGN KEY(student_id) REFERENCES students (id), 
	FOREIGN KEY(school_id) REFERENCES schools (id)
);

CREATE INDEX ix_brain_attempts_nonce ON brain_attempts (nonce);

CREATE INDEX ix_brain_attempts_school_id ON brain_attempts (school_id);

CREATE INDEX ix_brain_attempts_skill ON brain_attempts (skill);

CREATE INDEX ix_brain_attempts_student_id ON brain_attempts (student_id);

CREATE TABLE career_results (
	id INTEGER NOT NULL, 
	student_id INTEGER NOT NULL, 
	answers JSON NOT NULL, 
	scores JSON NOT NULL, 
	suggestions JSON NOT NULL, 
	school_id INTEGER NOT NULL, 
	created_at DATETIME NOT NULL, 
	updated_at DATETIME NOT NULL, 
	created_by INTEGER, 
	PRIMARY KEY (id), 
	FOREIGN KEY(student_id) REFERENCES students (id), 
	FOREIGN KEY(school_id) REFERENCES schools (id)
);

CREATE INDEX ix_career_results_school_id ON career_results (school_id);

CREATE INDEX ix_career_results_student_id ON career_results (student_id);

CREATE TABLE english_sessions (
	id INTEGER NOT NULL, 
	student_id INTEGER NOT NULL, 
	kind VARCHAR(12) NOT NULL, 
	text TEXT NOT NULL, 
	words INTEGER NOT NULL, 
	wpm FLOAT NOT NULL, 
	fillers INTEGER NOT NULL, 
	issues INTEGER NOT NULL, 
	score FLOAT NOT NULL, 
	school_id INTEGER NOT NULL, 
	created_at DATETIME NOT NULL, 
	updated_at DATETIME NOT NULL, 
	created_by INTEGER, 
	PRIMARY KEY (id), 
	FOREIGN KEY(student_id) REFERENCES students (id), 
	FOREIGN KEY(school_id) REFERENCES schools (id)
);

CREATE INDEX ix_english_sessions_school_id ON english_sessions (school_id);

CREATE INDEX ix_english_sessions_student_id ON english_sessions (student_id);

CREATE TABLE exam_papers (
	id INTEGER NOT NULL, 
	exam_id INTEGER NOT NULL, 
	kind VARCHAR(6) NOT NULL, 
	file_path VARCHAR(300) NOT NULL, 
	content_type VARCHAR(80) NOT NULL, 
	original_name VARCHAR(200) NOT NULL, 
	school_id INTEGER NOT NULL, 
	created_at DATETIME NOT NULL, 
	updated_at DATETIME NOT NULL, 
	created_by INTEGER, 
	PRIMARY KEY (id), 
	UNIQUE (exam_id, kind), 
	FOREIGN KEY(exam_id) REFERENCES exams (id), 
	FOREIGN KEY(school_id) REFERENCES schools (id)
);

CREATE INDEX ix_exam_papers_exam_id ON exam_papers (exam_id);

CREATE INDEX ix_exam_papers_school_id ON exam_papers (school_id);

CREATE TABLE flashcards (
	id INTEGER NOT NULL, 
	student_id INTEGER NOT NULL, 
	subject_id INTEGER, 
	topic VARCHAR(100) NOT NULL, 
	front TEXT NOT NULL, 
	back TEXT NOT NULL, 
	source VARCHAR(10) NOT NULL, 
	ease FLOAT NOT NULL, 
	interval_days INTEGER NOT NULL, 
	repetitions INTEGER NOT NULL, 
	lapses INTEGER NOT NULL, 
	due_date DATE NOT NULL, 
	last_reviewed DATE, 
	school_id INTEGER NOT NULL, 
	created_at DATETIME NOT NULL, 
	updated_at DATETIME NOT NULL, 
	created_by INTEGER, 
	PRIMARY KEY (id), 
	FOREIGN KEY(student_id) REFERENCES students (id), 
	FOREIGN KEY(subject_id) REFERENCES subjects (id), 
	FOREIGN KEY(school_id) REFERENCES schools (id)
);

CREATE INDEX ix_flashcards_due_date ON flashcards (due_date);

CREATE INDEX ix_flashcards_school_id ON flashcards (school_id);

CREATE INDEX ix_flashcards_student_id ON flashcards (student_id);

CREATE TABLE forum_replies (
	id INTEGER NOT NULL, 
	post_id INTEGER NOT NULL, 
	author_user_id INTEGER NOT NULL, 
	body TEXT NOT NULL, 
	accepted BOOLEAN NOT NULL, 
	hidden BOOLEAN NOT NULL, 
	school_id INTEGER NOT NULL, 
	created_at DATETIME NOT NULL, 
	updated_at DATETIME NOT NULL, 
	created_by INTEGER, 
	PRIMARY KEY (id), 
	FOREIGN KEY(post_id) REFERENCES forum_posts (id), 
	FOREIGN KEY(author_user_id) REFERENCES users (id), 
	FOREIGN KEY(school_id) REFERENCES schools (id)
);

CREATE INDEX ix_forum_replies_post_id ON forum_replies (post_id);

CREATE INDEX ix_forum_replies_school_id ON forum_replies (school_id);

CREATE TABLE homework_submissions (
	id INTEGER NOT NULL, 
	homework_id INTEGER NOT NULL, 
	student_id INTEGER NOT NULL, 
	text TEXT NOT NULL, 
	file_path VARCHAR(300) NOT NULL, 
	content_type VARCHAR(80) NOT NULL, 
	original_name VARCHAR(200) NOT NULL, 
	submitted_at DATETIME NOT NULL, 
	is_late BOOLEAN NOT NULL, 
	status VARCHAR(12) NOT NULL, 
	feedback TEXT NOT NULL, 
	grade VARCHAR(20) NOT NULL, 
	reviewed_at DATETIME, 
	school_id INTEGER NOT NULL, 
	created_at DATETIME NOT NULL, 
	updated_at DATETIME NOT NULL, 
	created_by INTEGER, 
	PRIMARY KEY (id), 
	UNIQUE (homework_id, student_id), 
	FOREIGN KEY(homework_id) REFERENCES homework (id), 
	FOREIGN KEY(student_id) REFERENCES students (id), 
	FOREIGN KEY(school_id) REFERENCES schools (id)
);

CREATE INDEX ix_homework_submissions_homework_id ON homework_submissions (homework_id);

CREATE INDEX ix_homework_submissions_school_id ON homework_submissions (school_id);

CREATE INDEX ix_homework_submissions_student_id ON homework_submissions (student_id);

CREATE TABLE learning_plans (
	id INTEGER NOT NULL, 
	student_id INTEGER NOT NULL, 
	week_start DATE NOT NULL, 
	items JSON NOT NULL, 
	school_id INTEGER NOT NULL, 
	created_at DATETIME NOT NULL, 
	updated_at DATETIME NOT NULL, 
	created_by INTEGER, 
	PRIMARY KEY (id), 
	UNIQUE (student_id, week_start), 
	FOREIGN KEY(student_id) REFERENCES students (id), 
	FOREIGN KEY(school_id) REFERENCES schools (id)
);

CREATE INDEX ix_learning_plans_school_id ON learning_plans (school_id);

CREATE INDEX ix_learning_plans_student_id ON learning_plans (student_id);

CREATE TABLE leave_requests (
	id INTEGER NOT NULL, 
	applicant_user_id INTEGER NOT NULL, 
	applicant_role VARCHAR(12) NOT NULL, 
	student_id INTEGER, 
	teacher_id INTEGER, 
	leave_type VARCHAR(20) NOT NULL, 
	from_date DATE NOT NULL, 
	to_date DATE NOT NULL, 
	reason TEXT NOT NULL, 
	file_path VARCHAR(300) NOT NULL, 
	content_type VARCHAR(80) NOT NULL, 
	original_name VARCHAR(200) NOT NULL, 
	status VARCHAR(20) NOT NULL, 
	school_id INTEGER NOT NULL, 
	created_at DATETIME NOT NULL, 
	updated_at DATETIME NOT NULL, 
	created_by INTEGER, 
	PRIMARY KEY (id), 
	FOREIGN KEY(applicant_user_id) REFERENCES users (id), 
	FOREIGN KEY(student_id) REFERENCES students (id), 
	FOREIGN KEY(teacher_id) REFERENCES teachers (id), 
	FOREIGN KEY(school_id) REFERENCES schools (id)
);

CREATE INDEX ix_leave_requests_applicant_user_id ON leave_requests (applicant_user_id);

CREATE INDEX ix_leave_requests_school_id ON leave_requests (school_id);

CREATE INDEX ix_leave_requests_status ON leave_requests (status);

CREATE INDEX ix_leave_requests_student_id ON leave_requests (student_id);

CREATE INDEX ix_leave_requests_teacher_id ON leave_requests (teacher_id);

CREATE TABLE marks (
	id INTEGER NOT NULL, 
	exam_id INTEGER NOT NULL, 
	student_id INTEGER NOT NULL, 
	marks FLOAT, 
	absent BOOLEAN NOT NULL, 
	remarks VARCHAR(200) NOT NULL, 
	school_id INTEGER NOT NULL, 
	created_at DATETIME NOT NULL, 
	updated_at DATETIME NOT NULL, 
	created_by INTEGER, 
	PRIMARY KEY (id), 
	UNIQUE (exam_id, student_id), 
	FOREIGN KEY(exam_id) REFERENCES exams (id), 
	FOREIGN KEY(student_id) REFERENCES students (id), 
	FOREIGN KEY(school_id) REFERENCES schools (id)
);

CREATE INDEX ix_marks_exam_id ON marks (exam_id);

CREATE INDEX ix_marks_school_id ON marks (school_id);

CREATE INDEX ix_marks_student_id ON marks (student_id);

CREATE TABLE portfolio_items (
	id INTEGER NOT NULL, 
	student_id INTEGER NOT NULL, 
	kind VARCHAR(12) NOT NULL, 
	title VARCHAR(200) NOT NULL, 
	details TEXT NOT NULL, 
	achieved_on DATE, 
	file_path VARCHAR(300) NOT NULL, 
	content_type VARCHAR(80) NOT NULL, 
	original_name VARCHAR(200) NOT NULL, 
	school_id INTEGER NOT NULL, 
	created_at DATETIME NOT NULL, 
	updated_at DATETIME NOT NULL, 
	created_by INTEGER, 
	PRIMARY KEY (id), 
	FOREIGN KEY(student_id) REFERENCES students (id), 
	FOREIGN KEY(school_id) REFERENCES schools (id)
);

CREATE INDEX ix_portfolio_items_school_id ON portfolio_items (school_id);

CREATE INDEX ix_portfolio_items_student_id ON portfolio_items (student_id);

CREATE TABLE quest_claims (
	id INTEGER NOT NULL, 
	student_id INTEGER NOT NULL, 
	day DATE NOT NULL, 
	quest VARCHAR(40) NOT NULL, 
	school_id INTEGER NOT NULL, 
	created_at DATETIME NOT NULL, 
	updated_at DATETIME NOT NULL, 
	created_by INTEGER, 
	PRIMARY KEY (id), 
	UNIQUE (student_id, day, quest), 
	FOREIGN KEY(student_id) REFERENCES students (id), 
	FOREIGN KEY(school_id) REFERENCES schools (id)
);

CREATE INDEX ix_quest_claims_school_id ON quest_claims (school_id);

CREATE INDEX ix_quest_claims_student_id ON quest_claims (student_id);

CREATE TABLE quiz_attempts (
	id INTEGER NOT NULL, 
	quiz_id INTEGER NOT NULL, 
	student_id INTEGER NOT NULL, 
	started_at DATETIME NOT NULL, 
	submitted_at DATETIME, 
	status VARCHAR(12) NOT NULL, 
	score FLOAT NOT NULL, 
	max_score FLOAT NOT NULL, 
	timed_out BOOLEAN NOT NULL, 
	school_id INTEGER NOT NULL, 
	created_at DATETIME NOT NULL, 
	updated_at DATETIME NOT NULL, 
	created_by INTEGER, 
	PRIMARY KEY (id), 
	UNIQUE (quiz_id, student_id), 
	FOREIGN KEY(quiz_id) REFERENCES quizzes (id), 
	FOREIGN KEY(student_id) REFERENCES students (id), 
	FOREIGN KEY(school_id) REFERENCES schools (id)
);

CREATE INDEX ix_quiz_attempts_quiz_id ON quiz_attempts (quiz_id);

CREATE INDEX ix_quiz_attempts_school_id ON quiz_attempts (school_id);

CREATE INDEX ix_quiz_attempts_student_id ON quiz_attempts (student_id);

CREATE TABLE quiz_questions (
	id INTEGER NOT NULL, 
	quiz_id INTEGER NOT NULL, 
	position INTEGER NOT NULL, 
	qtype VARCHAR(12) NOT NULL, 
	text TEXT NOT NULL, 
	options JSON NOT NULL, 
	answer JSON, 
	explanation TEXT NOT NULL, 
	topic VARCHAR(100) NOT NULL, 
	difficulty VARCHAR(10) NOT NULL, 
	marks FLOAT NOT NULL, 
	school_id INTEGER NOT NULL, 
	created_at DATETIME NOT NULL, 
	updated_at DATETIME NOT NULL, 
	created_by INTEGER, 
	PRIMARY KEY (id), 
	FOREIGN KEY(quiz_id) REFERENCES quizzes (id), 
	FOREIGN KEY(school_id) REFERENCES schools (id)
);

CREATE INDEX ix_quiz_questions_quiz_id ON quiz_questions (quiz_id);

CREATE INDEX ix_quiz_questions_school_id ON quiz_questions (school_id);

CREATE TABLE reflections (
	id INTEGER NOT NULL, 
	student_id INTEGER NOT NULL, 
	day DATE NOT NULL, 
	kind VARCHAR(12) NOT NULL, 
	prompt VARCHAR(80) NOT NULL, 
	mood VARCHAR(8) NOT NULL, 
	text TEXT NOT NULL, 
	school_id INTEGER NOT NULL, 
	created_at DATETIME NOT NULL, 
	updated_at DATETIME NOT NULL, 
	created_by INTEGER, 
	PRIMARY KEY (id), 
	FOREIGN KEY(student_id) REFERENCES students (id), 
	FOREIGN KEY(school_id) REFERENCES schools (id)
);

CREATE INDEX ix_reflections_day ON reflections (day);

CREATE INDEX ix_reflections_school_id ON reflections (school_id);

CREATE INDEX ix_reflections_student_id ON reflections (student_id);

CREATE TABLE shop_purchases (
	id INTEGER NOT NULL, 
	student_id INTEGER NOT NULL, 
	item VARCHAR(40) NOT NULL, 
	cost INTEGER NOT NULL, 
	school_id INTEGER NOT NULL, 
	created_at DATETIME NOT NULL, 
	updated_at DATETIME NOT NULL, 
	created_by INTEGER, 
	PRIMARY KEY (id), 
	UNIQUE (student_id, item), 
	FOREIGN KEY(student_id) REFERENCES students (id), 
	FOREIGN KEY(school_id) REFERENCES schools (id)
);

CREATE INDEX ix_shop_purchases_school_id ON shop_purchases (school_id);

CREATE INDEX ix_shop_purchases_student_id ON shop_purchases (student_id);

CREATE TABLE streaks (
	id INTEGER NOT NULL, 
	student_id INTEGER NOT NULL, 
	current INTEGER NOT NULL, 
	best INTEGER NOT NULL, 
	last_day DATE, 
	freezes INTEGER NOT NULL, 
	school_id INTEGER NOT NULL, 
	created_at DATETIME NOT NULL, 
	updated_at DATETIME NOT NULL, 
	created_by INTEGER, 
	PRIMARY KEY (id), 
	UNIQUE (student_id), 
	FOREIGN KEY(student_id) REFERENCES students (id), 
	FOREIGN KEY(school_id) REFERENCES schools (id)
);

CREATE INDEX ix_streaks_school_id ON streaks (school_id);

CREATE INDEX ix_streaks_student_id ON streaks (student_id);

CREATE TABLE student_parents (
	id INTEGER NOT NULL, 
	student_id INTEGER NOT NULL, 
	parent_id INTEGER NOT NULL, 
	school_id INTEGER NOT NULL, 
	created_at DATETIME NOT NULL, 
	updated_at DATETIME NOT NULL, 
	created_by INTEGER, 
	PRIMARY KEY (id), 
	UNIQUE (student_id, parent_id), 
	FOREIGN KEY(student_id) REFERENCES students (id), 
	FOREIGN KEY(parent_id) REFERENCES parents (id), 
	FOREIGN KEY(school_id) REFERENCES schools (id)
);

CREATE INDEX ix_student_parents_parent_id ON student_parents (parent_id);

CREATE INDEX ix_student_parents_school_id ON student_parents (school_id);

CREATE INDEX ix_student_parents_student_id ON student_parents (student_id);

CREATE TABLE student_prefs (
	id INTEGER NOT NULL, 
	student_id INTEGER NOT NULL, 
	ai_consent BOOLEAN NOT NULL, 
	ai_consent_by INTEGER, 
	ai_consent_at DATETIME, 
	leaderboard_opt_in BOOLEAN NOT NULL, 
	avatar JSON NOT NULL, 
	team VARCHAR(20) NOT NULL, 
	school_id INTEGER NOT NULL, 
	created_at DATETIME NOT NULL, 
	updated_at DATETIME NOT NULL, 
	created_by INTEGER, 
	PRIMARY KEY (id), 
	UNIQUE (student_id), 
	FOREIGN KEY(student_id) REFERENCES students (id), 
	FOREIGN KEY(school_id) REFERENCES schools (id)
);

CREATE INDEX ix_student_prefs_school_id ON student_prefs (school_id);

CREATE INDEX ix_student_prefs_student_id ON student_prefs (student_id);

CREATE TABLE student_transport (
	id INTEGER NOT NULL, 
	student_id INTEGER NOT NULL, 
	route_id INTEGER NOT NULL, 
	stop_name VARCHAR(100) NOT NULL, 
	school_id INTEGER NOT NULL, 
	created_at DATETIME NOT NULL, 
	updated_at DATETIME NOT NULL, 
	created_by INTEGER, 
	PRIMARY KEY (id), 
	UNIQUE (student_id), 
	FOREIGN KEY(student_id) REFERENCES students (id), 
	FOREIGN KEY(route_id) REFERENCES transport_routes (id), 
	FOREIGN KEY(school_id) REFERENCES schools (id)
);

CREATE INDEX ix_student_transport_school_id ON student_transport (school_id);

CREATE INDEX ix_student_transport_student_id ON student_transport (student_id);

CREATE TABLE topic_mastery (
	id INTEGER NOT NULL, 
	student_id INTEGER NOT NULL, 
	subject_id INTEGER NOT NULL, 
	topic VARCHAR(100) NOT NULL, 
	correct INTEGER NOT NULL, 
	total INTEGER NOT NULL, 
	mastery FLOAT NOT NULL, 
	school_id INTEGER NOT NULL, 
	created_at DATETIME NOT NULL, 
	updated_at DATETIME NOT NULL, 
	created_by INTEGER, 
	PRIMARY KEY (id), 
	UNIQUE (student_id, subject_id, topic), 
	FOREIGN KEY(student_id) REFERENCES students (id), 
	FOREIGN KEY(subject_id) REFERENCES subjects (id), 
	FOREIGN KEY(school_id) REFERENCES schools (id)
);

CREATE INDEX ix_topic_mastery_school_id ON topic_mastery (school_id);

CREATE INDEX ix_topic_mastery_student_id ON topic_mastery (student_id);

CREATE TABLE user_badges (
	id INTEGER NOT NULL, 
	student_id INTEGER NOT NULL, 
	badge VARCHAR(40) NOT NULL, 
	school_id INTEGER NOT NULL, 
	created_at DATETIME NOT NULL, 
	updated_at DATETIME NOT NULL, 
	created_by INTEGER, 
	PRIMARY KEY (id), 
	UNIQUE (student_id, badge), 
	FOREIGN KEY(student_id) REFERENCES students (id), 
	FOREIGN KEY(school_id) REFERENCES schools (id)
);

CREATE INDEX ix_user_badges_school_id ON user_badges (school_id);

CREATE INDEX ix_user_badges_student_id ON user_badges (student_id);

CREATE TABLE xp_events (
	id INTEGER NOT NULL, 
	student_id INTEGER NOT NULL, 
	kind VARCHAR(20) NOT NULL, 
	world VARCHAR(20) NOT NULL, 
	xp INTEGER NOT NULL, 
	coins INTEGER NOT NULL, 
	day DATE NOT NULL, 
	meta JSON NOT NULL, 
	school_id INTEGER NOT NULL, 
	created_at DATETIME NOT NULL, 
	updated_at DATETIME NOT NULL, 
	created_by INTEGER, 
	PRIMARY KEY (id), 
	FOREIGN KEY(student_id) REFERENCES students (id), 
	FOREIGN KEY(school_id) REFERENCES schools (id)
);

CREATE INDEX ix_xp_events_day ON xp_events (day);

CREATE INDEX ix_xp_events_kind ON xp_events (kind);

CREATE INDEX ix_xp_events_school_id ON xp_events (school_id);

CREATE INDEX ix_xp_events_student_id ON xp_events (student_id);

CREATE TABLE attempt_answers (
	id INTEGER NOT NULL, 
	attempt_id INTEGER NOT NULL, 
	question_id INTEGER NOT NULL, 
	answer JSON, 
	is_correct BOOLEAN, 
	marks_awarded FLOAT, 
	feedback TEXT NOT NULL, 
	school_id INTEGER NOT NULL, 
	created_at DATETIME NOT NULL, 
	updated_at DATETIME NOT NULL, 
	created_by INTEGER, 
	PRIMARY KEY (id), 
	UNIQUE (attempt_id, question_id), 
	FOREIGN KEY(attempt_id) REFERENCES quiz_attempts (id), 
	FOREIGN KEY(question_id) REFERENCES quiz_questions (id), 
	FOREIGN KEY(school_id) REFERENCES schools (id)
);

CREATE INDEX ix_attempt_answers_attempt_id ON attempt_answers (attempt_id);

CREATE INDEX ix_attempt_answers_question_id ON attempt_answers (question_id);

CREATE INDEX ix_attempt_answers_school_id ON attempt_answers (school_id);

CREATE TABLE leave_approvals (
	id INTEGER NOT NULL, 
	request_id INTEGER NOT NULL, 
	step VARCHAR(12) NOT NULL, 
	approver_user_id INTEGER NOT NULL, 
	decision VARCHAR(10) NOT NULL, 
	comment TEXT NOT NULL, 
	decided_at DATETIME NOT NULL, 
	school_id INTEGER NOT NULL, 
	created_at DATETIME NOT NULL, 
	updated_at DATETIME NOT NULL, 
	created_by INTEGER, 
	PRIMARY KEY (id), 
	FOREIGN KEY(request_id) REFERENCES leave_requests (id), 
	FOREIGN KEY(approver_user_id) REFERENCES users (id), 
	FOREIGN KEY(school_id) REFERENCES schools (id)
);

CREATE INDEX ix_leave_approvals_request_id ON leave_approvals (request_id);

CREATE INDEX ix_leave_approvals_school_id ON leave_approvals (school_id);

CREATE TABLE robo_help (
	id INTEGER NOT NULL, 
	answer_id INTEGER NOT NULL, 
	mode VARCHAR(12) NOT NULL, 
	lang VARCHAR(2) NOT NULL, 
	text TEXT NOT NULL, 
	provider VARCHAR(20) NOT NULL, 
	school_id INTEGER NOT NULL, 
	created_at DATETIME NOT NULL, 
	updated_at DATETIME NOT NULL, 
	created_by INTEGER, 
	PRIMARY KEY (id), 
	UNIQUE (answer_id, mode, lang), 
	FOREIGN KEY(answer_id) REFERENCES attempt_answers (id), 
	FOREIGN KEY(school_id) REFERENCES schools (id)
);

CREATE INDEX ix_robo_help_answer_id ON robo_help (answer_id);

CREATE INDEX ix_robo_help_school_id ON robo_help (school_id);
