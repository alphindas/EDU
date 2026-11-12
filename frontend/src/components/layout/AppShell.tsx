import {
  Award, Baby, BookOpenCheck, CalendarCheck, CalendarDays, CalendarOff, ClipboardList, FileQuestion, GraduationCap, IdCard, LayoutDashboard, LogOut, Moon, NotebookPen,
  Palette, ScanLine, School, Settings, Sun, Users, UsersRound,
} from "lucide-react";
import type { ReactNode } from "react";
import { useTranslation } from "react-i18next";
import { NavLink, Outlet, useNavigate } from "react-router-dom";
import NotificationBell from "@/components/common/NotificationBell";
import { LANGS } from "@/i18n";
import { useAuth } from "@/lib/auth";
import { ACCENTS, useTheme } from "@/lib/theme";
import type { Role } from "@/lib/types";
import { cn } from "@/lib/utils";

interface Item { to: string; key: string; icon: ReactNode; end?: boolean }
const I = (c: typeof School) => { const Ic = c; return <Ic size={18} />; };

const NAV: Record<string, Item[]> = {
  admin: [
    { to: "/admin", key: "nav.dashboard", icon: I(LayoutDashboard), end: true },
    { to: "/admin/structure", key: "nav.structure", icon: I(BookOpenCheck) },
    { to: "/admin/teachers", key: "nav.teachers", icon: I(Users) },
    { to: "/admin/students", key: "nav.students", icon: I(GraduationCap) },
    { to: "/admin/parents", key: "nav.parents", icon: I(UsersRound) },
    { to: "/admin/attendance", key: "nav.attendance", icon: I(CalendarCheck) },
    { to: "/admin/timetable", key: "nav.timetable", icon: I(CalendarDays) },
    { to: "/admin/homework", key: "nav.homework", icon: I(NotebookPen) },
    { to: "/admin/quizzes", key: "nav.quizzes", icon: I(FileQuestion) },
    { to: "/admin/exams", key: "nav.exams", icon: I(ClipboardList) },
    { to: "/admin/report-card", key: "nav.reportCards", icon: I(Award) },
    { to: "/admin/leave", key: "nav.leave", icon: I(CalendarOff) },
    { to: "/admin/id-verify", key: "nav.idVerify", icon: I(ScanLine) },
    { to: "/admin/settings", key: "nav.settings", icon: I(Settings) },
  ],
  teacher: [
    { to: "/teacher", key: "nav.dashboard", icon: I(LayoutDashboard), end: true },
    { to: "/teacher/students", key: "nav.myStudents", icon: I(GraduationCap) },
    { to: "/teacher/attendance", key: "nav.attendance", icon: I(CalendarCheck) },
    { to: "/teacher/timetable", key: "nav.timetable", icon: I(CalendarDays) },
    { to: "/teacher/homework", key: "nav.homework", icon: I(NotebookPen) },
    { to: "/teacher/quizzes", key: "nav.quizzes", icon: I(FileQuestion) },
    { to: "/teacher/exams", key: "nav.exams", icon: I(ClipboardList) },
    { to: "/teacher/report-card", key: "nav.reportCards", icon: I(Award) },
    { to: "/teacher/leave", key: "nav.leave", icon: I(CalendarOff) },
    { to: "/teacher/id-verify", key: "nav.idVerify", icon: I(ScanLine) },
  ],
  student: [
    { to: "/student", key: "nav.dashboard", icon: I(LayoutDashboard), end: true },
    { to: "/student/attendance", key: "nav.attendance", icon: I(CalendarCheck) },
    { to: "/student/timetable", key: "nav.timetable", icon: I(CalendarDays) },
    { to: "/student/homework", key: "nav.homework", icon: I(NotebookPen) },
    { to: "/student/quizzes", key: "nav.quizzes", icon: I(FileQuestion) },
    { to: "/student/exams", key: "nav.exams", icon: I(ClipboardList) },
    { to: "/student/report-card", key: "nav.reportCard", icon: I(Award) },
    { to: "/student/leave", key: "nav.leave", icon: I(CalendarOff) },
    { to: "/student/id-card", key: "nav.idCard", icon: I(IdCard) },
  ],
  parent: [
    { to: "/parent", key: "nav.children", icon: I(Baby), end: true },
    { to: "/parent/attendance", key: "nav.attendance", icon: I(CalendarCheck) },
    { to: "/parent/timetable", key: "nav.timetable", icon: I(CalendarDays) },
    { to: "/parent/homework", key: "nav.homework", icon: I(NotebookPen) },
    { to: "/parent/quizzes", key: "nav.quizzes", icon: I(FileQuestion) },
    { to: "/parent/exams", key: "nav.exams", icon: I(ClipboardList) },
    { to: "/parent/report-card", key: "nav.reportCard", icon: I(Award) },
    { to: "/parent/leave", key: "nav.leave", icon: I(CalendarOff) },
    { to: "/parent/id-card", key: "nav.idCard", icon: I(IdCard) },
  ],
};

