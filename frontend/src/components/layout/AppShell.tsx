import { useQueryClient } from "@tanstack/react-query";
import {
  Award, Baby, Bot, Check, Palette, BookOpen, BrainCircuit, Bus, CalendarCheck, CalendarDays, CalendarOff, ClipboardList, Compass, FileQuestion,
  Flower2, Gamepad2, GraduationCap, HeartHandshake, Home, IdCard, Layers, LayoutGrid, LineChart, LogOut, Megaphone, MessageCircle, MessagesSquare,
  Mic, Moon, NotebookPen, Rocket, ScanLine, School, Settings, ShieldCheck, Sparkles, Sun, Target, Users, UsersRound, X,
} from "lucide-react";
import { type ReactNode, useEffect, useRef, useState } from "react";
import { useTranslation } from "react-i18next";
import { Link, NavLink, Outlet, useLocation, useNavigate } from "react-router-dom";
import NotificationBell from "@/components/common/NotificationBell";
import { toast } from "@/components/common/toast";
import { CelebrationLayer } from "@/components/fun/Celebrate";
import Chitti from "@/components/fun/Chitti";
import { LANGS } from "@/i18n";
import { API_BASE } from "@/lib/api";
import { useAuth } from "@/lib/auth";
import { ACCENTS, PALETTES, useTheme } from "@/lib/theme";
import type { Role } from "@/lib/types";
import { cn } from "@/lib/utils";

type Ic = typeof School;
interface Item { to: string; key: string; icon: Ic; tone: string; end?: boolean }
interface Group { key: string; items: Item[] }

// tone = colour chip behind the icon (kid-friendly, consistent per feature)
const T = { sky: "bg-soft text-primary", sun: "bg-amber-100 text-amber-600", mint: "bg-emerald-100 text-emerald-600", lav: "bg-violet-100 text-violet-600",
  coral: "bg-orange-100 text-orange-600", rose: "bg-rose-100 text-rose-600", navy: "bg-indigo-100 text-indigo-700", teal: "bg-teal-100 text-teal-600" };

