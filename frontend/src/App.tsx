import { Navigate, Route, Routes } from "react-router-dom";
import AppShell from "@/components/layout/AppShell";
import { homePath, useAuth } from "@/lib/auth";
import type { Role } from "@/lib/types";
import ChangePassword from "@/pages/ChangePassword";
import Login from "@/pages/Login";
import AdminDashboard from "@/pages/admin/Dashboard";
import Parents from "@/pages/admin/Parents";
import Settings from "@/pages/admin/Settings";
import Structure from "@/pages/admin/Structure";
import Students from "@/pages/admin/Students";
import Teachers from "@/pages/admin/Teachers";
import ParentDashboard from "@/pages/parent/Dashboard";
import StudentDashboard from "@/pages/student/Dashboard";
import TeacherDashboard from "@/pages/teacher/Dashboard";
import TeacherStudents from "@/pages/teacher/Students";
import AdminAttendance from "@/pages/admin/Attendance";
import AdminTimetable from "@/pages/admin/Timetable";
import ParentAttendance from "@/pages/parent/Attendance";
import ParentIdCard from "@/pages/parent/IdCard";
import ParentTimetable from "@/pages/parent/Timetable";
import ChittiPage from "@/pages/shared/Chitti";
import LibraryPage from "@/pages/shared/Library";
import AnnouncementsPage from "@/pages/shared/Announcements";
import MessagesPage from "@/pages/shared/Messages";
import ForumPage from "@/pages/shared/Forum";
import CounsellingPage from "@/pages/shared/Counselling";
import ProjectsPage from "@/pages/shared/Projects";
import BusPage from "@/pages/shared/Bus";
import StudentHome from "@/pages/student/Home";
import Adventure from "@/pages/student/Adventure";
import BrainPage from "@/pages/student/Brain";
import EnglishPage from "@/pages/student/English";
import CareerPage from "@/pages/student/Career";
import GrowthPage from "@/pages/student/Growth";
import TeacherInsights from "@/pages/teacher/Insights";
import ParentHome from "@/pages/parent/Home";
import ParentProgress from "@/pages/parent/Progress";
import Intelligence from "@/pages/admin/Intelligence";
import TransportAdmin from "@/pages/admin/Transport";
import Safety from "@/pages/admin/Safety";
import LearningPage from "@/pages/shared/Learning";
import StudentFlashcards from "@/pages/student/Flashcards";
import TeacherGaps from "@/pages/teacher/Gaps";
import ExamsPage from "@/pages/shared/Exams";
import HomeworkPage from "@/pages/shared/Homework";
import IdVerifyPage from "@/pages/shared/IdVerify";
import LeavePage from "@/pages/shared/Leave";
import QuizzesPage from "@/pages/shared/Quizzes";
import ReportCardPage from "@/pages/shared/ReportCard";
import StudentAttendance from "@/pages/student/Attendance";
import StudentIdCard from "@/pages/student/IdCard";
import StudentTimetable from "@/pages/student/Timetable";
import TeacherAttendance from "@/pages/teacher/Attendance";
import TeacherTimetable from "@/pages/teacher/Timetable";

/** Route guard: wrong role -> bounce to your own group; not logged in -> /login; forced pw change -> /change-password. */
function Guard({ role }: { role: Role }) {
  const user = useAuth((s) => s.user);
  if (!user) return <Navigate to="/login" replace />;
  if (user.must_change_password) return <Navigate to="/change-password" replace />;
  if (user.role !== role) return <Navigate to={homePath(user.role)} replace />;
  return <AppShell role={role} />;
}

function Root() {
  const user = useAuth((s) => s.user);
  return <Navigate to={user ? homePath(user.role) : "/login"} replace />;
}