export function LangSwitcher() {
  const { i18n } = useTranslation();
  return (
    <select
      aria-label="Language"
      value={i18n.language}
      onChange={(e) => i18n.changeLanguage(e.target.value)}
      className="h-9 rounded-xl border border-line bg-card px-2 text-sm font-medium"
    >
      {LANGS.map((l) => <option key={l.code} value={l.code}>{l.label}</option>)}
    </select>
  );
}

export function ThemeControls() {
  const { dark, toggle, accent, setAccent } = useTheme();
  const next = ACCENTS[(ACCENTS.indexOf(accent) + 1) % ACCENTS.length];
  return (
    <>
      <button onClick={() => setAccent(next)} title={`Accent: ${accent}`} aria-label="Change accent colour" className="grid h-9 w-9 place-items-center rounded-xl text-mute hover:bg-soft hover:text-ink">
        <Palette size={18} />
      </button>
      <button onClick={toggle} aria-label="Toggle theme" className="grid h-9 w-9 place-items-center rounded-xl text-mute hover:bg-soft hover:text-ink">
        {dark ? <Sun size={18} /> : <Moon size={18} />}
      </button>
    </>
  );
}

export function Brand({ className }: { className?: string }) {
  return (
    <div className={cn("flex items-center gap-2.5", className)}>
      <span className="grad-bg grid h-9 w-9 place-items-center rounded-xl text-white shadow-card"><GraduationCap size={20} /></span>
      <span className="text-lg font-extrabold tracking-tight">Edu<span className="grad-text">Nest</span></span>
    </div>
  );
}

export default function AppShell({ role }: { role: Role }) {
  const { t } = useTranslation();
  const nav = useNavigate();
  const { user, logout } = useAuth();
  const items = NAV[role] ?? [];

  const link = (it: Item, mobile = false) => (
    <NavLink
      key={it.to}
      to={it.to}
      end={it.end}
      className={({ isActive }) =>
        cn(
          mobile ? "flex min-w-[4.5rem] flex-1 shrink-0 flex-col items-center gap-0.5 py-2 text-[10px] font-semibold" : "flex items-center gap-3 rounded-xl px-3 py-2.5 text-sm font-semibold",
          isActive ? (mobile ? "text-primary" : "bg-soft text-primary") : "text-mute hover:bg-soft/70 hover:text-ink",
        )
      }
    >
      {it.icon}
      <span>{t(it.key)}</span>
    </NavLink>
  );

  return (
    <div className="min-h-screen lg:grid lg:grid-cols-[260px_1fr]">
      <aside className="sticky top-0 hidden h-screen flex-col border-r border-line bg-card/60 p-4 backdrop-blur lg:flex">
        <Brand className="px-2 py-3" />
        <nav className="mt-6 flex flex-1 flex-col gap-1">{items.map((i) => link(i))}</nav>
        <div className="rounded-xl bg-soft p-3 text-xs text-mute">
          <div className="font-semibold text-ink">{user?.school?.name}</div>
          <div>{user?.school?.code}</div>
        </div>
      </aside>

      <div className="flex min-w-0 flex-col">
        <header className="sticky top-0 z-30 flex h-16 items-center gap-2 border-b border-line bg-bg/80 px-4 backdrop-blur lg:px-8">
          <Brand className="lg:hidden" />
          <div className="ml-auto flex items-center gap-1.5">
            <LangSwitcher />
            <NotificationBell />
            <ThemeControls />
            <div className="mx-2 hidden text-right leading-tight sm:block">
              <div className="text-sm font-semibold">{user?.full_name}</div>
              <div className="text-xs text-mute">{t(`roles.${role}`)}</div>
            </div>
            <button
              onClick={() => { logout(); nav("/login"); }}
              aria-label={t("common.logout")}
              title={t("common.logout")}
              className="grid h-9 w-9 place-items-center rounded-xl text-mute hover:bg-bad/10 hover:text-bad"
            >
              <LogOut size={18} />
            </button>
          </div>
        </header>
        <main className="flex-1 px-4 pb-28 pt-6 lg:px-8 lg:pb-10">
          <Outlet />
        </main>
      </div>

      {items.length > 1 && (
        <nav className="fixed inset-x-0 bottom-0 z-40 flex overflow-x-auto border-t border-line bg-card/95 backdrop-blur lg:hidden">{items.map((i) => link(i, true))}</nav>
      )}
    </div>
  );
}