const NAV: Record<string, Group[]> = {
  student: [
    { key: "navg.home", items: [
      { to: "/student", key: "nav.home", icon: Home, tone: T.sky, end: true },
      { to: "/student/chitti", key: "nav.chitti", icon: Bot, tone: T.lav },
      { to: "/student/adventure", key: "nav.adventure", icon: Gamepad2, tone: T.sun },
      { to: "/student/brain", key: "nav.brain", icon: BrainCircuit, tone: T.rose },
    ] },
    { key: "navg.learn", items: [
      { to: "/student/learning", key: "nav.learning", icon: Target, tone: T.mint },
      { to: "/student/quizzes", key: "nav.quizzes", icon: FileQuestion, tone: T.coral },
      { to: "/student/exams", key: "nav.exams", icon: ClipboardList, tone: T.navy },
      { to: "/student/flashcards", key: "nav.flashcards", icon: Layers, tone: T.teal },
      { to: "/student/library", key: "nav.library", icon: BookOpen, tone: T.sky },
      { to: "/student/english", key: "nav.english", icon: Mic, tone: T.rose },
      { to: "/student/career", key: "nav.career", icon: Compass, tone: T.sun },
    ] },
    { key: "navg.school", items: [
      { to: "/student/timetable", key: "nav.timetable", icon: CalendarDays, tone: T.sky },
      { to: "/student/homework", key: "nav.homework", icon: NotebookPen, tone: T.mint },
      { to: "/student/attendance", key: "nav.attendance", icon: CalendarCheck, tone: T.teal },
      { to: "/student/report-card", key: "nav.reportCard", icon: Award, tone: T.sun },
      { to: "/student/announcements", key: "nav.announcements", icon: Megaphone, tone: T.coral },
      { to: "/student/bus", key: "nav.bus", icon: Bus, tone: T.sun },
      { to: "/student/leave", key: "nav.leave", icon: CalendarOff, tone: T.rose },
      { to: "/student/id-card", key: "nav.idCard", icon: IdCard, tone: T.navy },
    ] },
    { key: "navg.connect", items: [
      { to: "/student/messages", key: "nav.messages", icon: MessageCircle, tone: T.sky },
      { to: "/student/forum", key: "nav.forum", icon: MessagesSquare, tone: T.lav },
      { to: "/student/projects", key: "nav.projects", icon: Rocket, tone: T.coral },
      { to: "/student/growth", key: "nav.growth", icon: Flower2, tone: T.mint },
      { to: "/student/counselling", key: "nav.counselling", icon: HeartHandshake, tone: T.rose },
    ] },
  ],
  teacher: [
    { key: "navg.home", items: [
      { to: "/teacher", key: "nav.dashboard", icon: Home, tone: T.sky, end: true },
      { to: "/teacher/insights", key: "nav.insights", icon: LineChart, tone: T.lav },
      { to: "/teacher/chitti", key: "nav.chitti", icon: Bot, tone: T.mint },
    ] },
    { key: "navg.academics", items: [
      { to: "/teacher/students", key: "nav.myStudents", icon: GraduationCap, tone: T.navy },
      { to: "/teacher/attendance", key: "nav.attendance", icon: CalendarCheck, tone: T.teal },
      { to: "/teacher/timetable", key: "nav.timetable", icon: CalendarDays, tone: T.sky },
      { to: "/teacher/homework", key: "nav.homework", icon: NotebookPen, tone: T.mint },
      { to: "/teacher/quizzes", key: "nav.quizzes", icon: FileQuestion, tone: T.coral },
      { to: "/teacher/exams", key: "nav.exams", icon: ClipboardList, tone: T.navy },
      { to: "/teacher/report-card", key: "nav.reportCards", icon: Award, tone: T.sun },
      { to: "/teacher/gaps", key: "nav.gaps", icon: Target, tone: T.rose },
      { to: "/teacher/library", key: "nav.library", icon: BookOpen, tone: T.sky },
    ] },
    { key: "navg.connect", items: [
      { to: "/teacher/announcements", key: "nav.announcements", icon: Megaphone, tone: T.coral },
      { to: "/teacher/messages", key: "nav.messages", icon: MessageCircle, tone: T.sky },
      { to: "/teacher/forum", key: "nav.forum", icon: MessagesSquare, tone: T.lav },
      { to: "/teacher/projects", key: "nav.projects", icon: Rocket, tone: T.coral },
      { to: "/teacher/counselling", key: "nav.counselling", icon: HeartHandshake, tone: T.rose },
      { to: "/teacher/leave", key: "nav.leave", icon: CalendarOff, tone: T.rose },
      { to: "/teacher/id-verify", key: "nav.idVerify", icon: ScanLine, tone: T.navy },
    ] },
  ],
  parent: [
    { key: "navg.home", items: [
      { to: "/parent", key: "nav.children", icon: Baby, tone: T.sky, end: true },
      { to: "/parent/chitti", key: "nav.parentChitti", icon: Bot, tone: T.lav },
      { to: "/parent/progress", key: "nav.progress", icon: Sparkles, tone: T.sun },
    ] },
    { key: "navg.school", items: [
      { to: "/parent/attendance", key: "nav.attendance", icon: CalendarCheck, tone: T.teal },
      { to: "/parent/timetable", key: "nav.timetable", icon: CalendarDays, tone: T.sky },
      { to: "/parent/homework", key: "nav.homework", icon: NotebookPen, tone: T.mint },
      { to: "/parent/quizzes", key: "nav.quizzes", icon: FileQuestion, tone: T.coral },
      { to: "/parent/exams", key: "nav.exams", icon: ClipboardList, tone: T.navy },
      { to: "/parent/report-card", key: "nav.reportCard", icon: Award, tone: T.sun },
      { to: "/parent/learning", key: "nav.learning", icon: BrainCircuit, tone: T.rose },
      { to: "/parent/bus", key: "nav.bus", icon: Bus, tone: T.sun },
      { to: "/parent/id-card", key: "nav.idCard", icon: IdCard, tone: T.navy },
    ] },
    { key: "navg.connect", items: [
      { to: "/parent/announcements", key: "nav.announcements", icon: Megaphone, tone: T.coral },
      { to: "/parent/messages", key: "nav.messages", icon: MessageCircle, tone: T.sky },
      { to: "/parent/leave", key: "nav.leave", icon: CalendarOff, tone: T.rose },
    ] },
  ],
  admin: [
    { key: "navg.home", items: [
      { to: "/admin", key: "nav.dashboard", icon: Home, tone: T.sky, end: true },
      { to: "/admin/intelligence", key: "nav.intelligence", icon: LineChart, tone: T.lav },
    ] },
    { key: "navg.people", items: [
      { to: "/admin/structure", key: "nav.structure", icon: LayoutGrid, tone: T.navy },
      { to: "/admin/teachers", key: "nav.teachers", icon: Users, tone: T.mint },
      { to: "/admin/students", key: "nav.students", icon: GraduationCap, tone: T.sky },
      { to: "/admin/parents", key: "nav.parents", icon: UsersRound, tone: T.coral },
    ] },
    { key: "navg.academics", items: [
      { to: "/admin/attendance", key: "nav.attendance", icon: CalendarCheck, tone: T.teal },
      { to: "/admin/timetable", key: "nav.timetable", icon: CalendarDays, tone: T.sky },
      { to: "/admin/homework", key: "nav.homework", icon: NotebookPen, tone: T.mint },
      { to: "/admin/quizzes", key: "nav.quizzes", icon: FileQuestion, tone: T.coral },
      { to: "/admin/exams", key: "nav.exams", icon: ClipboardList, tone: T.navy },
      { to: "/admin/report-card", key: "nav.reportCards", icon: Award, tone: T.sun },
      { to: "/admin/library", key: "nav.library", icon: BookOpen, tone: T.sky },
    ] },
    { key: "navg.manage", items: [
      { to: "/admin/announcements", key: "nav.announcements", icon: Megaphone, tone: T.coral },
      { to: "/admin/leave", key: "nav.leave", icon: CalendarOff, tone: T.rose },
      { to: "/admin/transport", key: "nav.transport", icon: Bus, tone: T.sun },
      { to: "/admin/safety", key: "nav.safety", icon: ShieldCheck, tone: T.mint },
      { to: "/admin/id-verify", key: "nav.idVerify", icon: ScanLine, tone: T.navy },
      { to: "/admin/settings", key: "nav.settings", icon: Settings, tone: T.navy },
    ] },
  ],
};
const MOBILE_MAIN: Record<string, string[]> = {
  student: ["/student", "/student/chitti", "/student/adventure", "/student/quizzes"],
  teacher: ["/teacher", "/teacher/attendance", "/teacher/quizzes", "/teacher/insights"],
  parent: ["/parent", "/parent/chitti", "/parent/attendance", "/parent/messages"],
  admin: ["/admin", "/admin/intelligence", "/admin/students", "/admin/announcements"],
};