export default function App() {
  return (
    <Routes>
      <Route path="/" element={<Root />} />
      <Route path="/login" element={<Login />} />
      <Route path="/change-password" element={<ChangePassword />} />

      <Route path="/admin" element={<Guard role="admin" />}>
        <Route index element={<AdminDashboard />} />
        <Route path="structure" element={<Structure />} />
        <Route path="teachers" element={<Teachers />} />
        <Route path="students" element={<Students />} />
        <Route path="parents" element={<Parents />} />
        <Route path="attendance" element={<AdminAttendance />} />
        <Route path="timetable" element={<AdminTimetable />} />
        <Route path="homework" element={<HomeworkPage />} />
        <Route path="quizzes" element={<QuizzesPage />} />
        <Route path="exams" element={<ExamsPage />} />
        <Route path="report-card" element={<ReportCardPage />} />
        <Route path="leave" element={<LeavePage />} />
        <Route path="id-verify" element={<IdVerifyPage />} />
        <Route path="settings" element={<Settings />} />
        <Route path="intelligence" element={<Intelligence />} />
        <Route path="library" element={<LibraryPage />} />
        <Route path="announcements" element={<AnnouncementsPage />} />
        <Route path="transport" element={<TransportAdmin />} />
        <Route path="safety" element={<Safety />} />
      </Route>
      <Route path="/teacher" element={<Guard role="teacher" />}>
        <Route index element={<TeacherDashboard />} />
        <Route path="students" element={<TeacherStudents />} />
        <Route path="attendance" element={<TeacherAttendance />} />
        <Route path="timetable" element={<TeacherTimetable />} />
        <Route path="homework" element={<HomeworkPage />} />
        <Route path="quizzes" element={<QuizzesPage />} />
        <Route path="exams" element={<ExamsPage />} />
        <Route path="report-card" element={<ReportCardPage />} />
        <Route path="gaps" element={<TeacherGaps />} />
        <Route path="ai-chat" element={<ChittiPage />} />
        <Route path="leave" element={<LeavePage />} />
        <Route path="id-verify" element={<IdVerifyPage />} />
        <Route path="insights" element={<TeacherInsights />} />
        <Route path="chitti" element={<ChittiPage />} />
        <Route path="library" element={<LibraryPage />} />
        <Route path="announcements" element={<AnnouncementsPage />} />
        <Route path="messages" element={<MessagesPage />} />
        <Route path="forum" element={<ForumPage />} />
        <Route path="projects" element={<ProjectsPage />} />
        <Route path="counselling" element={<CounsellingPage />} />
      </Route>
      <Route path="/student" element={<Guard role="student" />}>
        <Route index element={<StudentHome />} />
        <Route path="profile" element={<StudentDashboard />} />
        <Route path="chitti" element={<ChittiPage />} />
        <Route path="adventure" element={<Adventure />} />
        <Route path="brain" element={<BrainPage />} />
        <Route path="english" element={<EnglishPage />} />
        <Route path="career" element={<CareerPage />} />
        <Route path="growth" element={<GrowthPage />} />
        <Route path="library" element={<LibraryPage />} />
        <Route path="announcements" element={<AnnouncementsPage />} />
        <Route path="messages" element={<MessagesPage />} />
        <Route path="forum" element={<ForumPage />} />
        <Route path="projects" element={<ProjectsPage />} />
        <Route path="counselling" element={<CounsellingPage />} />
        <Route path="bus" element={<BusPage />} />
        <Route path="attendance" element={<StudentAttendance />} />
        <Route path="timetable" element={<StudentTimetable />} />
        <Route path="homework" element={<HomeworkPage />} />
        <Route path="quizzes" element={<QuizzesPage />} />
        <Route path="exams" element={<ExamsPage />} />
        <Route path="report-card" element={<ReportCardPage />} />
        <Route path="ai-chat" element={<ChittiPage />} />
        <Route path="learning" element={<LearningPage />} />
        <Route path="flashcards" element={<StudentFlashcards />} />
        <Route path="leave" element={<LeavePage />} />
        <Route path="id-card" element={<StudentIdCard />} />
      </Route>
      <Route path="/parent" element={<Guard role="parent" />}>
        <Route index element={<ParentHome />} />
        <Route path="children" element={<ParentDashboard />} />
        <Route path="chitti" element={<ChittiPage />} />
        <Route path="progress" element={<ParentProgress />} />
        <Route path="announcements" element={<AnnouncementsPage />} />
        <Route path="messages" element={<MessagesPage />} />
        <Route path="bus" element={<BusPage />} />
        <Route path="attendance" element={<ParentAttendance />} />
        <Route path="timetable" element={<ParentTimetable />} />
        <Route path="homework" element={<HomeworkPage />} />
        <Route path="quizzes" element={<QuizzesPage />} />
        <Route path="exams" element={<ExamsPage />} />
        <Route path="report-card" element={<ReportCardPage />} />
        <Route path="learning" element={<LearningPage />} />
        <Route path="leave" element={<LeavePage />} />
        <Route path="id-card" element={<ParentIdCard />} />
      </Route>
      <Route path="*" element={<Root />} />
    </Routes>
  );
}