export function LangSwitcher({ className }: { className?: string }) {
  const { i18n } = useTranslation();
  return (
    <select aria-label="Language" value={i18n.language} onChange={(e) => i18n.changeLanguage(e.target.value)}
      className={cn("h-10 rounded-2xl border-2 border-line bg-card px-2 text-sm font-bold text-ink", className)}>
      {LANGS.map((l) => <option key={l.code} value={l.code}>{l.flag} {l.label}</option>)}
    </select>
  );
}

export function ThemeControls() {
  const { dark, toggle, accent, setAccent } = useTheme();
  const { t } = useTranslation();
  const [open, setOpen] = useState(false);
  const box = useRef<HTMLDivElement>(null);
  useEffect(() => {
    if (!open) return;
    const close = (e: MouseEvent) => { if (box.current && !box.current.contains(e.target as Node)) setOpen(false); };
    const esc = (e: KeyboardEvent) => { if (e.key === "Escape") setOpen(false); };
    document.addEventListener("mousedown", close);
    document.addEventListener("keydown", esc);
    return () => { document.removeEventListener("mousedown", close); document.removeEventListener("keydown", esc); };
  }, [open]);
  return (
    <div className="relative" ref={box}>
      <button onClick={() => setOpen((o) => !o)} aria-label={t("palette.title")} title={t("palette.title")} aria-expanded={open}
        className="grid h-10 w-10 place-items-center rounded-2xl text-mute hover:bg-soft hover:text-ink">
        <Palette size={19} />
      </button>
      {open && (
        <div role="dialog" aria-label={t("palette.title")} className="absolute right-0 top-12 z-50 w-80 rounded-2xl border border-line bg-card p-4 shadow-pop animate-fade">
          <div className="mb-3 flex items-center justify-between">
            <span className="text-sm font-bold">{t("palette.title")}</span>
            <button onClick={toggle} className="flex items-center gap-1.5 rounded-xl border border-line px-2.5 py-1 text-xs font-semibold text-mute hover:text-ink">
              {dark ? <Sun size={14} /> : <Moon size={14} />}{dark ? t("palette.light") : t("palette.dark")}
            </button>
          </div>
          <div className="grid grid-cols-4 gap-2">
            {ACCENTS.map((a) => (
              <button key={a} onClick={() => setAccent(a)} aria-pressed={accent === a} title={t(`palette.${a}`)}
                className={cn("flex flex-col items-center gap-1 rounded-xl p-1.5 text-[11px] font-semibold text-mute transition hover:bg-soft",
                  accent === a && "bg-soft text-ink")}>
                <span className={cn("relative grid h-9 w-9 place-items-center rounded-full ring-2 ring-offset-2 ring-offset-card",
                  accent === a ? "ring-ink/60" : "ring-transparent")}
                  style={{ background: `linear-gradient(135deg, ${PALETTES[a][0]} 50%, ${PALETTES[a][1]} 50%)` }}>
                  {accent === a && <Check size={16} className="text-white drop-shadow" />}
                </span>
                <span className="w-full truncate text-center">{t(`palette.${a}`)}</span>
              </button>
            ))}
          </div>
          <p className="mt-3 text-[11px] text-mute">{t("palette.hint")}</p>
        </div>
      )}
    </div>
  );
}

export function Brand({ className }: { className?: string }) {
  return (
    <Link to="/" className={cn("flex items-center gap-2", className)}>
      <Chitti size={42} float={false} />
      <span className="leading-none">
        <span className="block font-display text-[1.45rem] font-extrabold tracking-tight text-navy dark:text-ink">Edu<span className="text-primary">Nest</span></span>
        <span className="hidden text-[10px] font-bold uppercase tracking-[.18em] text-mute sm:block">2.0 · Learn · Grow</span>
      </span>
    </Link>
  );
}

/** One WebSocket per signed-in user: new DMs / notifications refresh counts instantly. Silently falls back to polling. */
function useLive() {
  const qc = useQueryClient();
  const access = useAuth((s) => s.access);
  const { t } = useTranslation();
  useEffect(() => {
    if (!access) return;
    const base = API_BASE || window.location.origin;
    const url = `${base.replace(/^http/, "ws")}/api/ws?token=${encodeURIComponent(access)}`;
    let ws: WebSocket | null = null;
    let ping: ReturnType<typeof setInterval> | undefined;
    try {
      ws = new WebSocket(url);
      ws.onmessage = (e) => {
        const m = JSON.parse(e.data);
        if (m.type === "dm") {
          toast(t("msg.newFrom", { name: m.name }));
          qc.invalidateQueries({ queryKey: ["dm"] });
          qc.invalidateQueries({ queryKey: ["contacts"] });
          qc.invalidateQueries({ queryKey: ["notif-count"] });
        }
      };
      ping = setInterval(() => ws?.readyState === 1 && ws.send("ping"), 25_000);
    } catch { /* websockets unavailable: polling still works */ }
    return () => { clearInterval(ping); ws?.close(); };
  }, [access, qc, t]);
}

export default function AppShell({ role }: { role: Role }) {
  const { t } = useTranslation();
  const nav = useNavigate();
  const loc = useLocation();
  const { user, logout } = useAuth();
  const [more, setMore] = useState(false);
  const groups = NAV[role] ?? [];
  const all = groups.flatMap((g) => g.items);
  useLive();
  useEffect(() => { setMore(false); }, [loc.pathname]);

  const item = (it: Item) => (
    <NavLink key={it.to} to={it.to} end={it.end}
      className={({ isActive }) => cn("group flex items-center gap-3 rounded-2xl px-2.5 py-2 text-[0.92rem] font-bold transition",
        isActive ? "bg-card text-ink shadow-card ring-2 ring-primary/25" : "text-mute hover:bg-card/70 hover:text-ink")}>
      <span className={cn("grid h-8 w-8 shrink-0 place-items-center rounded-xl transition group-hover:scale-110", it.tone)}><it.icon size={17} /></span>
      <span className="truncate">{t(it.key)}</span>
    </NavLink>
  );
  const mobileMain = (MOBILE_MAIN[role] ?? []).map((p) => all.find((i) => i.to === p)).filter(Boolean) as Item[];
  const showFab = role === "student" && !loc.pathname.startsWith("/student/chitti");

  return (
    <div className="min-h-screen lg:grid lg:grid-cols-[272px_1fr]">
      <a href="#main" className="sr-only focus:not-sr-only focus:fixed focus:left-2 focus:top-2 focus:z-[90] focus:rounded-xl focus:bg-card focus:p-2">{t("common.skip")}</a>
      <aside className="sticky top-0 hidden h-screen flex-col border-r-2 border-line/70 bg-soft/40 p-4 backdrop-blur lg:flex">
        <Brand className="px-1 py-1" />
        <nav className="no-scrollbar mt-4 flex-1 space-y-4 overflow-y-auto pb-4" aria-label={t("common.menu")}>
          {groups.map((g) => (
            <div key={g.key}>
              <div className="mb-1 px-3 text-[11px] font-extrabold uppercase tracking-[.14em] text-mute/80">{t(g.key)}</div>
              <div className="space-y-0.5">{g.items.map(item)}</div>
            </div>
          ))}
        </nav>
        <div className="rounded-2xl border-2 border-dashed border-line bg-card/70 p-3 text-xs">
          <div className="flex items-center gap-2 font-bold text-ink"><School size={14} /> {user?.school?.name}</div>
          <div className="mt-0.5 text-mute">{user?.school?.code} · {t("tagline")}</div>
        </div>
      </aside>

      <div className="flex min-w-0 flex-col">
        <header className="no-print sticky top-0 z-30 flex h-16 items-center gap-2 border-b-2 border-line/60 bg-bg/85 px-3 backdrop-blur lg:px-8">
          <Brand className="lg:hidden" />
          <div className="ml-auto flex items-center gap-1 sm:gap-1.5">
            <LangSwitcher className="max-w-[7.5rem]" />
            <NotificationBell />
            <ThemeControls />
            <div className="mx-1 hidden items-center gap-2 rounded-2xl bg-card px-2 py-1 shadow-card sm:flex">
              <span className="grid h-8 w-8 place-items-center rounded-xl grad-bg text-sm font-extrabold text-white">{user?.full_name?.[0] ?? "?"}</span>
              <div className="pr-1 leading-tight">
                <div className="max-w-[9rem] truncate text-sm font-bold">{user?.full_name}</div>
                <div className="text-[11px] font-semibold text-mute">{t(`roles.${role}`)}</div>
              </div>
            </div>
            <button onClick={() => { logout(); nav("/login"); }} aria-label={t("common.logout")} title={t("common.logout")}
              className="grid h-10 w-10 place-items-center rounded-2xl text-mute hover:bg-bad/10 hover:text-bad"><LogOut size={19} /></button>
          </div>
        </header>
        <main id="main" className="flex-1 px-3 pb-28 pt-5 sm:px-5 lg:px-8 lg:pb-10">
          <Outlet />
        </main>
      </div>

      {/* mobile: 4 main tabs + "More" sheet with everything */}
      <nav className="no-print fixed inset-x-0 bottom-0 z-40 flex border-t-2 border-line bg-card/95 px-1 pb-[env(safe-area-inset-bottom)] backdrop-blur lg:hidden" aria-label={t("common.menu")}>
        {mobileMain.map((it) => (
          <NavLink key={it.to} to={it.to} end={it.end} className={({ isActive }) => cn("flex flex-1 flex-col items-center gap-0.5 py-2 text-[11px] font-bold", isActive ? "text-primary" : "text-mute")}>
            {({ isActive }) => (<><span className={cn("grid h-8 w-10 place-items-center rounded-xl transition", isActive && it.tone)}><it.icon size={19} /></span><span className="max-w-[4.5rem] truncate">{t(it.key)}</span></>)}
          </NavLink>
        ))}
        <button onClick={() => setMore(true)} className="flex flex-1 flex-col items-center gap-0.5 py-2 text-[11px] font-bold text-mute">
          <span className="grid h-8 w-10 place-items-center rounded-xl"><LayoutGrid size={19} /></span>{t("common.more")}
        </button>
      </nav>
      {more && (
        <div className="fixed inset-0 z-50 bg-navy/30 backdrop-blur-sm lg:hidden" onClick={() => setMore(false)}>
          <div className="absolute inset-x-0 bottom-0 max-h-[80vh] overflow-y-auto rounded-t-3xl bg-bg p-4 pb-8 animate-fade" onClick={(e) => e.stopPropagation()}>
            <div className="mb-3 flex items-center justify-between"><span className="font-display text-xl font-extrabold">{t("common.allFeatures")}</span>
              <button onClick={() => setMore(false)} className="rounded-xl p-2 hover:bg-soft" aria-label={t("common.close")}><X size={20} /></button></div>
            {groups.map((g) => (
              <div key={g.key} className="mb-4">
                <div className="mb-2 text-[11px] font-extrabold uppercase tracking-[.14em] text-mute">{t(g.key)}</div>
                <div className="grid grid-cols-4 gap-2">
                  {g.items.map((it) => (
                    <NavLink key={it.to} to={it.to} end={it.end} className="flex flex-col items-center gap-1 rounded-2xl bg-card p-2 text-center text-[11px] font-bold shadow-card">
                      <span className={cn("grid h-10 w-10 place-items-center rounded-xl", it.tone)}><it.icon size={19} /></span>
                      <span className="line-clamp-2">{t(it.key)}</span>
                    </NavLink>
                  ))}
                </div>
              </div>
            ))}
          </div>
        </div>
      )}

      {showFab && (
        <Link to="/student/chitti" aria-label={t("chitti.open")} className="no-print fixed bottom-24 right-4 z-40 flex items-center gap-2 rounded-full bg-card py-1 pl-1 pr-1 sm:pr-4 shadow-pop ring-4 ring-primary/20 transition hover:-translate-y-1 lg:bottom-6">
          <Chitti size={48} mood="wave" float={false} />
          <span className="hidden font-display text-base font-extrabold text-navy sm:block dark:text-ink">{t("chitti.ask")}</span>
        </Link>
      )}
      <CelebrationLayer />
    </div>
  );
}

export const PageHero = ({ title, subtitle, emoji, children, tone = "grad-sky" }: { title: string; subtitle?: string; emoji?: string; children?: ReactNode; tone?: string }) => (
  <div className={cn("relative mb-5 overflow-hidden rounded-3xl p-5 text-navy shadow-card sm:p-6", tone)}>
    <div className="relative z-10 flex flex-wrap items-center justify-between gap-3">
      <div>
        <h1 className="font-display text-2xl font-extrabold leading-tight sm:text-3xl">{emoji && <span className="mr-2">{emoji}</span>}{title}</h1>
        {subtitle && <p className="mt-1 max-w-2xl text-sm font-semibold text-navy/75">{subtitle}</p>}
      </div>
      {children}
    </div>
    <div className="pointer-events-none absolute -right-8 -top-10 h-40 w-40 rounded-full bg-white/30" aria-hidden />
    <div className="pointer-events-none absolute -bottom-12 right-24 h-28 w-28 rounded-full bg-white/20" aria-hidden />
  </div>
);
